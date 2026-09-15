#!/usr/bin/env python3
"""Local helper for the linear-ops skill.

This script validates a Linear routing file and renders safe local drafts.
It can also query Linear when a token is already present in the environment.
It intentionally does not read .env files or persist secrets.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover - validation environment issue
    raise SystemExit(
        "PyYAML is required for linear_ops.py; install it with "
        "'python3 -m pip install PyYAML'"
    ) from exc


REQUIRED_TOP_LEVEL = {
    "version",
    "workspace",
    "defaults",
    "statuses",
    "priorities",
    "ticket_types",
    "domains",
    "dashboard_views",
    "approval_gates",
}

SUPPORTED_VIEW_FILTERS = {
    "assignee",
    "labels",
    "priority",
    "project",
    "state",
    "team",
    "unassigned",
}

PRIORITY_TO_INT = {
    "Urgent": 1,
    "High": 2,
    "Medium": 3,
    "Low": 4,
    "No priority": 0,
    "None": 0,
}

INT_TO_PRIORITY = {
    0: "No priority",
    1: "Urgent",
    2: "High",
    3: "Medium",
    4: "Low",
}

LINEAR_API_URL = "https://api.linear.app/graphql"


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing config: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a YAML mapping: {path}")
    return data


def load_seed_tickets(path: Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    if not path.exists():
        raise SystemExit(f"Missing seed ticket file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return []
    if not isinstance(data, dict):
        raise SystemExit(f"Seed ticket file must be a YAML mapping: {path}")
    tickets = data.get("tickets", [])
    if not isinstance(tickets, list):
        raise SystemExit("Seed ticket file key 'tickets' must be a list")
    for idx, ticket in enumerate(tickets, start=1):
        if not isinstance(ticket, dict):
            raise SystemExit(f"Seed ticket #{idx} must be a mapping")
        for key in ("title", "domain", "type", "summary"):
            if key not in ticket:
                raise SystemExit(f"Seed ticket #{idx} missing {key!r}")
        for key in ("labels", "tasks"):
            if key in ticket and not isinstance(ticket[key], list):
                raise SystemExit(f"Seed ticket #{idx} {key!r} must be a list")
    return tickets


def validate_config(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL - set(data))
    if missing:
        errors.append(f"Missing top-level keys: {', '.join(missing)}")

    workspace = data.get("workspace")
    if not isinstance(workspace, dict) or not str(workspace.get("name", "")).strip():
        errors.append("workspace must include a non-empty name")

    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        errors.append("defaults must be a mapping")
    else:
        team = defaults.get("team")
        if not isinstance(team, dict) or not (
            str(team.get("key", "")).strip() or str(team.get("name", "")).strip()
        ):
            errors.append("defaults.team must include key or name")

    domains = data.get("domains")
    if not isinstance(domains, dict) or not domains:
        errors.append("domains must be a non-empty mapping")
    else:
        for name, domain in domains.items():
            if not isinstance(domain, dict):
                errors.append(f"domain {name!r} must be a mapping")
                continue
            for key in ("labels",):
                if key not in domain:
                    errors.append(f"domain {name!r} missing {key!r}")
            if not str(domain.get("project") or domain.get("planned_project") or "").strip():
                errors.append(f"domain {name!r} must include project or planned_project")
            for key in ("labels", "repos"):
                if key in domain and not isinstance(domain[key], list):
                    errors.append(f"domain {name!r} {key!r} must be a list")
                elif key in domain and any(not isinstance(value, str) for value in domain[key]):
                    errors.append(f"domain {name!r} {key!r} must contain only strings")

    if isinstance(defaults, dict):
        default_domain = defaults.get("domain")
        if default_domain and not isinstance(default_domain, str):
            errors.append("defaults.domain must be a string")
        elif default_domain and isinstance(domains, dict) and default_domain not in domains:
            errors.append(f"defaults.domain {default_domain!r} is not configured")

    for section in ("statuses", "priorities", "ticket_types", "approval_gates"):
        if section in data and not isinstance(data[section], dict):
            errors.append(f"{section} must be a mapping")

    ticket_types = data.get("ticket_types")
    if isinstance(ticket_types, dict):
        for name, ticket_type in ticket_types.items():
            if not isinstance(ticket_type, dict):
                errors.append(f"ticket type {name!r} must be a mapping")
                continue
            if "labels" in ticket_type and not isinstance(ticket_type["labels"], list):
                errors.append(f"ticket type {name!r} labels must be a list")
            elif "labels" in ticket_type and any(
                not isinstance(value, str) for value in ticket_type["labels"]
            ):
                errors.append(f"ticket type {name!r} labels must contain only strings")

    dashboard_views = data.get("dashboard_views")
    if not isinstance(dashboard_views, list) or not dashboard_views:
        errors.append("dashboard_views must be a non-empty list")
    else:
        for idx, view in enumerate(dashboard_views, start=1):
            if not isinstance(view, dict) or "name" not in view:
                errors.append(f"dashboard view #{idx} must include name")
                continue
            filters = view.get("filters", {})
            if not isinstance(filters, dict):
                errors.append(f"dashboard view #{idx} filters must be a mapping")
                continue
            unknown = sorted(set(filters) - SUPPORTED_VIEW_FILTERS)
            if unknown:
                errors.append(
                    f"dashboard view #{idx} has unsupported filters: {', '.join(unknown)}"
                )

    return errors


def pick_domain(data: dict[str, Any], domain_name: str | None) -> tuple[str, dict[str, Any]]:
    domains = data.get("domains", {})
    if domain_name:
        if domain_name not in domains:
            raise SystemExit(f"Unknown domain {domain_name!r}; choose from: {', '.join(domains)}")
        return domain_name, domains[domain_name]
    default_domain = data.get("defaults", {}).get("domain")
    if default_domain in domains:
        return default_domain, domains[default_domain]
    if domains:
        first = next(iter(domains))
        return first, domains[first]
    raise SystemExit("No domains configured")


def default_labels(data: dict[str, Any], ticket_type: str) -> list[str]:
    types = data.get("ticket_types", {})
    labels = []
    if ticket_type in types:
        labels.extend(types[ticket_type].get("labels", []) or [])
    return labels


def token_from_env() -> str:
    token = os.environ.get("LINEAR_API_KEY", "").strip()
    if not token:
        raise SystemExit(
            "Missing LINEAR_API_KEY. Export a Linear API key in this shell, or use Linear MCP."
        )
    return token


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def linear_request(token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(
        LINEAR_API_URL,
        data=body,
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Linear API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Linear API connection failed: {exc}") from exc

    if payload.get("errors"):
        messages = "; ".join(error.get("message", str(error)) for error in payload["errors"])
        raise SystemExit(f"Linear API GraphQL error: {messages}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SystemExit("Linear API response did not include data")
    return data


def issue_label_names(issue: dict[str, Any]) -> list[str]:
    return [
        label.get("name", "")
        for label in ((issue.get("labels") or {}).get("nodes") or [])
        if label.get("name")
    ]


def issue_is_open(issue: dict[str, Any]) -> bool:
    state = issue.get("state") or {}
    state_type = (state.get("type") or "").lower()
    state_name = (state.get("name") or "").lower()
    return state_type not in {"completed", "canceled"} and state_name not in {"done", "canceled"}


def issue_is_completed(issue: dict[str, Any]) -> bool:
    state = issue.get("state") or {}
    return (
        (state.get("type") or "").casefold() == "completed"
        or (state.get("name") or "").casefold() == "done"
    )


def issue_priority_name(issue: dict[str, Any]) -> str:
    return INT_TO_PRIORITY.get(issue.get("priority"), str(issue.get("priority", "")))


def issue_has_label(issue: dict[str, Any], *names: str) -> bool:
    labels = {name.casefold() for name in issue_label_names(issue)}
    return any(name.casefold() in labels for name in names)


def issue_is_waiting_or_blocked(issue: dict[str, Any]) -> bool:
    state_name = ((issue.get("state") or {}).get("name") or "").casefold()
    return (
        "waiting" in state_name
        or "blocked" in state_name
        or issue_has_label(issue, "needs-decision", "waiting-for-decision", "blocked")
    )


def issue_is_agent_ready(issue: dict[str, Any]) -> bool:
    state_name = ((issue.get("state") or {}).get("name") or "").casefold()
    return state_name == "ready" or issue_has_label(issue, "agent-ready")


def issue_is_customer_facing(issue: dict[str, Any]) -> bool:
    return issue_has_label(issue, "customer-facing")


def filter_values(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def value_matches(actual: Any, expected: Any) -> bool:
    actual_text = str(actual or "").casefold()
    return any(
        actual_text == str(candidate or "").casefold()
        for candidate in filter_values(expected)
    )


def issue_matches_view(issue: dict[str, Any], filters: dict[str, Any]) -> bool:
    state = issue.get("state") or {}
    team = issue.get("team") or {}
    project = issue.get("project") or {}
    assignee = issue.get("assignee") or {}
    for key, expected in filters.items():
        if key == "state":
            if any(str(value).casefold() == "open" for value in filter_values(expected)):
                if not issue_is_open(issue):
                    return False
            elif not (
                value_matches(state.get("name"), expected)
                or value_matches(state.get("type"), expected)
            ):
                return False
        elif key == "labels":
            expected_labels = {str(value).casefold() for value in filter_values(expected)}
            issue_labels = {name.casefold() for name in issue_label_names(issue)}
            if not expected_labels.intersection(issue_labels):
                return False
        elif key == "priority":
            if not (
                value_matches(issue_priority_name(issue), expected)
                or value_matches(issue.get("priority"), expected)
            ):
                return False
        elif key == "project":
            if not value_matches(project.get("name"), expected):
                return False
        elif key == "team":
            if not (
                value_matches(team.get("key"), expected)
                or value_matches(team.get("name"), expected)
            ):
                return False
        elif key == "assignee":
            if not (
                value_matches(assignee.get("name"), expected)
                or value_matches(assignee.get("email"), expected)
            ):
                return False
        elif key == "unassigned":
            is_unassigned = not assignee.get("id") and not assignee.get("name")
            if bool(expected) != is_unassigned:
                return False
    return True


def issues_for_dashboard(data: dict[str, Any], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    views = data.get("dashboard_views", [])
    if not views:
        return issues
    return [
        issue
        for issue in issues
        if any(issue_matches_view(issue, view.get("filters", {}) or {}) for view in views)
    ]


def priority_to_int(priority: str | int | None) -> int:
    if isinstance(priority, int):
        return priority
    if not priority:
        return 3
    return PRIORITY_TO_INT.get(str(priority), 3)


def issue_sort_key(issue: dict[str, Any]) -> tuple[int, str]:
    priority = issue.get("priority")
    priority_rank = priority if isinstance(priority, int) and priority > 0 else 99
    return (priority_rank, issue.get("updatedAt") or "")


def recent_issue_sort_key(issue: dict[str, Any]) -> str:
    return issue.get("updatedAt") or ""


def print_issue_line(issue: dict[str, Any]) -> None:
    state = (issue.get("state") or {}).get("name", "")
    project = (issue.get("project") or {}).get("name") or "No project"
    assignee = (issue.get("assignee") or {}).get("name") or "Unassigned"
    labels = ", ".join(issue_label_names(issue))
    label_suffix = f" [{labels}]" if labels else ""
    print(
        f"- {issue.get('identifier')} {issue.get('title')} "
        f"({project}; {state}; {issue_priority_name(issue)}; {assignee}){label_suffix}"
    )
    if issue.get("url"):
        print(f"  {issue['url']}")


def issue_summary(issue: dict[str, Any]) -> dict[str, str]:
    state = (issue.get("state") or {}).get("name", "")
    project = (issue.get("project") or {}).get("name") or "No project"
    assignee = (issue.get("assignee") or {}).get("name") or "Unassigned"
    labels = ", ".join(issue_label_names(issue))
    return {
        "identifier": str(issue.get("identifier") or ""),
        "title": str(issue.get("title") or ""),
        "url": str(issue.get("url") or ""),
        "project": str(project),
        "state": str(state),
        "priority": issue_priority_name(issue),
        "assignee": str(assignee),
        "labels": labels,
    }


def fetch_recent_issues(token: str, first: int) -> list[dict[str, Any]]:
    query = """
    query LinearOpsRecentIssues($first: Int!) {
      issues(first: $first, orderBy: updatedAt) {
        nodes {
          id
          identifier
          title
          url
          priority
          updatedAt
          createdAt
          state { id name type }
          team { id key name }
          project { id name }
          assignee { id name email }
          labels { nodes { id name } }
        }
      }
    }
    """
    data = linear_request(token, query, {"first": first})
    return ((data.get("issues") or {}).get("nodes") or [])


def seed_ticket_to_issue(data: dict[str, Any], ticket: dict[str, Any], idx: int) -> dict[str, Any]:
    domain_name, domain = pick_domain(data, ticket.get("domain"))
    ticket_type = ticket.get("type", "feature")
    labels = list(
        dict.fromkeys(
            default_labels(data, ticket_type)
            + (domain.get("labels") or [])
            + (ticket.get("labels") or [])
        )
    )
    status = ticket.get("status") or data.get("ticket_types", {}).get(ticket_type, {}).get("default_status", "Triage")
    state_type = "completed" if status == "Done" else "canceled" if status == "Canceled" else "started"
    priority = ticket.get("priority") or data.get("ticket_types", {}).get(ticket_type, {}).get("default_priority", "Medium")
    timestamp = ticket.get("updated_at") or ticket.get("created_at")
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    key = ticket.get("key") or f"SEED-{idx:03d}"
    tasks = [str(task) for task in ticket.get("tasks", []) or []]
    url = ticket.get("url") or ticket_url_from_fields(
        data,
        domain_name,
        domain,
        ticket_type,
        ticket["title"],
        ticket.get("summary", ""),
        tasks,
        priority,
        status,
        [str(label) for label in ticket.get("labels", []) or []],
    )
    return {
        "id": f"seed-{key}",
        "identifier": key,
        "title": ticket["title"],
        "url": url,
        "priority": priority_to_int(priority),
        "updatedAt": timestamp,
        "createdAt": ticket.get("created_at") or timestamp,
        "state": {"id": f"seed-state-{status}", "name": status, "type": state_type},
        "team": {
            "id": data["defaults"]["team"].get("id") or "seed-team",
            "key": data["defaults"]["team"].get("key"),
            "name": data["defaults"]["team"].get("name"),
        },
        "project": {"id": f"seed-project-{domain_name}", "name": domain.get("project")},
        "assignee": (
            {"id": "seed-assignee", "name": str(ticket["assignee"]), "email": ""}
            if ticket.get("assignee")
            else {"id": None, "name": None, "email": ""}
        ),
        "labels": {"nodes": [{"id": f"seed-label-{label}", "name": label} for label in labels]},
        "seed": ticket,
    }


def seed_tickets_to_issues(data: dict[str, Any], tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [seed_ticket_to_issue(data, ticket, idx) for idx, ticket in enumerate(tickets, start=1)]


def html_attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def html_text(value: Any) -> str:
    return html.escape(str(value))


def safe_http_url(value: Any) -> str:
    candidate = str(value or "").strip()
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc:
        return candidate
    return ""


def write_output(content: str, output: Path | None) -> None:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Wrote {output}")
    else:
        print(content)


def filters_text(filters: dict[str, Any]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in filters.items())


def issue_card_html(issue: dict[str, Any]) -> str:
    summary = issue_summary(issue)
    title = html_text(summary["title"])
    identifier = html_text(summary["identifier"])
    safe_url = safe_http_url(summary["url"])
    url = html_attr(safe_url)
    labels = html_text(summary["labels"])
    label_html = f'<div class="labels">{labels}</div>' if labels else ""
    if safe_url:
        heading = f'<a href="{url}">{identifier} {title}</a>'
    else:
        heading = f"{identifier} {title}".strip()
    return f"""
          <article class="issue">
            <h3>{heading}</h3>
            <div class="meta">
              <span>{html_text(summary["project"])}</span>
              <span>{html_text(summary["state"])}</span>
              <span>{html_text(summary["priority"])}</span>
              <span>{html_text(summary["assignee"])}</span>
            </div>
            {label_html}
          </article>"""


def render_dashboard_html(
    data: dict[str, Any],
    issues: list[dict[str, Any]] | None = None,
    mode: str = "spec",
    stale_days: int = 14,
    per_section: int = 10,
) -> str:
    issues = issues or []
    now = datetime.now(timezone.utc)
    domains = data.get("domains", {})
    views = data.get("dashboard_views", [])
    open_issues = [issue for issue in issues if issue_is_open(issue)]
    completed = [issue for issue in issues if issue_is_completed(issue)]

    def render_issue_list(section_issues: list[dict[str, Any]], empty: str) -> str:
        if not section_issues:
            return f'<p class="empty">{html_text(empty)}</p>'
        return "\n".join(issue_card_html(issue) for issue in section_issues[:per_section])

    waiting = [
        issue
        for issue in open_issues
        if issue_is_waiting_or_blocked(issue)
    ]
    agent_ready = [
        issue
        for issue in open_issues
        if issue_is_agent_ready(issue)
    ]
    customer = [
        issue for issue in open_issues if issue_is_customer_facing(issue)
    ]
    stale = []
    for issue in open_issues:
        updated = issue.get("updatedAt")
        if not updated:
            continue
        updated_at = parse_timestamp(updated)
        if not updated_at:
            continue
        if (now - updated_at).days > stale_days:
            stale.append(issue)

    by_project: dict[str, list[dict[str, Any]]] = {}
    for issue in open_issues:
        project_name = (issue.get("project") or {}).get("name") or "No project"
        by_project.setdefault(project_name, []).append(issue)

    if mode == "live":
        status_text = "Live read-only Linear data"
        command_html = "Live dashboard rendered from Linear GraphQL API."
        issue_count_label = "open live issues loaded"
        command_heading = "Live Command Dashboard"
    elif mode == "seed":
        status_text = "Seed ticket preview"
        command_html = (
            "Linear MCP is not connected here yet. This dashboard shows the seed "
            "backlog mapped through the routing config. Regenerate with --live after "
            "MCP auth or LINEAR_API_KEY."
        )
        issue_count_label = "seed issues loaded"
        command_heading = "Seed Command Dashboard"
    else:
        status_text = "Configuration preview"
        command_html = (
            "Linear MCP is not connected here yet. This dashboard shows the configured "
            "operating model and will render live data after MCP auth or LINEAR_API_KEY."
        )
        issue_count_label = "issues loaded"
        command_heading = "Configuration Command Dashboard"

    domain_rows = []
    for name, domain in domains.items():
        repos = "<br>".join(html_text(repo) for repo in (domain.get("repos") or [])) or "No repo"
        labels = ", ".join(domain.get("labels") or [])
        domain_rows.append(
            f"<tr><td>{html_text(name)}</td><td>{html_text(domain.get('project', ''))}</td>"
            f"<td>{html_text(labels)}</td><td>{repos}</td></tr>"
        )

    view_blocks = []
    for view in views:
        filters = filters_text(view.get("filters", {}) or {})
        view_blocks.append(
            f"""
        <section class="view">
          <h3>{html_text(view.get("name", ""))}</h3>
          <p>{html_text(view.get("purpose", ""))}</p>
          <code>{html_text(filters)}</code>
        </section>"""
        )

    project_sections = []
    for project_name in sorted(by_project):
        project_sections.append(
            f"""
        <section class="project">
          <h3>{html_text(project_name)}</h3>
          {render_issue_list(sorted(by_project[project_name], key=issue_sort_key), "No open issues.")}
        </section>"""
        )
    if not project_sections:
        project_sections.append('<p class="empty">No live issues loaded.</p>')

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_text(data['workspace']['name'])} Linear Dashboard</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #202329;
      --muted: #667085;
      --line: #d9dde5;
      --accent: #365e9d;
      --accent-soft: #e8eef8;
      --warn: #8a4b18;
      --warn-soft: #fff4e5;
      --ok: #23704a;
      --ok-soft: #e8f5ee;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 24px clamp(18px, 4vw, 44px);
    }}
    main {{
      padding: 22px clamp(18px, 4vw, 44px) 48px;
      max-width: 1440px;
      margin: 0 auto;
    }}
    h1, h2, h3 {{ margin: 0; letter-spacing: 0; }}
    h1 {{ font-size: 26px; }}
    h2 {{ font-size: 18px; margin: 28px 0 12px; }}
    h3 {{ font-size: 14px; margin-bottom: 8px; }}
    p {{ margin: 0 0 10px; color: var(--muted); }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{
      display: block;
      white-space: normal;
      color: #374151;
      background: #f3f4f6;
      border: 1px solid var(--line);
      padding: 8px;
      border-radius: 6px;
      overflow-wrap: anywhere;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
    }}
    th, td {{
      text-align: left;
      vertical-align: top;
      padding: 10px;
      border-bottom: 1px solid var(--line);
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    .toolbar {{
      margin-top: 14px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 10px;
      border-radius: 6px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 600;
    }}
    .badge.warn {{ background: var(--warn-soft); color: var(--warn); }}
    .badge.ok {{ background: var(--ok-soft); color: var(--ok); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
    }}
    .view, .project, .issue, .notice {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .notice {{
      margin-top: 16px;
      border-color: #ead6b8;
      background: var(--warn-soft);
    }}
    .issue + .issue {{ margin-top: 8px; }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .meta span {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 2px 6px;
    }}
    .labels {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .empty {{
      background: var(--panel);
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    @media (max-width: 720px) {{
      h1 {{ font-size: 22px; }}
      table, thead, tbody, th, td, tr {{ display: block; }}
      th {{ display: none; }}
      td {{ border-bottom: 0; }}
      tr {{ border-bottom: 1px solid var(--line); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html_text(data['workspace']['name'])} Linear Dashboard</h1>
    <div class="toolbar">
      <span class="badge {'ok' if mode == 'live' else 'warn'}">{html_text(status_text)}</span>
      <span class="badge">{len(domains)} domains</span>
      <span class="badge">{len(views)} views</span>
      <span class="badge">{len(open_issues)} {html_text(issue_count_label)}</span>
      <span class="badge">Generated {html_text(generated)}</span>
    </div>
    <div class="notice">{html_text(command_html)}</div>
  </header>
  <main>
    <h2>Dashboard Views</h2>
    <div class="grid">
      {''.join(view_blocks)}
    </div>

    <h2>{html_text(command_heading)}</h2>
    {''.join(project_sections)}

    <h2>Waiting or Blocked Work</h2>
    {render_issue_list(sorted(waiting, key=issue_sort_key), "No matching live issues loaded.")}

    <h2>Agent-Ready Work</h2>
    {render_issue_list(sorted(agent_ready, key=issue_sort_key), "No matching live issues loaded.")}

    <h2>Customer-Facing Work</h2>
    {render_issue_list(sorted(customer, key=issue_sort_key), "No matching live issues loaded.")}

    <h2>Stale Open Work</h2>
    {render_issue_list(sorted(stale, key=issue_sort_key), "No stale live issues loaded.")}

    <h2>Recently Completed Work</h2>
    {render_issue_list(sorted(completed, key=recent_issue_sort_key, reverse=True), "No recently completed issues loaded.")}

    <h2>Routing Domains</h2>
    <table>
      <thead>
        <tr><th>Domain</th><th>Project</th><th>Labels</th><th>Repos</th></tr>
      </thead>
      <tbody>
        {''.join(domain_rows)}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def cmd_validate(args: argparse.Namespace) -> int:
    data = load_config(args.config)
    errors = validate_config(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.config} is valid")
    return 0


def cmd_api_check(args: argparse.Namespace) -> int:
    token = token_from_env()
    query = """
    query LinearOpsHealth {
      viewer { id name email }
      teams { nodes { id key name } }
    }
    """
    data = linear_request(token, query)
    viewer = data.get("viewer") or {}
    teams = ((data.get("teams") or {}).get("nodes") or [])
    print(f"OK: authenticated as {viewer.get('name')} <{viewer.get('email')}>")
    print(f"Teams visible: {len(teams)}")
    for team in teams[:20]:
        print(f"- {team.get('key')} {team.get('name')} ({team.get('id')})")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    token = token_from_env()
    query = """
    query LinearOpsDiscovery {
      viewer { id name email }
      organization { id name urlKey }
      teams {
        nodes {
          id
          key
          name
          states { nodes { id name type } }
        }
      }
      projects { nodes { id name state } }
      issueLabels { nodes { id name team { id key name } } }
    }
    """
    data = linear_request(token, query)
    organization = data.get("organization") or {}
    print(f"# {organization.get('name', 'Linear')} discovery")
    print()
    print("## Teams")
    for team in ((data.get("teams") or {}).get("nodes") or []):
        print(f"- {team.get('key')} {team.get('name')} ({team.get('id')})")
        for state in ((team.get("states") or {}).get("nodes") or []):
            print(f"  - state: {state.get('name')} [{state.get('type')}] {state.get('id')}")
    print()
    print("## Projects")
    for project in ((data.get("projects") or {}).get("nodes") or []):
        print(f"- {project.get('name')} [{project.get('state')}] {project.get('id')}")
    print()
    print("## Labels")
    for label in ((data.get("issueLabels") or {}).get("nodes") or []):
        team = label.get("team") or {}
        scope = team.get("key") or "workspace"
        print(f"- {label.get('name')} ({scope}) {label.get('id')}")
    return 0


def cmd_dashboard_spec(args: argparse.Namespace) -> int:
    data = load_config(args.config)
    errors = validate_config(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"# {data['workspace']['name']} Linear Dashboard")
    print()
    for view in data["dashboard_views"]:
        print(f"## {view['name']}")
        print()
        print(view.get("purpose", "No purpose configured."))
        filters = view.get("filters", {})
        if filters:
            print()
            print("Filters:")
            for key, value in filters.items():
                print(f"- {key}: {value}")
        print()
    return 0


def cmd_dashboard_live(args: argparse.Namespace) -> int:
    token = token_from_env()
    data = load_config(args.config)
    errors = validate_config(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    issues = issues_for_dashboard(data, fetch_recent_issues(token, args.limit))
    open_issues = [issue for issue in issues if issue_is_open(issue)]
    now = datetime.now(timezone.utc)

    print(f"# {data['workspace']['name']} Linear Dashboard")
    print()

    print("## Command Dashboard")
    print()
    by_project: dict[str, list[dict[str, Any]]] = {}
    for issue in open_issues:
        project_name = (issue.get("project") or {}).get("name") or "No project"
        by_project.setdefault(project_name, []).append(issue)
    for project_name in sorted(by_project):
        print(f"### {project_name}")
        for issue in sorted(by_project[project_name], key=issue_sort_key)[: args.per_section]:
            print_issue_line(issue)
        print()

    print("## Waiting or Blocked Work")
    print()
    waiting = [
        issue
        for issue in open_issues
        if issue_is_waiting_or_blocked(issue)
    ]
    for issue in sorted(waiting, key=issue_sort_key)[: args.per_section]:
        print_issue_line(issue)
    if not waiting:
        print("- None found.")
    print()

    print("## Agent-Ready Work")
    print()
    agent_ready = [
        issue
        for issue in open_issues
        if issue_is_agent_ready(issue)
    ]
    for issue in sorted(agent_ready, key=issue_sort_key)[: args.per_section]:
        print_issue_line(issue)
    if not agent_ready:
        print("- None found.")
    print()

    print("## Customer-Facing Work")
    print()
    customer = [
        issue for issue in open_issues if issue_is_customer_facing(issue)
    ]
    for issue in sorted(customer, key=issue_sort_key)[: args.per_section]:
        print_issue_line(issue)
    if not customer:
        print("- None found.")
    print()

    print("## Recently Completed Work")
    print()
    completed = [issue for issue in issues if issue_is_completed(issue)]
    for issue in sorted(completed, key=recent_issue_sort_key, reverse=True)[: args.per_section]:
        print_issue_line(issue)
    if not completed:
        print("- None found.")
    print()

    stale_days = args.stale_days
    print(f"## Stale Open Work (>{stale_days} days)")
    print()
    stale = []
    for issue in open_issues:
        updated = issue.get("updatedAt")
        if not updated:
            continue
        updated_at = parse_timestamp(updated)
        if not updated_at:
            continue
        if (now - updated_at).days > stale_days:
            stale.append(issue)
    for issue in sorted(stale, key=issue_sort_key)[: args.per_section]:
        print_issue_line(issue)
    if not stale:
        print("- None found.")
    return 0


def cmd_dashboard_html(args: argparse.Namespace) -> int:
    data = load_config(args.config)
    errors = validate_config(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    issues: list[dict[str, Any]] = []
    mode = "spec"
    if args.live:
        token = token_from_env()
        issues = issues_for_dashboard(data, fetch_recent_issues(token, args.limit))
        mode = "live"
    elif args.seed:
        issues = issues_for_dashboard(
            data, seed_tickets_to_issues(data, load_seed_tickets(args.seed))
        )
        mode = "seed"

    content = render_dashboard_html(
        data,
        issues=issues,
        mode=mode,
        stale_days=args.stale_days,
        per_section=args.per_section,
    )
    write_output(content, args.output)
    return 0


def ticket_url_from_fields(
    data: dict[str, Any],
    domain_name: str,
    domain: dict[str, Any],
    ticket_type: str,
    title: str,
    summary: str,
    tasks: list[str],
    priority: str,
    status: str,
    extra_labels: list[str] | None = None,
) -> str:
    labels = list(
        dict.fromkeys(
            default_labels(data, ticket_type)
            + (domain.get("labels") or [])
            + (extra_labels or [])
        )
    )
    description = build_ticket_description(
        title=title,
        summary=summary,
        tasks=tasks,
        repos=domain.get("repos") or [],
        duplicate_pending=True,
    )
    team = data["defaults"]["team"].get("key") or data["defaults"]["team"].get("name")
    params = {
        "title": title,
        "description": description,
        "team": team,
        "status": status,
        "priority": (
            str(priority).casefold()
            if str(priority).casefold() in {"urgent", "high", "medium", "low"}
            else ""
        ),
        "labels": ",".join(labels),
        "project": domain.get("project", ""),
    }
    encoded = urllib.parse.urlencode({key: value for key, value in params.items() if value})
    return f"https://linear.new?{encoded}"


def cmd_draft_ticket(args: argparse.Namespace) -> int:
    data = load_config(args.config)
    errors = validate_config(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    domain_name, domain = pick_domain(data, args.domain)
    ticket_type = args.type
    labels = list(dict.fromkeys(default_labels(data, ticket_type) + (domain.get("labels") or [])))
    priority = args.priority or data.get("ticket_types", {}).get(ticket_type, {}).get("default_priority", "Medium")
    status = args.status or data.get("ticket_types", {}).get(ticket_type, {}).get("default_status", "Triage")
    tasks = [item.strip() for item in (args.tasks or "").split(";") if item.strip()]
    project = domain.get("project")
    planned_project = domain.get("planned_project")
    project_display = project or (f"{planned_project} (planned)" if planned_project else "")

    print(f"# {args.title}")
    print()
    print("| Field | Value |")
    print("|---|---|")
    print(f"| Type | {ticket_type} |")
    print(f"| Domain | {domain_name} |")
    team = data["defaults"]["team"]
    print(f"| Team | {team.get('name') or team.get('key')} |")
    print(f"| Project | {project_display} |")
    print(f"| Status | {status} |")
    print(f"| Priority | {priority} |")
    print(f"| Labels | {', '.join(labels)} |")
    print()
    print("## Outcome")
    print()
    print(args.summary or "TBD")
    print()
    print("## Context")
    print()
    print("Draft generated locally. Duplicate check is pending until live Linear access is connected.")
    print()
    print("## Scope")
    print()
    print("- TBD")
    print()
    print("## Acceptance Criteria")
    print()
    print("- [ ] Outcome is implemented or answered.")
    print("- [ ] Verification evidence is attached or summarized.")
    print()
    print("## Tasks")
    print()
    if tasks:
        for task in tasks:
            print(f"- [ ] {task}")
    else:
        print("- [ ] Define implementation tasks.")
    print()
    print("## Links")
    print()
    for repo in domain.get("repos", []) or []:
        print(f"- {repo}")
    print()
    print("## Open Questions")
    print()
    print("- None captured yet.")
    return 0


def build_ticket_description(
    title: str,
    summary: str,
    tasks: list[str],
    repos: list[str],
    duplicate_pending: bool,
) -> str:
    lines = [
        "## Outcome",
        "",
        summary or "TBD",
        "",
        "## Context",
        "",
    ]
    if duplicate_pending:
        lines.append("Duplicate check is pending until live Linear access is connected.")
    else:
        lines.append("Duplicate check completed before creation.")
    lines.extend(
        [
            "",
            "## Scope",
            "",
            "- TBD",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Outcome is implemented or answered.",
            "- [ ] Verification evidence is attached or summarized.",
            "",
            "## Tasks",
            "",
        ]
    )
    if tasks:
        lines.extend(f"- [ ] {task}" for task in tasks)
    else:
        lines.append("- [ ] Define implementation tasks.")
    lines.extend(["", "## Links", ""])
    if repos:
        lines.extend(f"- {repo}" for repo in repos)
    else:
        lines.append("- None")
    lines.extend(["", "## Open Questions", "", "- None captured yet."])
    return "\n".join(lines)


def cmd_ticket_url(args: argparse.Namespace) -> int:
    data = load_config(args.config)
    errors = validate_config(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    domain_name, domain = pick_domain(data, args.domain)
    ticket_type = args.type
    priority = args.priority or data.get("ticket_types", {}).get(ticket_type, {}).get("default_priority", "Medium")
    status = args.status or data.get("ticket_types", {}).get(ticket_type, {}).get("default_status", "Triage")
    tasks = [item.strip() for item in (args.tasks or "").split(";") if item.strip()]
    print(f"# Pre-filled Linear URL for {domain_name}")
    print()
    print(
        ticket_url_from_fields(
            data,
            domain_name,
            domain,
            ticket_type,
            args.title,
            args.summary,
            tasks,
            priority,
            status,
        )
    )
    return 0


def cmd_seed_urls(args: argparse.Namespace) -> int:
    data = load_config(args.config)
    errors = validate_config(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    tickets = load_seed_tickets(args.seed)
    for idx, ticket in enumerate(tickets, start=1):
        domain_name, domain = pick_domain(data, ticket.get("domain"))
        ticket_type = ticket.get("type", "feature")
        priority = ticket.get("priority") or data.get("ticket_types", {}).get(ticket_type, {}).get("default_priority", "Medium")
        status = ticket.get("status") or data.get("ticket_types", {}).get(ticket_type, {}).get("default_status", "Triage")
        tasks = ticket.get("tasks") or []
        if not isinstance(tasks, list):
            raise SystemExit(f"Seed ticket #{idx} tasks must be a list")
        print(f"## {ticket.get('key', f'SEED-{idx:03d}')} {ticket['title']}")
        print()
        print(
            ticket_url_from_fields(
                data,
                domain_name,
                domain,
                ticket_type,
                ticket["title"],
                ticket.get("summary", ""),
                [str(task) for task in tasks],
                priority,
                status,
                [str(label) for label in ticket.get("labels", []) or []],
            )
        )
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Linear Ops local helper")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-config", help="validate routing config")
    validate.add_argument("--config", type=Path, required=True)
    validate.set_defaults(func=cmd_validate)

    api_check = sub.add_parser("api-check", help="verify Linear API token")
    api_check.set_defaults(func=cmd_api_check)

    discover = sub.add_parser("discover", help="list Linear teams, states, projects, and labels")
    discover.set_defaults(func=cmd_discover)

    dashboard = sub.add_parser("dashboard-spec", help="render dashboard views")
    dashboard.add_argument("--config", type=Path, required=True)
    dashboard.set_defaults(func=cmd_dashboard_spec)

    live_dashboard = sub.add_parser("dashboard-live", help="render dashboard from live Linear issues")
    live_dashboard.add_argument("--config", type=Path, required=True)
    live_dashboard.add_argument("--limit", type=int, default=100)
    live_dashboard.add_argument("--per-section", type=int, default=10)
    live_dashboard.add_argument("--stale-days", type=int, default=14)
    live_dashboard.set_defaults(func=cmd_dashboard_live)

    html_dashboard = sub.add_parser("dashboard-html", help="render dashboard HTML")
    html_dashboard.add_argument("--config", type=Path, required=True)
    html_dashboard.add_argument("--output", type=Path)
    dashboard_source = html_dashboard.add_mutually_exclusive_group()
    dashboard_source.add_argument("--live", action="store_true")
    dashboard_source.add_argument("--seed", type=Path)
    html_dashboard.add_argument("--limit", type=int, default=100)
    html_dashboard.add_argument("--per-section", type=int, default=10)
    html_dashboard.add_argument("--stale-days", type=int, default=14)
    html_dashboard.set_defaults(func=cmd_dashboard_html)

    draft = sub.add_parser("draft-ticket", help="render a local ticket draft")
    draft.add_argument("--config", type=Path, required=True)
    draft.add_argument("--title", required=True)
    draft.add_argument("--summary", default="")
    draft.add_argument("--domain")
    draft.add_argument("--type", default="feature")
    draft.add_argument("--priority")
    draft.add_argument("--status")
    draft.add_argument("--tasks", default="", help="semicolon-separated tasks")
    draft.set_defaults(func=cmd_draft_ticket)

    ticket_url = sub.add_parser("ticket-url", help="render a pre-filled linear.new URL")
    ticket_url.add_argument("--config", type=Path, required=True)
    ticket_url.add_argument("--title", required=True)
    ticket_url.add_argument("--summary", default="")
    ticket_url.add_argument("--domain")
    ticket_url.add_argument("--type", default="feature")
    ticket_url.add_argument("--priority")
    ticket_url.add_argument("--status")
    ticket_url.add_argument("--tasks", default="", help="semicolon-separated tasks")
    ticket_url.set_defaults(func=cmd_ticket_url)

    seed_urls = sub.add_parser("seed-urls", help="render pre-filled URLs for seed tickets")
    seed_urls.add_argument("--config", type=Path, required=True)
    seed_urls.add_argument("--seed", type=Path, required=True)
    seed_urls.set_defaults(func=cmd_seed_urls)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
