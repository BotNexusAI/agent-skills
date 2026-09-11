# Skill authoring guide

This repository follows the open Agent Skills format. A skill is a directory with a required `SKILL.md` and optional supporting resources.

## Minimal structure

```text
skills/<skill-name>/
└── SKILL.md
```

The frontmatter must include:

```yaml
---
name: example-skill
description: Explain what the skill does and when an agent should use it.
---
```

The `name` must be 1–64 characters, use lowercase letters, numbers, and hyphens, contain no consecutive hyphens, and match the parent directory. The `description` must be non-empty and no longer than 1024 characters. Include concrete trigger language, but do not turn the description into a complete manual.

Optional frontmatter fields include `license`, `compatibility`, `metadata`, and the experimental `allowed-tools` field. Use them only when they communicate a real constraint or useful attribution.

## Writing the body

The body is loaded when the skill activates. Include the decisions and workflow details that materially improve the agent's work:

- state the outcome the skill is responsible for;
- identify the relevant inputs and constraints;
- describe the preferred workflow and important decision points;
- define safety, authorization, or stopping boundaries where needed;
- include realistic examples or edge cases when they change behavior;
- link to supporting files using paths relative to the skill root.

Keep the entrypoint concise. Move detailed schemas, provider-specific instructions, and long examples into focused files under `references/`. Put repeatable deterministic logic under `scripts/` and templates or static files under `assets/`.

## Progressive disclosure

Use three layers:

1. frontmatter for discovery;
2. `SKILL.md` for the common workflow;
3. references, scripts, and assets only when the active task needs them.

Keep references close to the skill and avoid deep chains of linked documents. A future maintainer should be able to understand the skill's behavior by starting at its `SKILL.md`.

## Validation and testing

Run the repository validator:

```bash
npm run validate
```

Then test the skill with at least one realistic request and inspect the actual result. Check that the skill activates for its intended request, remains quiet for nearby unrelated requests, follows its safety boundaries, and can find every referenced file.

The validator checks repository structure and frontmatter conventions. It cannot determine whether the workflow is correct, safe, or genuinely useful; those require review.

## Public-release checklist

Before merging a skill, confirm:

- no secrets or private data are present;
- all bundled files are intended for public distribution;
- licenses and attributions are complete;
- scripts do not silently perform consequential external actions;
- external writes, account access, and spending have explicit boundaries;
- the README or skill page explains installation and intended use;
- a realistic task has been run and the result reviewed.
