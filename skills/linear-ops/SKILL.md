---
name: linear-ops
description: Manage work in Linear. Use when a user asks to create, draft, route, prioritize, search, update, summarize, triage, or dashboard tasks, tickets, issues, backlog items, roadmap work, repo work, feature requests, bugs, chores, spikes, decisions, or follow-ups in Linear.
---

# Linear Ops

## Overview

Use this skill as the operating layer between messy conversation and structured
Linear work. Linear is the task source of truth; project documentation remains
the durable memory and decision layer.

Prefer Linear MCP tools when they are available in the current client. If MCP is
not connected, use the GraphQL API only when an authenticated token is explicitly
available through the runtime. Do not read `.env` files. If no live Linear access
exists, produce a safe ticket draft and tell the user what authentication is
needed.

Authentication priority:

1. Primary: use the host's authenticated Linear MCP connection for live reads
   and writes supported by the available tools.
2. Secondary: use the bundled helper's read-only GraphQL commands only when a
   `LINEAR_API_KEY` is already present in the environment. Never ask the user
   to paste a key into chat, read `.env` files, or persist the key.
3. If neither path is available, stay in draft/specification mode and explain
   what connection is needed.

Capability modes:

- `dry-run`: no auth; render dashboard spec and ticket drafts.
- `prefilled URL`: no auth; generate a `linear.new` URL the user can open/save.
- `live`: Linear MCP or `LINEAR_API_KEY` is available; search, discover,
  dashboard, and write according to approval gates.

## Required Context

1. If the project has a `.glue/linear-routing.yaml`, read the nearest one before
   creating, routing, or updating work. If no routing file exists, use explicit
   team/project information and do not invent workspace-specific labels or
   statuses.
2. If present, read `.glue/linear-seed-tickets.yaml` when bootstrapping the
   first backlog or rendering the local seed dashboard.
3. Read `references/ticketing-policy.md` when mapping conversational work into
   ticket type, priority, queue, labels, or dashboard views.
4. Read `references/linear-docs.md` before configuring Linear, using API/MCP
   fields, or answering questions about Linear capabilities.

## Workflow

1. Classify the request.
- `feature`: new user/system capability.
- `bug`: broken or regressed behavior.
- `chore`: maintenance, cleanup, dependency, docs hygiene.
- `research`: information gathering with an output.
- `spike`: bounded technical uncertainty reduction.
- `decision`: A designated decision-maker must choose among options.
- `ops`: business/process/infrastructure coordination.

2. Gather enough context.
- Use the current conversation first.
- Inspect relevant repo files when ticket scope, acceptance criteria, or labels
  depend on actual code/state.
- Keep tickets outcome-oriented; do not turn every implementation detail into a
  separate issue unless it can be worked independently.

3. Route through `.glue/linear-routing.yaml` when it exists.
- Match by repo path, domain keywords, and existing project names.
- Prefer the configured default team when no domain is clear.
- Put ambiguous items in the workspace's configured triage status; put
  actionable items in its configured ready status; use the workspace's
  equivalent of `Waiting for decision` only when a decision is required.

4. Search before create.
- Search Linear for similar open issues by title keywords, repo label, project,
  and domain labels.
- If a likely duplicate exists, propose updating/commenting/linking it instead
  of creating a new issue.
- If live access is unavailable, state that duplicate checking is pending.

5. Draft the ticket.
- Include: title, type, project/team, status, priority, labels, summary,
  context, scope, acceptance criteria, tasks/checklist, links, and open
  questions.
- Use Markdown; Linear's editor supports Markdown-style content.
- Keep titles specific and imperative or outcome-based.

6. Apply write policy.
- Normal issue creation from an explicit user request may be live once Linear is
  connected and duplicate check is complete.
- Show a dry-run draft first when the request says "discussed", "the thing",
  "all tasks", or otherwise depends heavily on implicit context.
- Ask before destructive or externally meaningful writes: archive/delete,
  close work as done, mark urgent, commit public/customer promises, create many
  issues/projects, or alter global workflow/labels.

7. Update memory.
- Link Linear issue/project IDs from the project's configured durable state file
  only when they affect active priorities or durable decisions.
- Do not mirror the backlog into Markdown.

## Dashboard Workflow

When the user asks to view the dashboard:

1. If Linear access exists, query open issues/projects using the configured
   dashboard views in `.glue/linear-routing.yaml`.
2. Return a concise operating dashboard: active work, blocked/waiting items,
   decisions needed from the user, stale work, and recently completed items.
3. If Linear access is not connected, show the intended dashboard views from the
   routing file and say live data requires Linear authentication.

Use the bundled `scripts/linear_ops.py dashboard-spec --config
.glue/linear-routing.yaml` to render the configured dashboard plan locally when
a routing file exists. Use `dashboard-live` when `LINEAR_API_KEY` is exported.
Use `dashboard-html` when the user wants a local browser-viewable dashboard
artifact. Add `--seed .glue/linear-seed-tickets.yaml` to render the local seed
backlog before Linear is authenticated.

## Helper Script

Use `scripts/linear_ops.py` for deterministic local work:

The helper requires Python 3.10+ and PyYAML. If PyYAML is not already
available, install the bundled dependency with
`python3 -m pip install -r <skill-root>/scripts/requirements.txt`.

- Invoke the bundled script from its installed skill directory, for example
  `python3 <skill-root>/scripts/linear_ops.py ...`.
- If the host provides a `linear-ops` wrapper, that wrapper may be used instead.

Examples below use `<skill-root>` as the installed skill directory.

```bash
python3 <skill-root>/scripts/linear_ops.py validate-config --config .glue/linear-routing.yaml
python3 <skill-root>/scripts/linear_ops.py api-check
python3 <skill-root>/scripts/linear_ops.py discover
python3 <skill-root>/scripts/linear_ops.py dashboard-spec --config .glue/linear-routing.yaml
python3 <skill-root>/scripts/linear_ops.py dashboard-live --config .glue/linear-routing.yaml
python3 <skill-root>/scripts/linear_ops.py dashboard-html --config .glue/linear-routing.yaml --seed .glue/linear-seed-tickets.yaml --output docs/linear-ops-dashboard.html
python3 <skill-root>/scripts/linear_ops.py draft-ticket --config .glue/linear-routing.yaml --domain product --type feature --title "Add a dashboard" --summary "Expose useful work status for review"
python3 <skill-root>/scripts/linear_ops.py ticket-url --config .glue/linear-routing.yaml --domain product --type feature --title "Add a dashboard" --summary "Expose useful work status for review"
python3 <skill-root>/scripts/linear_ops.py seed-urls --config .glue/linear-routing.yaml --seed .glue/linear-seed-tickets.yaml
```

The helper does not perform live Linear writes. It can perform live read-only
Linear API queries when `LINEAR_API_KEY` is already present in the shell. Use MCP
or a later guarded API path for live writes after auth is connected.
