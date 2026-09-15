# Linear Docs Reference

Official docs relevant to the Linear operating layer.

## Core Model

- Concepts: https://linear.app/docs/conceptual-model
- Issues are the basic task object. Each issue belongs to one team and has a
  title and status; other properties such as priority, estimate, label, due date,
  assignee, project, relations, and sub-issues are optional.
- Projects group issues toward time-bound deliverables. Cycles are sprint-like
  repeating work periods. Views are dynamic filtered issue lists.
- Triage is an optional intake status. Backlog is a status category. Workflows
  are team-specific ordered statuses.

## MCP

- MCP server: https://linear.app/docs/mcp
- Remote MCP URL: `https://mcp.linear.app/mcp`
- Codex setup from Linear docs:
  `codex mcp add linear --url https://mcp.linear.app/mcp`
- Linear says its MCP server supports finding, creating, and updating Linear
  objects such as issues, projects, and comments.

## API

- GraphQL getting started: https://linear.app/developers/graphql
- Filtering: https://linear.app/developers/filtering
- Endpoint: `https://api.linear.app/graphql`
- Use OAuth for apps used by others. Personal API keys are acceptable for
  personal scripts.
- Always check the GraphQL `errors` array; HTTP 200 can still contain partial
  GraphQL failures.
- Most paginated results can be filtered. Linear supports comparators such as
  `eq`, `neq`, `in`, `nin`, `contains`, `containsIgnoreCase`, `lt`, `lte`,
  `gt`, and `gte`, plus relationship filters such as `labels: { name: ... }`
  and `state: { type: ... }`.
- Linear recommends the TypeScript SDK when building custom integrations.
- Apollo schema explorer: https://studio.apollographql.com/public/Linear-API/

## Issue Creation And Editing

- Creating issues: https://linear.app/docs/creating-issues
- Issues can be created through UI, `linear.new`, email, GraphQL API, and
  integrations.
- Linear pre-filled URLs support fields such as title, description, status,
  team, priority, assignee, estimate, labels, project, milestone, links, and
  template.
- Editor: https://linear.app/docs/editor
- Linear supports most Markdown elements in issue descriptions and documents.

## Labels, Priority, Relations

- Labels: https://linear.app/docs/labels
- Labels can be team-level or workspace-level. Label descriptions help keep
  usage consistent. Linear reserves names such as assignee, cycle, estimate,
  priority, project, state, and status.
- Priority: https://linear.app/docs/priority
- Supported priorities: No priority, Low, Medium, High, Urgent. Linear does not
  support custom priority levels; use labels or statuses for extra nuance.
- Issue relations: https://linear.app/docs/issue-relations
- Relations include blocked, blocking, related, and duplicate.
- Parent/sub-issues: https://linear.app/docs/parent-and-sub-issues
- Sub-issues inherit parent team, priority, and project. Labels are not
  inherited.

## Collaboration And Hosting

- Linear is a hosted SaaS product; teams do not need to host Linear to
  collaborate with team members.
- Team members collaborate by joining the Linear workspace, receiving access to
  relevant teams/projects, and using comments, mentions, assignments, project
  updates, and views.
- If self-hosting or data-residency control becomes mandatory, evaluate Plane as
  the project-management fallback rather than trying to self-host Linear.
