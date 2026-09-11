# Contributing

Thank you for helping improve the Veridian Labs Agent Skills collection.

## Before you start

Open an issue or discussion for a substantial new skill so its audience and scope can be agreed before implementation. Small corrections and narrowly scoped improvements can go directly through a pull request.

Every contribution must be safe to publish. Do not include:

- credentials, tokens, private keys, or environment files;
- customer, scholar, employee, or account-specific data;
- internal URLs, unpublished product plans, or private operational procedures;
- copied material whose license does not permit redistribution.

## Skill requirements

Each skill must live in `skills/<skill-name>/SKILL.md` and follow the [authoring guide](docs/skill-authoring.md). At minimum:

- the directory name and frontmatter `name` must match;
- `name` must use lowercase letters, numbers, and single hyphens;
- `description` must explain what the skill does and when it applies;
- instructions must be specific to the task and avoid generic agent advice;
- referenced files must use relative paths and exist in the skill directory;
- scripts must document dependencies and fail with actionable messages.

## Pull requests

Keep pull requests focused. Explain the user problem, the intended activation boundary, what was tested, and any compatibility or licensing considerations.

Before submitting:

```bash
npm run validate
```

Review the complete diff for accidental private material. A passing validator checks structure; it does not replace human review of the instructions, scripts, or security implications.

## Review standard

Maintainers review skills for:

1. clear scope and useful activation metadata;
2. correctness and evidence from a realistic task;
3. progressive disclosure and manageable context size;
4. portability across compatible agents;
5. safe handling of tools, files, credentials, and external side effects;
6. complete licensing and attribution.

Maintainers may request a narrower scope, additional examples, a public-safety redaction, or a separate skill when one contribution combines unrelated workflows.
