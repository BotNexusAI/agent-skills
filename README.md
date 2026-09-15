# Veridian Labs Agent Skills

Reusable skills for AI agents, published by the team behind [BotNexus.ai](https://botnexus.ai).

BotNexus.ai is Veridian Labs' agentic framework, operating system, and SaaS offering for building, running, and governing useful AI agents. This repository shares selected skills we created for our own work so that other builders can inspect, adapt, and use them in their own agent workflows.

The collection is designed for the open [Agent Skills](https://agentskills.io/) format and works with compatible tools including Codex, Claude Code, Cursor, and other agents supported by the [`skills`](https://github.com/vercel-labs/skills) CLI.

## Install

List the skills currently available in this repository:

```bash
npx skills add BotNexusAI/agent-skills --list
```

Install one skill into the current project:

```bash
npx skills add BotNexusAI/agent-skills --skill <skill-name>
```

Install one skill globally:

```bash
npx skills add BotNexusAI/agent-skills --skill <skill-name> --global
```

For the Linear workflow specifically:

```bash
npx skills add BotNexusAI/agent-skills --skill linear-ops
```

Individual skills are also discoverable through [skills.sh](https://skills.sh/BotNexusAI/agent-skills) after they are published and used.

## Repository layout

Each published skill is self-contained under `skills/`:

```text
skills/
└── <skill-name>/
    ├── SKILL.md       # Required metadata and instructions
    ├── references/    # Optional detailed guidance
    ├── scripts/       # Optional executable helpers
    └── assets/        # Optional templates and static resources
```

The repository itself contains the shared authoring, contribution, and validation conventions. Skill-specific instructions stay inside the relevant skill directory.

## Principles

- Share practical workflows that have been used and reviewed in real work.
- Keep each skill focused, portable, and useful outside Veridian Labs.
- Make activation descriptions precise enough to avoid unrelated matches.
- Put detailed material in references and keep the main `SKILL.md` easy to load.
- Never include credentials, private customer information, account-specific data, or internal-only operating instructions.
- Treat bundled scripts and referenced files as part of the skill's public supply-chain surface.

## Status

The repository is being bootstrapped. Skills will be added selectively after review for usefulness, portability, licensing, security, and public disclosure.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. The authoring conventions are documented in [docs/skill-authoring.md](docs/skill-authoring.md).

## License

Unless a skill directory states otherwise, repository material is released under the [MIT License](LICENSE). Individual skills may include their own license terms; review the skill directory before redistributing it.

## About Veridian Labs

[Veridian Labs](https://veridianlabs.co) builds agent-native products and infrastructure. [BotNexus.ai](https://botnexus.ai) is its agentic framework, operating system, and SaaS offering for turning specialized knowledge and workflows into governed, reusable agent capabilities.
