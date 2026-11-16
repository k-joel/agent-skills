#!/usr/bin/env python3
# Create or refresh the standard project docs in docs/ with their canonical headers,
# and register them in the root AGENTS.md.
#
# Each stored header is the doc's canonical boilerplate (H1 + preamble + embedded
# MAINTENANCE GUIDE comment + "---") plus its empty-state scaffold, so a fresh file
# is valid per its own guide immediately. The AGENTS.md Project Docs entries are the
# canonical entries for each doc. Docs are written under ./docs relative to the
# current working directory (run from the project root).

import argparse
import sys
from pathlib import Path

_ABSENT = object()
HEADER_ARCH = r"""# Architecture

This is the live, as-built architecture reference. It describes the code as it
exists today, not planned or historical designs. When this document and the code
disagree, the code wins — update this document in the same change. Canonical
terms live in [`GLOSSARY.md`](GLOSSARY.md), rationale in
[`DECISIONS.md`](DECISIONS.md), open defects in [`ISSUES.md`](ISSUES.md),
structural debt in [`ARCH_ISSUES.md`](ARCH_ISSUES.md), and operational gotchas
in [`NOTES.md`](NOTES.md).

<!--
ARCH.md MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Audience: Engineers and LLM agents needing an accurate map of the codebase.
- Purpose: Authoritative as-built reference of system structure, boundaries,
  runtime topology, data/control flows, schemas, contracts, cross-cutting
  mechanisms, extension points, deployment, and test/quality gates.
- Code-First Rule: Derive every claim directly from source, config, build, and
  CI files (package manifests, entry points, schemas, routes, tests). Never
  document theoretical patterns or unimplemented plans.

UPDATE TRIGGERS
Update docs/ARCH.md whenever a change alters any of the following:
- Process/runtime topology, concurrency model, or lifecycle ownership.
- External API, CLI, RPC, or MCP tool surface and payload contracts.
- Configuration sources, discovery precedence, or environment overrides.
- Database schemas, migrations, identity/invalidation keys, or vector/cache layouts.
- Core data, ingestion, or query/read-path pipelines.
- Cross-cutting boundaries (auth, error handling, logging, security, OS behavior).
- Plugin/extension contracts, deployment/install layout, or test/CI quality gates.
- Any spotted mismatch between this file and actual code.

INCLUSION / EXCLUSION CRITERIA
- INCLUDE:
  - Verified stack, architectural style/hybrids, and explicit In-Scope vs.
    Out-of-Scope boundaries.
  - Runtime topology, process/thread ownership, and dependency direction rules.
  - Component inventory, internal abstractions, interaction protocols, and
    concrete extension mechanisms.
  - Data architecture: domain entities, relationships, actual DDL/schemas,
    consistency/caching/invalidation rules, and filesystem layout.
  - Cross-cutting implementation patterns (auth/secrets, error/retry/fallback,
    logging/observability, input validation, config precedence).
  - Deployment/install topology and test layers + runnable quality-gate commands.
- EXCLUDE (ROUTE ELSEWHERE OR OMIT):
  - Why a choice was made / alternatives considered -> DECISIONS.md
  - Functional bugs or regressions -> ISSUES.md
  - Structural debt, layer violations, or smells -> ARCH_ISSUES.md
  - Operational quirks or debugging tips -> NOTES.md
  - Standalone term definitions -> GLOSSARY.md
  - Speculative roadmaps, exhaustive line-by-line code dumps, or boilerplate
    sections for technology stacks not detected in the codebase.

STRUCTURE & FORMATTING
- Top-level sections: Numbered H2 headings (`1. Purpose and scope` .. `13. ...`)
  separated by `---` horizontal rules on their own lines.
- Subsections: Numbered H3 headings (`2.1 ...`, `6.1 ...`). Omit unused optional
  subsections; never leave empty "TBD" sections.
- Canonical section order (adapt domain-specific titles to the codebase):
  1. Purpose and scope
  2. Runtime topology
  3. Primary write / ingestion data flow
  4. Primary read / query paths
  5. Domain model
  6. Data architecture
  7. Component design
  8. External interface / API contracts
  9. Cross-cutting concerns
  10. Extension points
  11. Install and launch architecture
  12. Testing architecture
  13. Maintaining this document
- Tables: Use compact Markdown tables for inventories, configs, and schemas.
- Diagrams: Use fenced ASCII diagrams with Unicode arrows (`→`, `──►`, `▼`).
  Never use `-->` inside HTML comments or diagrams that could break parsers.
- Code blocks: Always specify a language tag (`sql`, `json`, `bash`, `text`).

QUALITY & STYLE RULES
- Tense & Tone: Present tense, declarative, terse, and high-signal. No filler.
- Verification: Inspect actual files before writing; cite exact module paths,
  symbol names, config keys, and CLI commands in backticks.
- Consistency: Match canonical vocabulary in GLOSSARY.md and link ADRs inline
  (e.g., `(ADR-005)` or `[ADR-015](DECISIONS.md#...)`) without duplicating rationale.
- Privacy/Safety: Never embed real secrets, tokens, or personal local paths in
  examples; use placeholders (`<workspace>`, `~/.app/`).

LIFECYCLE & WORKFLOW
1. Inspect diff/codebase: Detect active stack, entry points, schemas, and configs.
2. Add: Insert new components/endpoints/tables into the matching numbered section.
3. Modify: Update flows, config tables, and schemas in place to match the code.
4. Retire: Delete removed components, flags, and endpoints from ARCH.md (history
   belongs in git and DECISIONS.md, not stale sections here).
5. Reconcile: If an existing section contradicts the code, fix ARCH.md immediately.

ANTI-PATTERNS
- Documenting planned features, aspirational clean layers, or unverified memory.
- Mixing ADRs, bug lists, or tech-debt commentary into ARCH.md.
- Leaving stale DDL, obsolete CLI flags, or dead module names after refactors.
- Including framework sections (e.g., React/Java/.NET) not present in the repo.
- Using vague qualifiers ("probably", "usually", "various helpers").

EXAMPLE LAYOUT (4-SPACE INDENTED)

    ---

    ## 1. Purpose and scope

    | In scope | Out of scope |
    |---|---|
    | `<core capability>` | `<explicit boundary>` |

    ---

    ## 2. Runtime topology

    ### 2.1 Default mode (`mode: <name>`)

    ```text
    caller ──► <entry-point> ──► <worker/store>
    ```

    | Process / thread | Role | Owns |
    |---|---|---|
    | `<process>` | `<role>` | `<resources>` |

    ---

    ## 3. <Write / ingestion> data flow

    ```text
    input event → filter/debounce → bounded queue → <unit_of_work>() → store
    ```

    ### 3.1 Reconciliation backstops

    1. **Startup reconcile** — `<initial catch-up behavior>`.

    ---

    ## 4. <Read / query> paths

    ### 4.1 <Query path name>

    1. `<Step 1: parse/validate>`
    2. `<Step 2: query store and rank/merge>`

    ---

    ## 5. Domain model

    | Entity | Identity | Key attributes |
    |---|---|---|
    | **<Entity>** | `<unique key>` | `<core fields>` |

    Relationships: `<EntityA> 1—* <EntityB>`.

    ---

    ## 6. Data architecture

    ### 6.1 Primary store (`<path-or-engine>`)

    ```sql
    CREATE TABLE <entity> (id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE);
    ```

    ### 6.2 Secondary / index store

    - `<Engine>`: `<key structure, consistency, and identity binding rules>`.

    ### 6.3 Filesystem layout

    ```text
    <root>/
      <data-dir>/
        <db-file>
        log/<role>.log
    ```

    ---

    ## 7. Component design

    | Module | Responsibility |
    |---|---|
    | `src/<pkg>/<mod>.py` | `<single-sentence role>` |

    ### 7.1 Configuration

    | Config key | Environment | Default |
    |---|---|---|
    | `<section.key>` | `<ENV_VAR>` | `<default>` |

    ---

    ## 8. <Interface / API> surface

    ### 8.1 `<operation_name>`

    | Input | Type | Default | Notes |
    |---|---|---|---|
    | `<param>` | string | required | `<constraint>` |

    ```json
    {"status": "ok", "results": []}
    ```

    ---

    ## 9. Cross-cutting concerns

    ### 9.1 Error handling
    `<Exception hierarchy and fail-soft vs. fatal boundaries.>`

    ### 9.2 Concurrency and consistency
    `<Locks, leases, read-only isolation, and ordering guarantees.>`

    ### 9.3 Logging and observability
    `<Log destinations, levels, redaction rules, and status signals.>`

    ### 9.4 Security boundaries
    `<Auth tokens, file permissions, and non-sandbox boundaries.>`

    ### 9.5 Platform behavior
    `<OS-specific watchers, locks, sockets/pipes, or process flags.>`

    ---

    ## 10. Extension points

    | Extension | Mechanism | Rules |
    |---|---|---|
    | `<plugin type>` | `<discovery path>` | `<override/validation rules>` |

    ---

    ## 11. Install and launch architecture

    ```text
    source ──<installer>──► runtime copy ──► <launcher> ──► entrypoint
    ```

    ---

    ## 12. Testing architecture

    ### 12.1 Test isolation
    `<Env overrides and fixtures isolating tests from user/global state.>`

    ### 12.2 Test layers

    | Layer | What it covers |
    |---|---|
    | Unit | `<isolated modules>` |
    | Integration | `<end-to-end flows with real/stubbed boundaries>` |

    ### 12.3 Quality gates

    ```bash
    <lint / typecheck / test commands>
    ```

    ---

    ## 13. Maintaining this document

    Update triggers and companion-doc split (`ARCH.md`, `DECISIONS.md`,
    `ISSUES.md`, `ARCH_ISSUES.md`, `NOTES.md`, `GLOSSARY.md`).
-->

---

"""
HEADER_CHANGELOG = r"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
CHANGELOG.md MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Curated, reverse-chronological record of notable, user-visible changes per version.
- Audience: human end users, operators, and developers evaluating upgrades or diagnosing
  regressions—not a git commit dump or internal engineering diary.
- Portable source of truth: reuse release sections from this file for GitHub Releases.

UPDATE TRIGGERS
- Update `## [Unreleased]` in the same task/session whenever you add a user-visible feature,
  change existing behavior/API/CLI/config/defaults, deprecate or remove functionality, fix a
  user-facing bug, or patch a security vulnerability.
- Update on release: promote `## [Unreleased]` to a versioned section and open a new
  `## [Unreleased]` section above it.
- Update post-release only to mark a pulled release `[YANKED]`, record a missed release or
  breaking change, or fix typos/broken links.
- Before ending a session that altered user-facing behavior, verify `## [Unreleased]`
  captures every qualifying change.

INCLUSION / EXCLUSION CRITERIA
- Include: Every notable user-visible change (features, behavior changes, deprecations,
  removals, bug fixes, security fixes). Consistency is mandatory—an incomplete changelog
  misleads users relying on it as the source of truth.
- Exclude: Whitespace/formatting edits, pure internal refactors with no behavior change, merge
  commits, work-in-progress steps, routine CI tweaks, and raw `git log` entries.

STRUCTURE & FORMATTING
- Section order: `## [Unreleased]` at the top, followed by releases newest-first
  (`## [X.Y.Z] - YYYY-MM-DD`). Never skip a released version.
- Dates & Versions: Strict ISO 8601 dates (`YYYY-MM-DD`) and SemVer (`MAJOR.MINOR.PATCH`:
  breaking / backward-compatible feature / backward-compatible fix). Append `[YANKED]` to
  pulled releases (`## [X.Y.Z] - YYYY-MM-DD [YANKED]`).
- Categories: Under `## [Unreleased]` and each release, group bullets strictly under these
  six `###` headings in order, omitting any empty category:
    - `Added`      (new features)
    - `Changed`    (changes to existing functionality)
    - `Deprecated` (soon-to-be-removed features)
    - `Removed`    (now-removed features)
    - `Fixed`      (bug fixes)
    - `Security`   (vulnerability fixes and security-relevant changes)
- Reference links: Keep reference-style links at the bottom of the file so every heading
  links to its comparison diff or tag (`[unreleased]` -> `vLATEST...HEAD`, `[X.Y.Z]` ->
  `vPREV...vX.Y.Z`, initial `[X.Y.Z]` -> `releases/tag/vX.Y.Z`).

QUALITY & STYLE RULES
- Describe user-visible impact, not internal implementation; name the specific feature,
  endpoint, flag, setting, or behavior affected.
- Keep bullets concise (1-2 lines), match audience tone, maintain consistent tense across
  entries, and end every bullet with a period.
- Evidence rule: Document only changes actually implemented and verified in the code/diff;
  never record speculative, planned, or unverified work.
- Link to the relevant issue, PR, commit, or ADR where helpful (and credit contributors if
  appropriate).
- Good: `- Login timeout on mobile caused by premature token expiry. ([#456](https://github.com/org/repo/issues/456))`
- Bad:  `- Refactored session handler.` or `- Various bug fixes and improvements.`

LIFECYCLE & WORKFLOW
- Ongoing edits: Add entries to `## [Unreleased]` as changes land, not only at release time.
- Deprecations & Breaking Changes: Deprecate in an earlier release before removing so users
  have a safe upgrade path. Prefix breaking changes and removals with `**BREAKING:**`, state
  the replacement, migration path, and deadline, and pair with a `MAJOR` version bump.
- Release-day workflow:
  1. Confirm `## [Unreleased]` captures all notable changes since the last release.
  2. Choose next `X.Y.Z` per SemVer.
  3. Rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`.
  4. Insert a fresh empty `## [Unreleased]` section directly above it.
  5. Update bottom reference links (`[unreleased]` -> `vX.Y.Z...HEAD`; add `[X.Y.Z]`).
  6. Review wording, `**BREAKING:**` prominence, and links before tagging.
- Yanks & Corrections: Never silently delete a pulled release—keep it and append `[YANKED]`.
  Only rewrite past releases to add missed releases/breaking changes, fix typos, or repair
  broken links; never erase history.

ANTI-PATTERNS
- Dumping `git log` / raw commit messages or vague bullets ("bug fixes", "improvements").
- Ambiguous regional dates (`03/04/26`), empty `###` headings, skipped versions, or mixed
  formatting/tenses across releases.
- Silent breaking changes/removals without deprecation notice or migration instructions.
- Silently deleting yanked releases or selectively omitting notable changes.

EXAMPLE LAYOUT (4-SPACE INDENTED)

    ## [Unreleased]

    ### Added

    - User profile export in JSON format via `/v2/export`. ([#489](https://github.com/org/repo/pull/489))

    ## [2.0.0] - 2026-03-15

    ### Removed

    - **BREAKING:** Legacy `/v1/export` endpoint. Migrate to `/v2/export`.

    ### Fixed

    - Login timeout on mobile devices during token refresh. ([#456](https://github.com/org/repo/issues/456))

    ## [1.0.1] - 2026-02-01 [YANKED]

    ### Security

    - Patched token validation bypass in OAuth callback.

    [unreleased]: https://github.com/org/repo/compare/v2.0.0...HEAD
    [2.0.0]: https://github.com/org/repo/compare/v1.0.1...v2.0.0
    [1.0.1]: https://github.com/org/repo/compare/v1.0.0...v1.0.1
    [1.0.0]: https://github.com/org/repo/releases/tag/v1.0.0
-->

---

## [Unreleased]

"""
HEADER_DECISIONS = r"""# Architecture Decision Records

Concise record of architecturally significant choices made in this project—capturing the context, decision, and trade-offs behind non-obvious structure and dependencies. Read the relevant entry before modifying or reverting established behavior.

<!--
DECISIONS.md MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Canonical, single-file log of architecturally significant decisions for future
  engineers and autonomous agents.
- Explains *why* structural, dependency, and cross-cutting design choices exist.
- NOT a changelog, task/issue tracker, release note, API doc, or how-to guide.

UPDATE TRIGGERS
Update `docs/DECISIONS.md` before ending a session or finalizing a change whenever you:
- Introduce, swap, or retire a technology, framework, protocol, or design pattern.
- Make a structural choice that constrains multiple modules or is costly to reverse.
- Accept or reject a `Proposed` ADR.
- Supersede or deprecate an existing ADR (update BOTH the new and old entries,
  plus the summary index table).
Draft entries before or alongside implementation—never leave decisions undocumented.

INCLUSION / EXCLUSION CRITERIA
INCLUDE:
- Framework, library, or runtime adoption/removal.
- Data storage, schema paradigm, caching, or state-management architecture.
- Public API, IPC, or integration contracts and concurrency/deployment models.
- Security, authentication, or boundary rules and non-obvious constraints.

EXCLUDE:
- Routine bug fixes, patch/minor version bumps, or dependency hygiene.
- Local implementation details, variable naming, or behavior-preserving refactors.
- Trivial config/lint tweaks, temporary workarounds, or unmade hypotheticals.

STRUCTURE & FORMATTING
- Single H1: Keep `# Architecture Decision Records` as the only H1 in the file
  (per MADR / markdownlint MD025).
- Summary Index Table: Maintain `| ADR | Decision |` under `## Entries`
  in ascending numeric order. Every row must link to its section anchor
  (`[NNN](#adr-nnn-kebab-case-title)`).
- Numbering: Use 3-digit zero-padded IDs (`ADR-001`, `ADR-002`, ...; expand to
  4 digits only past `999`). IDs are permanent; never reuse or renumber them.
- Entry Heading: `## ADR-NNN: <Short Descriptive Title>` (H2 so file keeps one H1).
- Required Metadata (immediately below the entry heading):
    **Status**: Proposed | Accepted | Rejected | Deprecated | Superseded by ADR-NNN
    **Date**: YYYY-MM-DD  (ISO 8601 date of creation or last status update)
    **Deciders**: <@handles, team/role, or agent/session identifier>
- Required Subsections (exact names and H3 level, in order):
    ### Context
    ### Decision
    ### Consequences
- Required Consequences Fields:
    **Good**: <Positive outcomes.>
    **Bad**: <Real trade-offs, costs, or limitations.>
    **Mitigations**: <Guardrails or follow-up actions; omit ONLY if none apply.>
- Never omit `### Context`, `### Decision`, `### Consequences`, `**Good**:`, or
  `**Bad**:`. Keep entries in ascending numeric order (`ADR-001` .. `ADR-NNN`).

QUALITY & STYLE RULES
- Tense & Tone: Neutral, factual, concise (~15-25 lines per entry). Use past
  tense for `Context` ("Faced..."), present/imperative for `Decision` ("Use...").
- Honesty: Document genuine downsides in `**Bad**:`; no choice is cost-free.
- Verifiability: Ground claims in concrete constraints, observed measurements,
  or repo-relative paths and ADR IDs (`ADR-NNN`). Avoid vague adjectives
  ("faster", "cleaner", "better") without specifics.
- Cross-Links: Reference related decisions inline as `ADR-NNN` (e.g., `see ADR-002`).

LIFECYCLE & WORKFLOW
- Add: Append the new entry at the end of the file with the next `ADR-NNN` and
  add its matching row to the summary index table.
- Promote / Reject: Transition `**Status**` (`Proposed` -> `Accepted` or
  `Rejected`) and update `**Date**`. Keep `Rejected` entries so dead ends are
  not retried.
- Clarify: Only typo or wording fixes that preserve meaning are allowed on an
  `Accepted` entry. Never silently change the substance of an `Accepted` ADR.
- Supersede / Deprecate (Preserve History): Never delete old entries. To replace
  an `Accepted` decision, append a new `ADR-MMM` citing `ADR-NNN`, then update
  the old entry's `**Status**` to `Superseded by ADR-MMM` (or `Deprecated` if
  retired without replacement) and update its `**Date**`.

ANTI-PATTERNS
- Editing an `Accepted` ADR to say the opposite instead of writing a new ADR.
- Deleting `Deprecated`, `Rejected`, or `Superseded` entries, or renumbering IDs.
- Adding extra H1 (`#`) headings, skipping metadata fields, or forgetting to
  update the top summary index table / anchor links.
- Writing `**Bad**: None.` or omitting trade-offs.
- Recording implementation steps, file diffs, or routine bug fixes as ADRs.

EXAMPLE LAYOUT (4-SPACE INDENTED)

    ## Entries

    | ADR | Decision |
    |---|---|
    | [001](#adr-001-short-descriptive-title) | Short descriptive title |

    ---

    ## ADR-001: Short Descriptive Title

    **Status**: Accepted
    **Date**: YYYY-MM-DD
    **Deciders**: @handle, Core Team

    ### Context

    <2-4 sentences describing the problem, technical constraints, and forces
    requiring a decision. Cite affected components or prior ADRs if relevant.>

    ### Decision

    <1-3 sentences stating the exact choice made and any firm boundaries.>

    ### Consequences

    **Good**: <Concrete benefits and enabled capabilities.>

    **Bad**: <Accepted costs, complexity, or limitations.>

    **Mitigations**: <Steps or controls reducing the bad consequences.>

-->

---

## Entries

| ADR | Decision |
|---|---|

"""
HEADER_GLOSSARY = r"""# Glossary

A searchable index of a code workspace so an assistant can find symbols and code without reading whole files.

<!--
GLOSSARY.md MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Canonical ubiquitous-language reference for this repository/context, written for developers and AI agents.
- Not a user guide, API reference, changelog, or general software engineering dictionary.
- If GLOSSARY-MAP.md exists at the repo root, keep this file strictly scoped to this context; otherwise, this is the single repo glossary.

UPDATE TRIGGERS
Update this file in the same task/PR before concluding whenever you:
- Introduce a new project-specific concept, architecture role, tool, or config artifact.
- Rename, split, merge, or redefine an existing canonical term.
- Retire a component or alias that could still cause naming confusion.
- Resolve terminology ambiguity across code, tests, or docs.

INCLUSION / EXCLUSION CRITERIA
- Include: Project-specific domain/system concepts, canonical names chosen over competing synonyms, and named tools/components with distinct conceptual roles.
- Exclude: General programming concepts (timeouts, error types, utility patterns, standard protocols), transient local variables, and step-by-step implementation details.
- Litmus test: "Is this unique to this project's context, or general programming vocabulary?" Only the former belongs.

STRUCTURE & FORMATTING
- Top of file: H1 context title followed by a 1–2 sentence overview paragraph.
- Sections: Start with `## Language`. Add `## <Cluster>` H2 sections only when 3+ related terms form a natural group. Omit empty sections; do not use H3+ headings.
- Ordering & IDs: Group logically within sections; do not add numbering, dates, status tags, or custom IDs.
- Entry syntax (separate entries with one blank line; no bullets or nested lists):
  - Line 1: `**Canonical Term**:` (optional plain `(qualifier)` before `:`). Use sentence-style casing for prose concepts; preserve exact casing for literal tool/command names (e.g., `**tool_name**:`).
  - Line 2+: 1–2 sentence definition.
  - Final line: `_Avoid_: synonym1, synonym2` (append `(in prose)` or `(retired)` in parentheses when disambiguating).

QUALITY & STYLE RULES
- Be opinionated: pick one canonical term per concept and list all rejected aliases under `_Avoid_`.
- Keep definitions tight: 1–2 sentences max, present tense, declarative. Define what the concept IS, not how it works step-by-step or why it exists.
- Verify against the codebase: confirm file paths, config keys, defaults, and exact tool/symbol names in code before adding or editing an entry.
- Cross-references: refer to other glossary entries inline using their canonical spelling (italicized if helpful); avoid external URLs or line-number links.

LIFECYCLE & WORKFLOW
- Add: Place under the fitting `## <Cluster>` or `## Language`; create a new `##` section only when a cohesive cluster emerges.
- Revise: Edit definitions in place when boundaries, paths, or defaults change while keeping the 1–2 sentence cap.
- Rename / Consolidate: Replace the bold term with the new canonical name and move the old name into `_Avoid_` (optionally tagged `(retired)`).
- Retire: Remove entries for deleted concepts. If the old term still appears in legacy files or prompts, keep it in the replacement entry's `_Avoid_` list rather than keeping a dead entry.

ANTI-PATTERNS
- Adding general programming terms or standard library/protocol concepts.
- Defining two synonyms as separate entries instead of choosing one and putting the other in `_Avoid_`.
- Writing multi-paragraph explanations, tutorials, or historical rationale inside definitions.
- Leaving empty `##` sections, using bullet points inside entries, or omitting `_Avoid_` when known aliases exist.

EXAMPLE LAYOUT (4-SPACE INDENTED)
    # Billing

    Processes customer invoices and tracks payment settlement for fulfilled orders.

    ## Language

    **Invoice**:
    A request for payment issued to a customer after order fulfillment.
    _Avoid_: bill, statement, payment request

    **Ledger entry** (settled):
    An immutable accounting record created once an invoice payment clears.
    _Avoid_: transaction, receipt (in prose)

    ## Operations

    **reconcile_invoices**:
    Scheduled job that matches bank settlement records against open invoices.
    _Avoid_: sync_bills, payment_sweep
-->

---

## Language

"""
HEADER_ISSUES = r"""# Issues

Ongoing issue tracker for open bugs, defects, and gaps found while working on
this repository — by humans or by LLM sessions.

<!--
ISSUES.md MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Role: Single local-markdown tracker of currently OPEN bugs, defects, and
  actionable codebase, test, tooling, or documentation gaps.
- Audience: Humans and LLM agents working in this repository.
- Not for: Operational gotchas or non-defect notes (put those in NOTES.md),
  feature brainstorms/specs, or an archive of resolved issues.

UPDATE TRIGGERS
- Add an entry whenever a bug, defect, or gap is flagged during a session —
  however small, and even if only mentioned in passing in a summary.
- Update an existing entry in place if its cause or fix changes while open.
- Delete an entry immediately once its fix is completed and verified.
- Check this file before ending a session if any defect was found or fixed.

INCLUSION / EXCLUSION CRITERIA
- Include: Verified or directly observed defects, failing checks, and gaps.
- Exclude:
  - Operational gotchas and non-defect tips (move to NOTES.md).
  - Fixed or obsolete issues (delete rather than marking done).
  - Unverified guesses (inspect relevant files before recording).

STRUCTURE & FORMATTING
- Top-level sections: `# Issues`, short preamble, this guide, then `## Open`.
- Always keep `## Open` present, even when empty (leave no entries beneath it).
  Never create a `## Closed` or `## Resolved` section.
- ID scheme: `ISS-NNN` using the next free positive integer (`max open n + 1`,
  or `1` if none exist). Never reuse an ID referenced in open work.
- Entry order: Ascending `ISS-NNN` under `## Open`.
- Required fields per entry (exact order, four bullets):
  - `Symptom`: Observable error, failing command, or broken behavior.
  - `Where flagged`: `YYYY-MM-DD, <session or task context>`.
  - `Cause`: Backticked `path/to/file:line` and concise root cause
    (write `Unknown (not yet inspected)` only if uninvestigated).
  - `Suggested fix`: Concrete command, code change, or doc update.
- Formatting: Use ISO dates (`YYYY-MM-DD`) and backticks for file paths,
  line references (`file:line`), commands, and symbols.

QUALITY & STYLE RULES
- Be brief, factual, and direct; keep each bullet to 1–2 short sentences.
- Inspect `docs/ISSUES.md` and the affected files before editing. Never guess
  `file:line` locations, symptoms, or fixes.
- Make surgical edits only: preserve unrelated open entries verbatim.

LIFECYCLE & WORKFLOW
- Read first: Check existing `## Open` entries to avoid duplicates and compute
  the next `ISS-NNN`.
- Reference & link: Refer to entries by `ISS-NNN` in commits or PRs (do not
  use GitHub `#<n>` syntax).
- Close by deleting: Local-markdown entries do NOT auto-close on PR merge.
  Delete the entire `### ISS-NNN` heading and its bullets once fixed (either
  in the fixing commit/PR or manually afterward).
- Verify: Re-read the diff after editing to confirm schema compliance and
  that no unrelated lines changed.

ANTI-PATTERNS
- Marking an entry done, struck through, or moved to `## Closed` instead of
  deleting it.
- Logging operational gotchas or workarounds here instead of `NOTES.md`.
- Assuming GitHub tracker behavior (`#<n>` references or PR auto-closing).
- Omitting required bullets, writing long narratives, or guessing `file:line`.
- Reordering or reformatting existing open entries without cause.

EXAMPLE LAYOUT (4-SPACE INDENTED)
    ## Open

    ### ISS-NNN: <short, specific summary>

    - **Symptom**: `<command or action>` fails with `<brief observed error>`.
    - **Where flagged**: YYYY-MM-DD, <task or check where discovered>.
    - **Cause**: `<path/to/file>:<line>` <concise explanation of defect>.
    - **Suggested fix**: <exact command or minimal change>, then re-run
      `<verification command>`.
-->

---

## Open

"""
HEADER_NOTES = r"""# Notes

Gotchas, oddities, and verified findings that are not open issues (`ISSUES.md`).
Read this before a live or coding session — the quirks below cost real time to rediscover.

<!--
NOTES.md MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Audience: Future LLM agents and developers before coding, debugging, or running live sessions.
- Is: A dense operational reference of verified gotchas, non-obvious invariants, environment/tooling quirks, and fragile coupling that cost real time to rediscover.
- Is NOT: An issue tracker (`ISSUES.md`), architecture log (ADRs), changelog, TODO list, or general API tutorial.

UPDATE TRIGGERS
Update this file at the end of a session (or immediately during work) whenever you:
- Discover and verify a non-obvious failure mode, race, timeout, platform quirk, or workaround.
- Change a default, path, config key, ordering invariant, or constraint already documented here.
- Fix a bug whose regression prevention relies on preserving a hidden constraint (cite `(ISS-NNN, fixed YYYY-MM-DD)`).
- Retire a component, flag, or workaround, making its existing note obsolete.

INCLUSION / EXCLUSION CRITERIA
- Include:
  * Silent failure modes and ordering invariants ("must run X before Y because Z silently breaks").
  * Host/OS/tool/SDK version quirks, port/path/permissions traps, and test-harness constraints.
  * Intentional design traps where the "obvious" refactor breaks a subtle contract.
- Exclude:
  * Open bugs, unverified theories, or unresolved regressions (file in `ISSUES.md` instead).
  * Routine feature summaries, git-history narration, or facts obvious from reading one short function.
  * Speculative advice not directly observed in code, logs, or test runs.

STRUCTURE & FORMATTING
- Top-level structure: Keep `# Notes` and the short preamble visible; keep all entries under `## <component-or-area>` headings.
- Headings: Use short, lowercase component/area names (no `###` subheadings; omit empty `##` sections).
- Numbering/IDs: Do NOT assign numeric IDs (no `NOTE-01`). Use unnumbered `- ` bullets under each `##` heading.
- Sub-items: Keep bullets flat. Use indented numbered items (`  1. `) only for 2-4 tightly coupled consequences of a single root cause.
- Bullet anatomy:
  `- **<Bold lead-in rule or quirk>** [(YYYY-MM-DD[, ref])]: <mechanism, what breaks if violated, exact symbol/path/workaround>.`
- Dates & versions: Use ISO `YYYY-MM-DD` for time-sensitive observations or fixes; pin exact versions when version-specific (e.g., `SDK 2.x`).
- Cross-links: Put symbols, files, keys, and env vars in inline backticks; reference `(ISS-NNN, fixed YYYY-MM-DD)` or `(ADR-NNN)` inline when relevant.

QUALITY & STYLE RULES
- Tone & tense: Terse, factual, imperative or present tense for active invariants; past tense only for the observed failure/repro.
- Brevity: Target 1-4 sentences (one paragraph) per bullet.
- Evidence required: State concrete thresholds, paths, error behaviors, and symbols rather than vague adjectives ("slow", "broken"). Always pair a prohibition ("never do X") with its failure mode and the safe alternative.

LIFECYCLE & WORKFLOW
- Add: Append a new bullet under the most specific existing `## <component-or-area>` (or create a new `##` section). Merge closely related facts into one bullet instead of fragmenting.
- Edit in place: When behavior, defaults, or paths change, rewrite the existing bullet in place and update its date. Never append a second bullet that contradicts an older one.
- Promote/Migrate: Move unresolved defects to `ISSUES.md`. If an architectural choice gets an ADR, link `(ADR-NNN)` and keep only the operational footgun here.
- Retire: Delete bullets when the underlying component or quirk is removed, unless residual disk/state cleanup remains relevant (narrow the note to that residue).

ANTI-PATTERNS
- Dumping raw terminal logs, multi-paragraph essays, or fenced code blocks into bullets.
- Recording unverified guesses, open bugs, or personal workspace state irrelevant to other sessions.
- Writing "Do not change X" without explaining *what breaks* and *what to do instead*.
- Leaving stale bullets intact after refactoring, or leaving empty `##` sections behind.

EXAMPLE LAYOUT (4-SPACE INDENTED)

    ## worker-runtime

    - **Flush queue state before releasing the process lock** (`runtime.stop`, 2026-05-14): `clear_dirty_flags` is unscoped; releasing the lock first lets a newly spawned worker lose dirty state written concurrently. Always join background threads and flush while the lock is held.
    - **Loopback probes must target `127.0.0.1`, not `localhost`** (ISS-12, fixed 2026-06-02): On dual-stack hosts where the service binds IPv4 only, `localhost` stalls on IPv6 connect timeouts (~1 s per request). Pass URLs through `net.ipv4_loopback` before calling the HTTP client.
-->

---

"""
HEADER_RUNBOOK = r"""# Runbook

Repeatable operational procedures for this repository, executed by operators or agents under time pressure. Each entry covers one verified task; see [Entries](#entries) below to locate a procedure.

**Risk legend:** `SAFE` (reads or disposable writes) · `OPERATOR` (recoverable state changes) · `MANUAL` (actions outside the terminal) · `DESTRUCTIVE` (deletion or irreversible change).

<!--
RUNBOOK MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Repeatable, ordered operational procedures executed under time pressure (setup, probes, recovery, cleanup, release).
- Intended reader: an operator or agent executing a task mid-incident or mid-workflow.
- NOT for design rationale, architecture docs, API/config reference, or changelogs.

UPDATE TRIGGERS
Update this file before ending a session whenever you:
- Add a new repeatable operational workflow.
- Change commands, flags, paths, config keys, or expected output for an existing entry.
- Execute a [DRAFT] entry or branch in a real run (confirm steps and remove [DRAFT], or record observed failures).
- Confirm a new failure mode and its fix during a real run.
- Retire an obsolete workflow or step.

INCLUSION / EXCLUSION CRITERIA
- Include: one focused, repeatable task per entry; only steps and failures confirmed by a real run (or marked [DRAFT] if untested).
- Exclude: imagined procedures not marked [DRAFT], one-off commands, background prose, design rationale, and non-executable reference material.

STRUCTURE & FORMATTING
- Single H1: Keep `# Runbook` as the only H1 in the file.
- Summary Index Table: Maintain `| RUN | Procedure |` under `## Entries` in ascending numeric order. Every row must link to its section anchor (`[NNN](#run-nnn-risk-kebab-case-title)`).
- File order: visible preamble -> this comment -> `## Entries` index table -> `## RUN-NNN ...` sections in ascending ID order.
- IDs: sequential 3-digit zero-padded IDs (`RUN-NNN`, starting at 001). Assign the next free ID. Never renumber entries or reuse retired IDs.
- Entry heading: `## RUN-NNN (<RISK>): <imperative task>` (append `[DRAFT]` if untested).
- Risk tags: `SAFE`, `OPERATOR`, `MANUAL`, `DESTRUCTIVE`. Combine with `, ` when multiple apply (e.g., `OPERATOR, MANUAL`).
- Summary paragraph (required): 1-2 sentences right under the heading stating what the procedure does and what it does NOT cover.
- Steps (required): numbered ordinal steps (`1.`, `2.`, ...), one action per step, copy-pasteable code block, and `Expected: <observable result>.` when it helps confirm success.
- Troubleshooting (optional; omit heading if no confirmed failures exist): `**Troubleshooting**`, followed by symptom-first bullets ordered from cheapest to most expensive diagnostic: ``- **`<verbatim symptom>`**: <cause>. Fix: `<command>`.``

QUALITY & STYLE RULES
- Voice & brevity: imperative or present tense, concise, high-signal; no filler or historical commentary.
- Truth & placeholders: record only steps and failures observed in a real run. Keep unknown values visibly bracketed as `[placeholder]` and explain how to obtain them; never invent values. Mark untested entries or branches `[DRAFT]` and ask the first real runner to report back.
- Commands: copy-pasteable with concrete values where known; label variants inside the code block (`# safe mode` / `# live mode`).
- Ordering & safety: state wrong-order consequences inline before hazardous steps. For `OPERATOR` or `DESTRUCTIVE` entries, state the rollback path (or plainly note that none exists) and end with a verification step proving the final observable state. Mark the preferred path `(recommended)` when alternatives exist.

LIFECYCLE & WORKFLOW
- Add: assign the next free `RUN-NNN`, add a row to `## Entries`, and append the entry using the Example Layout below.
- Update: edit commands, expected results, and troubleshooting inline when behavior changes; remove obsolete steps.
- Promote draft: after a real run confirms the steps, update observed outputs, fill resolved placeholders, and remove `[DRAFT]`.
- Retire: delete the `## RUN-NNN` section body and update its `## Entries` row to `| [NNN](#...) | Retired - <reason or replacement RUN-NNN> |` so the ID is never reused.

ANTI-PATTERNS
- Writing desk-imagined steps without `[DRAFT]`.
- Inventing tokens, ports, hostnames, or IDs instead of using `[bracketed placeholders]`.
- Renumbering entries or reusing retired `RUN-NNN` IDs.
- Putting multiple actions in one step, or using bullets instead of numbered steps.
- Writing vague troubleshooting ("check logs") instead of verbatim symptom + cause + exact fix.
- Leaving stale commands after changing code/tooling, or adding design rationale.

EXAMPLE LAYOUT (4-SPACE INDENTED)

    ## Entries

    | RUN | Procedure |
    |---|---|
    | [001](#run-001-risk-imperative-task) | <imperative task> |

    ---

    ## RUN-001 (OPERATOR): <imperative task>

    <What this procedure does.> Does not <scope exclusion>. Rollback: <undo command, or "none; state change is irreversible">.

    1. <Perform one action (note wrong-order consequence if applicable)>:

       ```
       # safe mode (recommended)
       <command with [bracketed placeholder] - obtain via [how]>
       ```

       Expected: <observable result>.

    2. <Verify final observable state>:

       ```
       <verification command>
       ```

       Expected: <observable end state>.

    **Troubleshooting**

    - **`<verbatim error or log string>`**: <cause>. Fix: `<exact command>`.
-->

---

## Entries

| RUN | Procedure |
|---|---|

"""
HEADER_TECH_DEBT = r"""# Technical Debt Tracker

Canonical register of verified technical debt for this repository. Maintained autonomously by LLM agents and engineering contributors per the embedded specification below.

<!--
TECH_DEBT.md MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Authoritative repo-local tracker for verified, actionable technical debt across code, security, architecture, dependencies, tests, performance, data, documentation, infrastructure, and process.
- Intended readers: autonomous coding/audit agents and engineers prioritizing, executing, or verifying debt paydown.
- NOT a product backlog, feature request list, functional user-bug tracker, ADR archive, sprint capacity planner, or refactoring tutorial.

UPDATE TRIGGERS
Update this file whenever ANY of the following occurs:
- Audit / Health Check: Asked to audit, inventory, assess code health, or rank what to refactor first (run applicable stack checks across scope and reconcile the full file).
- Debt Introduced: Before ending a session in which you add a workaround, TODO/FIXME/HACK, skipped test, suppressed lint/type check, pinned legacy dependency, or deferred design fix.
- Debt Discovered: Encountering qualifying, untracked debt in files read or modified during unrelated feature or bug work.
- Status / Scope Change: Starting, pausing, decomposing, re-scoping, reassigning, or moving/renaming files referenced by an active entry.
- Remediation Verified: After fixing debt AND confirming via re-scan/tests/build that the finding/metric dropped (never mark Done on code edits alone).
- Component Retirement: When deleting or replacing code referenced by active entries.

STACK DETECTION & AUDIT CHECKS
Inspect root manifests before scanning to select applicable checks:
- Node / TypeScript / React (`package.json`): outdated/unused deps (`npm outdated`, `depcheck`/`knip`), CVEs (`npm audit`), strict typecheck (`tsc`), zero-warning lint (`eslint`), circular deps (`madge`), initial bundle size.
- PHP / Laravel (`composer.json`): outdated/unused deps (`composer outdated`), CVEs (`composer audit`), static analysis (`phpstan`), complexity/mess (`phpmd`), layer boundaries (`deptrac`).
- Database / MySQL (when schema/migrations/DB exist): migration-vs-schema drift, `EXPLAIN` / full table scans, unindexed FKs, missing FK constraints.
- Other Stacks (`pyproject.toml`, `go.mod`, `Cargo.toml`, etc.): run equivalent repo-native linters, typecheckers, complexity/coverage tools, and vulnerability scanners.
- Cross-Stack (all repos): secret scans (`gitleaks`/`trufflehog`), test coverage/runtime reports, git log aging on `TODO`/`FIXME`/`HACK` (>6 months), build/CI warnings, `CODEOWNERS`.

INCLUSION / EXCLUSION CRITERIA
INCLUDE an entry ONLY when directly observed in repo files or tool output and matching at least one category threshold below.

Canonical Category Slugs (normalize synonyms: `design`→`architecture`, `deps`→`dependency`, `perf`→`performance`, `docs`→`documentation`, `infra`→`infrastructure`):
- `code`:
  Subcategories: `large_function`, `high_complexity`, `deep_nesting`, `long_parameter_list`, `god_class`, `duplicate_code`, `dead_code`, `magic_numbers`, `commented_code`, `poor_naming`, `inconsistent_patterns`, `empty_catch_blocks`, `generic_exceptions`, `missing_error_handling`, `data_clumps`.
  Thresholds: functions >50 lines (>20 simple ops); cyclomatic complexity >10; nesting >4 levels; >4 params; class >300 lines or >15 public methods; duplicated blocks >30 lines or >3 similar blocks; unreachable/unused exports/commented-out blocks; magic numbers/hardcoded business literals; empty/generic/missing error handling.
- `security`:
  Subcategories: `secrets_in_code`, `missing_input_validation`, `weak_auth_hashing`, `unbounded_sessions`, `missing_rate_limiting`, `missing_security_headers`, `missing_authorization`.
  Thresholds: committed secrets/API keys/credentials (source or git history); public endpoints lacking schema/DTO/FormRequest validation; MD5/SHA-1 password hashing (require bcrypt/argon2id); unbounded sessions or un-rate-limited auth endpoints; missing CSP/HSTS/X-Content-Type-Options/Referrer-Policy; missing authorization checks on protected routes.
- `architecture`:
  Subcategories: `monolithic_design`, `circular_dependencies`, `god_object`, `inappropriate_intimacy`, `abstraction_inversion`, `leaky_abstractions`, `shotgun_surgery`, `broken_hierarchy`, `performance_bottlenecks`, `resource_contention`, `single_point_failure`.
  Thresholds: circular module dependencies; reversed layer dependencies (e.g., repository→service→UI); shotgun surgery (1 change requires edits in 5+ files); framework types leaking across layer boundaries; monolithic bottlenecks or single points of failure.
- `dependency`:
  Subcategories: `outdated_dependencies`, `vulnerable_dependencies`, `deprecated_dependencies`, `version_conflicts`, `license_violations`, `license_unknown`, `unused_dependencies`, `oversized_dependencies`, `redundant_dependencies`.
  Thresholds: >2 major versions behind; unmaintained/abandoned (>24 months without release); HIGH/CRITICAL CVEs; unused declared packages; version conflicts; incompatible/unknown licenses; unpinned or heavy single-purpose deps.
- `test`:
  Subcategories: `low_coverage`, `missing_unit_tests`, `missing_integration_tests`, `missing_end_to_end_tests`, `flaky_tests`, `slow_tests`, `brittle_tests`, `disabled_tests`, `unclear_test_intent`, `missing_test_data`, `environment_dependencies`.
  Thresholds: critical-path coverage <80%; missing unit/integration tests for critical logic/workflows; flaky tests on main; skipped/disabled tests without linked issue or removal date; test suite >10 min without documented budget; tests lacking meaningful assertions or test-data strategy.
- `performance`:
  Subcategories: `n_plus_one_queries`, `missing_pagination`, `bundle_bloat`, `missing_caching`.
  Thresholds: N+1 queries on list endpoints; unbounded list queries (missing pagination); initial frontend bundle >200 KB gzip or missing route-level code splitting; uncached expensive read/aggregation paths.
- `data`:
  Subcategories: `schema_drift`, `missing_indexes`, `orphaned_records`.
  Thresholds: production/actual schema diverging from migrations; unindexed FKs or hot-query columns causing sequential scans; unenforced FKs or orphaned child records.
- `documentation`:
  Subcategories: `missing_api_docs`, `outdated_api_docs`, `missing_comments`, `outdated_comments`, `missing_architecture_docs`, `missing_deployment_docs`, `missing_onboarding_docs`, `missing_docstring`.
  Thresholds: README contradicting current setup/dev workflow; comments contradicting code; public APIs/exports lacking docblocks or type hints; missing ADRs/architecture/deployment/onboarding docs; docs stale >3-6 months.
- `infrastructure`:
  Subcategories: `eol_runtime`, `deprecated_framework_api`, `build_warnings`, `secrets_management`, `missing_monitoring`, `inadequate_logging`, `missing_alerting`, `poor_observability`, `manual_deployment`, `missing_pipeline`, `environment_drift`, `hardcoded_config`, `missing_dr_plan`.
  Thresholds: EOL/near-EOL runtimes; deprecated framework APIs; non-zero build/compile/lint warnings; secrets outside a secret manager (plain env/long-lived shared creds); missing structured logs, error tracking, p95 latency metrics, SLO alerts, CI/CD, IaC, or DR plan; dev/staging/prod drift.
- `process`:
  Subcategories: `aging_todo_fixme`, `unscheduled_deprecation`, `untracked_debt`, `missing_codeowners`, `lingering_feature_flags`.
  Thresholds: `TODO`/`FIXME`/`HACK` >6 months old without owner/ticket; `@deprecated` without removal date/replacement; missing/stale `CODEOWNERS`; feature flags at 100% rollout >6 weeks without removal plan; ad-hoc untracked workarounds.

EXCLUDE:
- Unverified suspicions without observed `file:line`, symbol, or tool output.
- Cosmetic formatting already enforced by auto-formatters.
- Product feature requests or functional user-facing bugs unrelated to code/design/ops health.
- Speculative future-proofing without measurable current velocity, quality, reliability, or security cost.
- Trivial <15-min cleanups safe to fix immediately inline (fix now instead of logging overhead).
- Duplicate entries for the same root cause (consolidate systemic occurrences under one ID listing affected paths).

SCORING, EFFORT & PRIORITY MODEL
Impact Tiers (calibrated to 1-10 severity across velocity, quality, productivity, business):
- `CRITICAL` (9-10): Active security vulns/secrets, prod-breaking/data-loss risk, compliance/legal violations, team blockers.
- `HIGH` (7-8): Major velocity slowdown, regular prod defects, customer-facing quality/perf risk, severe arch/test gaps.
- `MEDIUM` (4-6): Moderate maintenance friction, localized complexity/duplication, partial observability/doc gaps.
- `LOW` (1-3): Minor doc/style/cleanup issues with negligible risk.

Effort Sizes:
- `XS`: 1-4 hours | `S`: 0.5-2 days | `M`: 3-5 days | `L`: 1-2 weeks | `XL`: 3+ weeks.
- Rule: Any `L` or `XL` entry MUST be decomposed into `XS`-`M` child items before entering `Planned` or `In Progress`.

Deterministic Priority Matrix (Effort x Impact):
- `P0`: `CRITICAL` + `XS`/`S`/`M`
- `P1`: `CRITICAL` + `L`/`XL` (decompose first), OR `HIGH` + `XS`/`S`/`M`
- `P2`: `HIGH` + `L`/`XL` (decompose first), OR `MEDIUM` + `XS`/`S`/`M`
- `P3`: `MEDIUM` + `L`/`XL` (decompose first), OR `LOW` (any effort)

Optional Quantitative Scoring (for `P0`/`P1` or tie-breaking when real telemetry exists; NEVER fabricate inputs):
- `Interest Rate = Impact (1-10) x Encounters per Sprint`
- `Cost of Delay = Interest Rate x Sprints Delayed x Team Multiplier`
- `WSJF = (Business Value [1-10] + Time Criticality [1-10] + Risk Reduction [1-10]) / EffortWeight (XS=1, S=2, M=5, L=8, XL=13)`
- `Quadrant`: `Reckless-Deliberate` (highest urgency), `Prudent-Deliberate`, `Reckless-Inadvertent`, `Prudent-Inadvertent`.

STRUCTURE & FORMATTING
Keep these exact 4 top-level `##` headings in order. Never delete a required heading; if a section has no entries, write `_None._` (and omit empty table headers):
1) `## Summary`
   - Bullets: `**Last Updated:** YYYY-MM-DD`, `**Last Full Audit:** YYYY-MM-DD (or Pending) | **Stacks:** {detected} | **Audit Checks:** X PASS / Y FAIL / Z N/A (or Pending)`, `**Open Debt:** N total (P0: n, P1: n, P2: n, P3: n)`, `**Trend:** Baseline | Improving | Stable | Worsening (Resolved since last audit: N)`, `**Open by Category:**` (comma-separated non-zero `category: count` pairs, or `None`), `**Top 3 to Pay Down First:**` (numbered list `1.`-`3.` of highest-priority IDs with 1-line rationale, or `None`).
2) `## Active Debt Ledger`
   - Markdown table of ALL non-terminal items (`Status` not `Done` or `Won't Fix`).
   - Exact columns: `| ID | Priority | Status | Category | Subcategory | Item | Location | Effort | Impact | Updated |`
   - Strict sort order: (1) Priority `P0`→`P3`, (2) Effort ascending `XS`→`XL` (break ties by higher CoD/WSJF if recorded, then ID ascending).
3) `## Debt Details`
   - One `### DEBT-YYYY-NNN: Short Title` subsection per active ledger row, in exact ledger sort order.
   - Required bullets: `**Category / Subcategory:**`, `**Status / Priority:**`, `**Location:**`, `**Dates:**` (`Created YYYY-MM-DD | Updated YYYY-MM-DD`), `**Evidence:**`, `**Impact Rationale:**`, `**Remediation Target:**`.
   - Optional bullets (omit if empty): `**Scoring:**` (`Quadrant` / `CoD` / `WSJF` / `Risk` / `Skill`), `**Dependencies / Ref:**` (parent/child IDs, PR/issue/ADR links, owner, tags).
4) `## Resolved & Retired Log`
   - Append-only table preserving history, sorted newest `Closed` date first.
   - Exact columns: `| ID | Category | Item | Final Status | Resolution & Verification Evidence | Closed |`

Formatting Conventions:
- IDs: `DEBT-YYYY-NNN` (4-digit creation year + zero-padded sequence >=3 digits starting at `001`; e.g., `YYYY=2026`, `NNN=001`). Monotonic per year; NEVER reuse retired IDs.
- Dates: Strict ISO-8601 `YYYY-MM-DD`.
- Status Lifecycle: Active (`Identified`, `Analyzed`, `Prioritized`, `Planned`, `In Progress`, `Review`) → Terminal (`Done`, `Won't Fix`).
- Locations & Cross-links: Repo-relative paths with line ranges in backticks (e.g., `` `src/auth/login.ts:45-120` ``); cite only verified files, ADRs, or issue IDs.

QUALITY & STYLE RULES
- Tone & Brevity: Terse, objective, factual. Keep ledger `Item` titles <=70 chars; keep detail text to 1-3 crisp sentences.
- Evidence Mandate: Cite directly observed `file:line`, symbols, or command output. Never guess line numbers, CVEs, test timings, or coverage percentages.
- Targeted Update vs. Full Audit: When logging or closing individual items mid-task, update affected items, `Last Updated`, `Open Debt`, `Open by Category`, and `Top 3`; do NOT alter `Last Full Audit` or `Audit Checks` unless a full audit ran.
- Verification Loop: Before transitioning any item to `Done`, re-run the relevant scan/test/lint/audit command to verify the finding disappeared or metric dropped. Rework that leaves debt metrics unchanged is not debt paydown.

LIFECYCLE & WORKFLOW
- Add: Assign next unused `DEBT-YYYY-NNN`; set `Identified` (or `Analyzed`/`Prioritized` once scored); add row to `## Active Debt Ledger`, add block to `## Debt Details`, and update `## Summary`.
- Promote / Edit: Advance `Status` (`Identified`→`Analyzed`→`Prioritized`→`Planned`→`In Progress`→`Review`); bump `Updated`; keep Ledger, Details, and Summary synchronized.
- Decompose (`L`/`XL`): Create `XS`-`M` child `DEBT-YYYY-NNN` entries referencing the parent ID; retire the oversized parent to `## Resolved & Retired Log` as `Done` (`Decomposed into DEBT-YYYY-AAA, ...`) to avoid double-counting.
- Retire (`Done` / `Won't Fix`): Never delete entries. Remove from `## Active Debt Ledger` and `## Debt Details`, prepend row to `## Resolved & Retired Log` with `Final Status`, verification evidence or explicit rationale (e.g., `Accepted via ADR-012` / `Component deleted`), and `Closed` date; update `## Summary`.

ANTI-PATTERNS
- Logging speculative debt without inspecting code/output, or leaving stale `Location` paths after refactors.
- Marking debt `Done` without post-fix verification confirming reduction.
- Deleting closed items, erasing history, or reusing `DEBT-YYYY-NNN` IDs.
- Fabricating `Interest Rate` / `Cost of Delay` scores when encounter/sprint data is missing.
- Scheduling unsplit `L`/`XL` items into `Planned` or `In Progress`.
- Letting `## Summary` counts or `Top 3` drift out of sync with `## Active Debt Ledger`.
- Adding refactoring tutorials, sprint velocity ratios, or general feature/bug tasks to this file.

EXAMPLE LAYOUT (4-SPACE INDENTED)

    ## Summary

    - **Last Updated:** 2026-01-15
    - **Last Full Audit:** 2026-01-15 | **Stacks:** Node/TypeScript | **Audit Checks:** 40 PASS / 1 FAIL / 1 N/A
    - **Open Debt:** 1 total (P0: 1, P1: 0, P2: 0, P3: 0)
    - **Trend:** Improving (Resolved since last audit: 1)
    - **Open by Category:** security: 1
    - **Top 3 to Pay Down First:**
      1. `DEBT-YYYY-002` — Unvalidated public webhook endpoint (`P0`, `S` quick win eliminating auth bypass risk).

    ## Active Debt Ledger

    | ID | Priority | Status | Category | Subcategory | Item | Location | Effort | Impact | Updated |
    | :- | :- | :- | :- | :- | :- | :- | :- | :- | :- |
    | DEBT-YYYY-002 | P0 | Prioritized | security | missing_input_validation | Public billing webhook skips schema/signature check | `src/api/webhook.ts:18-64` | S | CRITICAL | 2026-01-15 |

    ## Debt Details

    ### DEBT-YYYY-002: Public billing webhook skips schema/signature check

    - **Category / Subcategory:** security / missing_input_validation
    - **Status / Priority:** Prioritized / P0 (Impact: CRITICAL, Effort: S)
    - **Location:** `src/api/webhook.ts:18-64`
    - **Dates:** Created 2026-01-10 | Updated 2026-01-15
    - **Evidence:** Route parses `req.body` directly without Zod schema or HMAC signature validation (`eslint`/manual audit).
    - **Impact Rationale:** Exposes billing state transitions to spoofed requests (9/10 security risk).
    - **Remediation Target:** Add HMAC verification middleware + strict DTO schema; verify with negative integration tests.
    - **Scoring:** Quadrant: Reckless-Deliberate | WSJF: 13.5 | Risk: low | Skill: mid
    - **Dependencies / Ref:** Tags: `security`, `api`

    ## Resolved & Retired Log

    | ID | Category | Item | Final Status | Resolution & Verification Evidence | Closed |
    | :- | :- | :- | :- | :- | :- |
    | DEBT-YYYY-001 | dependency | Upgrade lodash 4.17.15 (HIGH CVE) | Done | Upgraded to 4.17.21; `npm audit` reports 0 HIGH/CRITICAL vulns | 2026-01-14 |
-->

---

## Summary

- **Last Updated:** YYYY-MM-DD
- **Last Full Audit:** Pending | **Stacks:** Pending | **Audit Checks:** Pending
- **Open Debt:** 0 total (P0: 0, P1: 0, P2: 0, P3: 0)
- **Trend:** Baseline
- **Open by Category:** None
- **Top 3 to Pay Down First:** None

## Active Debt Ledger

_None._

## Debt Details

_None._

## Resolved & Retired Log

_None._

"""
HEADER_TOOLS = r"""# Tools

Development helper scripts live in [`tools/`](../tools/) (top level). This file is the
inventory and the reference for agents deciding whether a new script is needed.

**Before writing any new tool, check this inventory.** If an existing tool can do the job,
use it instead of adding another script. Existing tools may be extended with more features
as long as the additions fit the purpose the tool was designed for. **Whenever a tool is
created or modified, this document must be updated in the same session** so the inventory
stays current.

<!--
TOOLS.md MAINTENANCE GUIDE (FOR AGENTS & CONTRIBUTORS)

PURPOSE & SCOPE
- Is: The canonical inventory of standalone developer/agent helper scripts in `tools/`
  and the mandatory pre-creation check before adding any new script.
- Is Not: A CLI flag manual, usage tutorial, changelog, or registry for application
  source code, build artifacts, or third-party binaries.
- Audience: LLM agents and developers maintaining this repository.

UPDATE TRIGGERS
- Check this file BEFORE writing any new helper script.
- Update this file IN THE SAME SESSION whenever a script in `tools/` is added,
  renamed, deleted, or modified in purpose, inputs/outputs, paths, or dependencies.

INCLUSION / EXCLUSION CRITERIA
- Include: Top-level standalone scripts/executables in `tools/` meant to be invoked
  directly.
- Exclude: Internal shared modules imported only by other scripts, uncommitted one-off
  scripts, generated artifacts, and exhaustive CLI flag lists (keep those in script
  help output or source docstrings).

STRUCTURE & FORMATTING
- Top-level structure: `# Tools`, short preamble linking [`tools/`](../tools/), this
  comment block, and `## Inventory`. Always keep `## Inventory` (if empty, put
  `_No tools registered._`); omit any extra sections.
- Ordering: Strictly alphabetical (case-insensitive) by exact filename.
- Entry format: Single-line bullet using ``- **`<Filename.ext>`** — <Summary>``
  (bold inline code filename, single space, em-dash `—`, single space).
- Metadata policy: No ID numbers, dates, versions, or inline status tags. Reference
  affected repo paths in inline code.

QUALITY & STYLE RULES
- Voice & Tense: Concise, third-person present tense starting with an action verb
  (e.g., "Validates...", "Exports...", "Cleans...").
- Brevity: 1 to 2 sentences on a single bullet line; no sub-bullets or code blocks.
- Verification: Read the actual script before writing or editing an entry. State what
  it does, key inputs/outputs or repo paths, and non-stdlib packages or external
  SDKs/tools required (note `Standard library only.` if none).

LIFECYCLE & WORKFLOW
- Add: Confirm no existing tool fits or can be extended; add script to `tools/`;
  insert entry in alphabetical order under `## Inventory`.
- Modify: Update the existing bullet in place if behavior, paths, or dependencies
  change.
- Rename: Update the backticked filename and re-sort alphabetically.
- Retire: Delete the bullet in the same session the script is removed from `tools/`
  (rely on git history; do not retain deprecated or struck-through entries).

ANTI-PATTERNS
- Adding a new script without first checking or extending existing tools.
- Documenting CLI flags, usage examples, or implementation internals here.
- Leaving stale/deleted entries, unsorted entries, or unverified claims.
- Using hyphens (`-`) instead of an em-dash (`—`), omitting bold/backticks on
  filenames, or adding sub-bullets.

EXAMPLE LAYOUT (4-SPACE INDENTED)

    ## Inventory

    - **`CheckAssets.py`** — Validates asset sizes under `assets/` against thresholds and exits non-zero on failure. Standard library only.
    - **`SyncSchemas.py`** — Regenerates bindings from `schemas/` into `include/generated/` via `codegen-cli` (Node.js).
-->

---

## Inventory

_No tools registered._

"""

AGENTS_HEADING = "## Project Docs"
AGENTS_INTRO = "Read the relevant doc before planning or reporting work:"
AGENTS_ENTRIES = {
    "arch": "- [docs/ARCH.md](docs/ARCH.md) — the live architecture overview (topology, data flow, domain/data model, component design, testing). **Important:** update it whenever the project's structure, runtime topology, interfaces, schema, or behaviour changes; when the document and the code disagree, the code wins.",
    "changelog": "- [docs/CHANGELOG.md](docs/CHANGELOG.md) — the user-facing, curated history of notable changes. **It must be updated after every agent session**.",
    "decisions": '- [docs/DECISIONS.md](docs/DECISIONS.md) — architecture decision records (ADRs) in compressed form: the "why" behind structural, architectural, and dependency choices. **Read the relevant entry before changing behaviour that looks unusual, and add an entry for every new architectural decision.**',
    "glossary": "- [docs/GLOSSARY.md](docs/GLOSSARY.md) — canonical domain terms; use its vocabulary in code, docs, and summaries.",
    "issues": "- [docs/ISSUES.md](docs/ISSUES.md) — the ongoing issue tracker. **Add every issue, bug or defect flagged during an LLM session here — even if it is only mentioned in passing in the summary — and delete the entry once it is fixed.**",
    "notes": "- [docs/NOTES.md](docs/NOTES.md) — gotchas, watch-outs and oddities. **Add anything a future session needs to know that is not an open issue here.**",
    "runbook": "- [docs/RUNBOOK.md](docs/RUNBOOK.md): numbered operator procedures. **Review it each session and update any procedures affected by the work.**",
    "tech-debt": "- [docs/TECH_DEBT.md](docs/TECH_DEBT.md) — architectural debt and code smells. **Add every structural anti-pattern, code duplication, or AI-induced code smell spotted during a session here, and delete the entry once refactored.**",
    "tools": "- [docs/TOOLS.md](docs/TOOLS.md) — the inventory of development scripts in [tools/](tools/). **Check it before writing any new tool, and update it whenever a tool is created or modified.**",
}
AGENTS_SKELETON_HEAD = r"""# AGENTS.md

## Project Overview

<Brief description of the project, its purpose, and how to run it.>

"""
AGENTS_SKELETON_TAIL = r"""## Conventions

<Code style guidelines, common workflows, and project-specific conventions.>
"""

DOCS_DIR = Path("docs")
AGENTS_FILE = Path("AGENTS.md")

DOCS = [
    ("arch", "ARCH.md", HEADER_ARCH),
    ("changelog", "CHANGELOG.md", HEADER_CHANGELOG),
    ("decisions", "DECISIONS.md", HEADER_DECISIONS),
    ("glossary", "GLOSSARY.md", HEADER_GLOSSARY),
    ("issues", "ISSUES.md", HEADER_ISSUES),
    ("notes", "NOTES.md", HEADER_NOTES),
    ("runbook", "RUNBOOK.md", HEADER_RUNBOOK),
    ("tech-debt", "TECH_DEBT.md", HEADER_TECH_DEBT),
    ("tools", "TOOLS.md", HEADER_TOOLS),
]


def build_parser():
    parser = argparse.ArgumentParser(
        prog="create_docs.py",
        description=(
            "Create or refresh the standard project docs in docs/ with their canonical "
            "headers, and register them in AGENTS.md. Use --<name> with no value to "
            "create a new doc; pass N (the last line of the old header) to replace the "
            "first N lines of an existing doc. --agents replaces AGENTS.md lines "
            "BEGIN:END with the Project Docs section; -1 creates a skeleton AGENTS.md."
        ),
    )
    parser.add_argument(
        "--list", action="store_true", help="list existing standard docs in docs/"
    )
    parser.add_argument(
        "--agents",
        metavar="BEGIN:END",
        default=_ABSENT,
        help="replace AGENTS.md lines BEGIN:END with the Project Docs section "
        "(BEGIN:BEGIN-1 inserts without replacing), or -1 to create a skeleton AGENTS.md",
    )
    for flag, filename, _header in DOCS:
        parser.add_argument(
            "--" + flag,
            nargs="?",
            const=None,
            default=_ABSENT,
            type=int,
            metavar="N",
            dest=flag.replace("-", "_"),
            help="create or refresh " + filename + " (N = last line of the old header)",
        )
    return parser


def _encode(text, eol):
    if eol != "\n":
        text = text.replace("\n", eol)
    return text.encode("utf-8")


def _compose(header, rest, eol):
    text = header if rest is None else header + "\n".join(rest) + "\n"
    return _encode(text, eol)


def _agents_block_lines(flagset):
    lines = [AGENTS_HEADING, "", AGENTS_INTRO]
    for flag, _filename, _header in DOCS:
        if flag in flagset:
            lines.append(AGENTS_ENTRIES[flag])
    return lines


def _handle_agents(value, selected):
    flagset = {flag for flag, _filename, _header, _n in selected}
    if not flagset:
        print(
            "note: no document flags given; the Project Docs section will list no entries",
            file=sys.stderr,
        )
    block = _agents_block_lines(flagset)
    if value == "-1":
        if AGENTS_FILE.exists():
            print(
                "error: AGENTS.md already exists; pass --agents BEGIN:END to update it",
                file=sys.stderr,
            )
            return 1
        text = AGENTS_SKELETON_HEAD + "\n".join(block) + "\n\n" + AGENTS_SKELETON_TAIL
        AGENTS_FILE.write_bytes(_encode(text, "\n"))
        print("created AGENTS.md")
        return 0
    begin_s, sep, end_s = value.partition(":")
    if not sep or not begin_s.isdigit() or not end_s.isdigit():
        print(f"error: --agents expects BEGIN:END or -1, got: {value}", file=sys.stderr)
        return 1
    begin, end = int(begin_s), int(end_s)
    if not AGENTS_FILE.exists():
        print(
            "error: AGENTS.md not found; pass --agents -1 to create it", file=sys.stderr
        )
        return 1
    raw = AGENTS_FILE.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines()
    if begin < 1 or begin > len(lines) + 1 or end < begin - 1 or end > len(lines):
        print(
            f"error: --agents {value} is out of range: AGENTS.md has {len(lines)} lines",
            file=sys.stderr,
        )
        return 1
    out = lines[: begin - 1]
    if out and out[-1] != "":
        out.append("")
    out += block
    after = lines[end:]
    if after and after[0] != "":
        out.append("")
    out += after
    AGENTS_FILE.write_bytes(_encode("\n".join(out) + "\n", eol))
    if end == begin - 1:
        print(f"updated AGENTS.md (inserted before line {begin})")
    else:
        print(f"updated AGENTS.md (replaced lines {begin}:{end})")
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    doc_args = [
        (flag, filename, header, getattr(args, flag.replace("-", "_")))
        for flag, filename, header in DOCS
    ]
    selected = [d for d in doc_args if d[3] is not _ABSENT]
    agents_value = args.agents

    if args.list:
        if selected or agents_value is not _ABSENT:
            parser.error("--list cannot be combined with document flags or --agents")
        for _flag, filename, _header, _n in doc_args:
            path = DOCS_DIR / filename
            if path.is_file():
                count = len(path.read_bytes().decode("utf-8").splitlines())
                print(f"{path.as_posix()} ({count} lines)")
        return 0

    if not selected and agents_value is _ABSENT:
        parser.error(
            "no document selected: use --list, --agents, or one of --arch ... --tools"
        )

    errors = 0
    for flag, filename, header, n in selected:
        path = DOCS_DIR / filename
        if not path.is_file():
            if n is not None:
                print(
                    f"note: {path.as_posix()} does not exist; ignoring line argument {n}",
                    file=sys.stderr,
                )
            DOCS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_compose(header, None, "\n"))
            print(f"created {path.as_posix()}")
            continue
        if n is None:
            print(
                f"error: {path.as_posix()} already exists; pass the line where its header "
                f"ends, e.g. --{flag} 20 (the first 20 lines are replaced)",
                file=sys.stderr,
            )
            errors += 1
            continue
        raw = path.read_bytes().decode("utf-8")
        eol = "\r\n" if "\r\n" in raw else "\n"
        lines = raw.splitlines()
        if n < 1 or n > len(lines):
            print(
                f"error: --{flag} {n} is out of range: "
                f"{path.as_posix()} has {len(lines)} lines",
                file=sys.stderr,
            )
            errors += 1
            continue
        path.write_bytes(_compose(header, lines[n:], eol))
        print(f"updated {path.as_posix()} (replaced {n} lines)")

    if agents_value is not _ABSENT:
        errors += _handle_agents(agents_value, selected)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
