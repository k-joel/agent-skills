---
name: init-project-docs
description: One-time initialization of the standard project documentation set (ARCH, CHANGELOG, DECISIONS, GLOSSARY, ISSUES, NOTES, RUNBOOK, TECH_DEBT, TOOLS) in docs/, registered in the root AGENTS.md. Use when setting up or standardizing documentation for a new or existing project. Creates or refreshes each doc with its canonical header, adds the Project Docs entries to AGENTS.md, and drafts initial content following each doc's embedded maintenance guide. Single-use: every generated doc carries its own maintenance instructions, so later updates follow the doc itself and this skill is never invoked again.
---

# Initialize Project Documentation

Initialize the standard nine-document set in `docs/` at the project root and register it in the
root `AGENTS.md`. Each document embeds its own `<!-- MAINTENANCE GUIDE -->` comment — the
authoritative spec for how to create, update, and retire its content. This skill runs **once** per
project: after it completes, every future update follows the maintenance guide inside the affected
doc. Never invoke this skill again.

Run everything from the project root (the script writes to `./docs/` and `./AGENTS.md`). The
bundled script is Python 3, standard library only.

## The documentation set

| Flag | File | Purpose |
|---|---|---|
| `--arch` | `docs/ARCH.md` | Live, as-built architecture reference: topology, data flows, components. |
| `--changelog` | `docs/CHANGELOG.md` | Reverse-chronological record of notable user-visible changes (Keep a Changelog). |
| `--decisions` | `docs/DECISIONS.md` | Architecture decision records: why structural choices exist (`ADR-NNN` entries). |
| `--glossary` | `docs/GLOSSARY.md` | Canonical project vocabulary; rejected aliases under `_Avoid_`. |
| `--issues` | `docs/ISSUES.md` | Open bugs, defects, and gaps (`ISS-NNN` entries). |
| `--notes` | `docs/NOTES.md` | Verified gotchas, invariants, and operational quirks. |
| `--runbook` | `docs/RUNBOOK.md` | Repeatable operator procedures (`RUN-NNN` entries). |
| `--tech-debt` | `docs/TECH_DEBT.md` | Verified technical debt ledger (`DEBT-YYYY-NNN` entries). |
| `--tools` | `docs/TOOLS.md` | Inventory of standalone helper scripts in `tools/`. |

The same run also registers the processed docs in the root `AGENTS.md` (step 4).

## Workflow

### 1. Inventory existing docs

Run from the project root, where `<skill-dir>` is the directory containing this SKILL.md:

```bash
python "<skill-dir>/scripts/create_docs.py" --list
```

This prints every standard doc that already exists in `docs/`, with its line count.

### 2. Choose scope with the user

- If `--list` returned matches, ask which file headers to overwrite; accept `all` for everything.
- If no standard docs exist yet, ask which docs to initialize (default: all nine).
- Exclude every doc the user does not want touched.

### 3. Write headers

For each selected doc:

- **Existing file**: read the file and find `N`, the line where the old header ends and the content
  begins. The old header is the H1 title, the preamble, the `<!-- MAINTENANCE GUIDE -->` comment, the
  `---` separator, and the old empty-state scaffold. `N` is the last line of that block — the script
  replaces lines 1..`N` and preserves everything from `N+1`. Never include content lines in `N`; they
  would be deleted.
- **New file**: pass no line number; the script creates `docs/<FILE>.md` with the stored header.

### 4. Register the docs in AGENTS.md

1. Search for an `AGENTS.md` in the project root.
2. If it exists, search it for a documentation section — a heading such as `## Project Docs`,
   `## Docs`, `## Documentation`, or similar.
   - If a docs section exists, note `BEGIN:END`, the line range of that section (heading line
     through its last entry). The script replaces exactly those lines.
   - If no docs section exists, find an appropriate place for it (for example after the project
     overview or near other reference material) and note the insertion line.
3. If `AGENTS.md` does not exist, pass `--agents -1`; the script creates a skeleton `AGENTS.md`
   with the Project Docs section already filled out.
4. Pass `--agents BEGIN:END` in the **same call** as the doc flags from step 3. The script writes
   the Project Docs section (heading + intro line + entries) for every doc flagged in that call and
   **skips entries for docs that were not flagged** — no `--issues` flag means no `ISSUES.md` entry.
   To insert the section without deleting any lines, pass a zero-width range: `--agents 40:39`
   inserts before line 40.

Batch everything into one call, for example:

```bash
python "<skill-dir>/scripts/create_docs.py" --issues 86 --notes 65 --arch --agents 30:45
```

The stored header is the boilerplate (H1 + preamble + maintenance guide comment + `---`) plus the
doc's empty-state scaffold, so a fresh file is valid per its own guide immediately. The script
refuses to touch an existing file without a line number, refuses `-1` when `AGENTS.md` already
exists, and refuses a range when `AGENTS.md` does not exist.

### 5. Draft and rewrite content

After the headers are in place, make each doc conform to the `EXAMPLE LAYOUT` and
`STRUCTURE & FORMATTING` rules in **its own** maintenance guide — the guide inside each doc is
authoritative.

- **New docs**: draft initial content from the actual codebase. Inspect source, config, and git
  history before writing; never invent facts. Keep the empty-state scaffold wherever nothing
  qualifies (for example, leave `## Open` empty in ISSUES.md and `_No tools registered._` in
  TOOLS.md).
- **Existing docs**: rewrite the preserved content into the conforming layout. **Preserve entry IDs —
  `ADR-NNN`, `ISS-NNN`, `RUN-NNN`, and `DEBT-YYYY-NNN` are permanent and never renumbered — plus
  facts, dates, and evidence.** Restructure only the format (for example, an ad-hoc bug list becomes
  `### ISS-NNN` entries with Symptom / Where flagged / Cause / Suggested fix).
- Fill placeholders: set the GLOSSARY H1 and overview sentence for *this* project, the TECH_DEBT
  `**Last Updated:**` date and `**Stacks:**` value, and CHANGELOG reference links when the
  repository URL is known.
- Complete the AGENTS.md skeleton if one was created: fill the overview placeholder and add the
  project's conventions and workflows.

### 6. Verify

Check each doc against its guide's hard rules before finishing, for example:

- ISSUES.md keeps `## Open` present at all times and has no `## Closed` or `## Resolved` section.
- DECISIONS.md and RUNBOOK.md keep a single H1 and a maintained `## Entries` index table with
  working anchors.
- TECH_DEBT.md keeps its four `##` sections in order, with Summary counts matching the ledger.
- TOOLS.md lists entries strictly alphabetically using the `` **`<file>`** — summary `` format.
- CHANGELOG.md groups bullets under the six `###` categories, omitting empty ones.
- AGENTS.md lists exactly the processed docs under the Project Docs section and its other content
  is untouched.

## Script reference

```bash
python "<skill-dir>/scripts/create_docs.py" --list
```

Lists the standard docs that already exist in `docs/`, one per line, with line counts. Cannot be
combined with other flags.

```bash
python "<skill-dir>/scripts/create_docs.py" --<name> [N] ...
```

For each doc flag (repeatable, combinable in one invocation):

- If `docs/<FILE>.md` does not exist: create it with the stored header. A passed `N` is ignored with
  a note.
- If it exists: replace its first `N` lines with the stored header and keep the rest.
  `N` = the last line of the old header, e.g. `--issues 20` replaces the first 20 lines.

```bash
python "<skill-dir>/scripts/create_docs.py" --agents BEGIN:END|--agents -1 ...
```

Registers the docs flagged in the same invocation in the root `AGENTS.md`:

- `--agents BEGIN:END`: replace lines `BEGIN`..`END` of AGENTS.md with the Project Docs section
  (`## Project Docs`, the intro line, and one entry per flagged doc). Entries for unflagged docs are
  excluded. A zero-width range (`40:39`) inserts the section before line 40 without deleting.
- `--agents -1`: create a skeleton AGENTS.md with the Project Docs section already filled out
  (refused if AGENTS.md already exists).

Errors (non-zero exit): an existing file without `N`; `N` out of range; `--list` combined with other
flags; no document selected; malformed or out-of-range `--agents` range. Existing files keep their
line-ending style (CRLF stays CRLF).

**Single-use skill.** After this run the docs maintain themselves: every update follows the
maintenance guide embedded in the affected doc. Do not invoke this skill again.
