# agent-skills

> A curated collection of **Agent Skills** — self-contained playbooks that teach AI coding
> agents how to handle specific tasks, from GitHub operations to Qt 6 and C++ profiling.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Each skill is a directory with a `SKILL.md` that an agent loads on demand, plus optional
`scripts/`, `references/`, and `assets/` to back it up. Skills are written to be precise,
opinionated, and grounded in real, validated workflows.

## Skills

First-party skills maintained in this repository:

| Skill | Category | Description |
|-------|----------|-------------|
| [ask](ask/SKILL.md) | Q&A | Answer technical questions and explain code, concepts, and architecture in strict read-only mode. Grounds answers in the actual codebase and recommends changes without ever applying them. |
| [easy-profiler-guide](easy-profiler-guide/SKILL.md) | C++ / Performance | End-to-end guide to the `easy_profiler` C++ library (v2.1.0): integrate the build, instrument with `EASY_*` macros, capture `.prof` files, and analyze them. Bundles stdlib-only Python scripts to summarize and diff captures. |
| [github](github/SKILL.md) | DevOps / GitHub | GitHub operations via the `gh` CLI and REST/GraphQL APIs: repositories, commits, branches, pull requests, issues, and GitHub Actions — with auth, security, and troubleshooting guidance. |
| [init-project-docs](init-project-docs/SKILL.md) | Documentation | One-time initialization of the standard project documentation set (`ARCH`, `CHANGELOG`, `DECISIONS`, `GLOSSARY`, `ISSUES`, `NOTES`, `RUNBOOK`, `TECH_DEBT`, `TOOLS`) in `docs/`, registered in the root `AGENTS.md`. |
| [qt-coding-guide](qt-coding-guide/SKILL.md) | Qt / QML | Modern Qt 6 and QML coding on Windows with MSBuild: strict MVVM, C++/QML integration, layouts and performance, and the `qmllint` / `qmlcachegen` / `moc` tooling pipeline. |

## Using a skill

Skills are designed to be loaded by an agent at the moment they become relevant:

- **Automatic** — an agent reads each skill's `description` and loads it when the task matches
  (for example, `qt-coding-guide` loads whenever Qt/QML code is written or reviewed).
- **Explicit** — invoke a skill directly with its name (e.g. `/ask how does this work?`).

Once loaded, follow the skill's `SKILL.md`. Skills that ship `scripts/` reference them by path
(`<skill-dir>/scripts/...`) so they run anywhere without installation.

> [!TIP]
> Skills are self-contained: copy any skill directory into your agent's skills folder to use it
> in another project.

## Repository layout

```text
agent-skills/
├── ask/                  # Read-only technical Q&A
├── easy-profiler-guide/  # easy_profiler C++ integration + analysis scripts
├── github/               # GitHub operations (gh CLI + API)
├── init-project-docs/    # Standard docs/ initialization
├── qt-coding-guide/      # Qt 6 / QML + MSBuild tooling
├── .agents/skills/       # Synced community skills (see skills-lock.json)
└── skills-lock.json      # Locked sources + hashes for synced skills
```

Most skills follow the same structure: a `SKILL.md` entry point, a `references/` directory for
deep-dive documentation, and a `scripts/` directory for helper tooling where useful.
