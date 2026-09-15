# Ticketing Policy

Use this policy to convert conversation into structured Linear work.

## Source Of Truth

- Linear owns backlog, queue, status, priority, assignment, and issue history.
- Project documentation owns durable memory: decisions, strategy, state
  summaries, and links to important Linear issues/projects.
- Do not copy the whole backlog into project documentation.

## Ticket Types

`feature`: New product/runtime behavior. Requires outcome, scope, acceptance
criteria, and likely affected repo.

`bug`: Existing behavior is wrong. Requires observed behavior, expected
behavior, reproduction/evidence, and verification path.

`chore`: Maintenance, cleanup, docs, dependency work, or non-user-visible
improvement. Requires why it matters and done condition.

`research`: Knowledge-gathering task. Requires question, sources/scope, and
expected output format.

`spike`: Bounded technical uncertainty. Requires timebox or stop condition and
decision/output.

`decision`: A choice a designated decision-maker must make. Requires options,
criteria, and the decision owner.

`ops`: Process, business, launch, sales, or infrastructure coordination.
Requires owner, desired operational outcome, and deadline if any.

## Priority Policy

`Urgent`: Production outage, active customer/business damage, deadline today, or
security issue. Ask before setting urgent unless the user explicitly says so.

`High`: Blocks current priority path, customer-facing launch, revenue work, or
another active implementation.

`Medium`: Valuable planned work with no immediate blocker.

`Low`: Cleanup, future option, or non-blocking polish.

`No priority`: Idea, parking lot, or unclear value.

## Status Policy

`Triage`: Needs classification, de-duplication, owner, or decision.

`Ready`: Clear enough to work, with acceptance criteria and no known blocker.

`In Progress`: Actively being worked now. Do not set just because a ticket was
created.

`Waiting for decision`: Needs a decision, credentials, business judgment, or
review. Use the workspace's configured status name when it differs.

`Blocked`: External dependency prevents progress and the blocker is named.

`Done`: Acceptance criteria verified. Ask before closing if status is uncertain.

`Canceled`: No longer relevant or explicitly dropped. Ask before canceling.

## Ticket Shape

Use this description structure unless a Linear template is already configured:

```markdown
## Outcome

## Context

## Scope

## Acceptance Criteria
- [ ]

## Tasks
- [ ]

## Links

## Open Questions
```

## Sub-Issues Versus Checklist

Use checklist tasks when one person/agent can complete the work in one coherent
pass. Use sub-issues when tasks have independent owners, repos, verification
paths, or can be scheduled separately.

## Approval Gates

Ask the user before:

- Creating more than five issues at once.
- Creating or modifying projects, workflows, labels, or workspace-level config.
- Marking anything `Urgent`.
- Closing/canceling another person's work.
- Making customer-facing commitments or public launch/release dates.
- Creating issues that expose private client or learner data.

## Duplicate Discipline

Search before creating. If duplicate confidence is high, update the existing
issue. If confidence is medium, show the candidate duplicate and ask. If live
Linear access is missing, mark duplicate check as pending in the draft.
