---
name: anti-vibecode-sdd
description: Creates robust, scalable, maintainable and documented software projects without AI or vibe-coded quality problems, using Spec-Driven Development (SDD). Use when starting a new project, writing or reviewing specs/plans/tasks, applying the anti-vibecode standard, deciding what to test, or designing UI. Triggers: "new project", "spec-driven", "SDD", "anti-vibecode", "not vibe coded", "proyecto nuevo", "sin vibe codear". Bundles the anti-vibecode guide, portable prompt, machine-readable standard and the SDD phase prompts.
---

# Anti-vibecode SDD

## Overview

This skill packages the Silex method: **Spec-Driven Development (SDD)** plus the **anti-vibecode engineering standard**. Goal: software that looks and behaves as if a competent product team designed, engineered, tested and maintained it — no generic AI aesthetics, no fake functionality, no unverified claims, no test inflation.

## Resources in this folder

| File | Purpose |
|------|---------|
| `anti-vibecode-guide.md` | Full standard: visual design (§1–2 incl. design process), layout/a11y, SEO, performance, security, testing policy (§22), audit smells (§28), DoD (§31) |
| `anti-vibecode-prompt.md` | Portable instruction set for sessions where this repo is not present |
| `anti-vibecode-standard.json` | Machine-readable mirror of the rules, with `governance` and `research` keys |
| `prompts.md` | One prompt per SDD phase (constitution → spec → clarification → plan → tasks → UI design → implementation → validation → change) |

## Authority hierarchy

When working inside the base (or a project cloned from it), this order decides conflicts:

1. User request (scope changes must be reflected in the spec before implementation).
2. Approved constitution (`docs/constitution.md`).
3. Approved spec and plan of the active feature.
4. `AGENTS.md` — general operational rules.
5. `anti-vibecode-guide.md` + `anti-vibecode-standard.json` (this folder) — quality guardrails.
6. Role and reference docs (`docs/role.md`, `docs/web-prompts.md`, `docs/references.md`) — never higher authority.

Unresolved conflict about security, data integrity or behavior: **stop and ask** with `[NEEDS DECISION]`.

## Workflow: SDD in 7 phases

Constitution → Spec → Clarification → Plan → Tasks → Implementation → Validation. UI features add a **UI Design** step before implementation (see below).

- Use the matching prompt from `prompts.md`; one phase at a time; **human approval gates every phase**.
- Each phase produces an artifact: `docs/constitution.md`, `specs/NNN-*/spec.md`, `plan.md`, `tasks.md`, code + verification, RF-by-RF verdict.
- **Work classification:** new feature/behavior change (needs approved RF) · bug/regression (reproduce → root cause → smallest fix) · refactor (no behavior change, evidence required) · docs/config/tooling (justified by approved task or technical decision). Traceability applies to **behavior changes**, not to every supporting file.
- Once a plan (or a task range) is approved, execute it without stopping after every task — unless scope changes or a blocking decision appears.

## Verification and testing (value policy)

Verification must be appropriate to the type of change. A test exists **only if it can fail because of a real regression that matters**:

- Prioritize critical processes: data/persistence, money, auth/authorization, security boundaries, core business rules, their error handling, and e2e of critical user journeys.
- Merge tests that share setup or scenario into **short** parametrized/table-driven tests — one test per scenario, never per implementation detail. Merging must not create long or slow tests.
- Never write render-only tests, getter tests, or tests that merely confirm a third-party library works.
- UI, docs, configuration and infrastructure RFs may use alternative evidence (checklist pass, review, build output, recorded manual verification).
- Warning sign: suite growing linearly with every RF → redesign the tests, do not add more.
- No claim of "done/verified/fixed" without evidence.

## UI work

1. **Load the `frontend-ui-engineering` skill first** (skill tool in OpenCode; if unavailable, follow the design sections of `anti-vibecode-guide.md`).
2. Design process before styling: design tokens → semantic layout → states (loading/empty/error/success/unauthorized/offline) → meaning-based components → polish (typography, spacing, intentional motion).
3. Guardrail is intentionality, not prohibition (guide §1.1): elegant, modern, polished designs with effects are welcome when they communicate something real; never decoration as filler.
4. Verify: states, routes, responsive behavior, accessibility (WCAG 2.2 baseline).

## Definition of done (essentials)

Requested behavior works · business rules correct · zero fake functionality · intentional visual hierarchy and consistent tokens · accessibility basics · routes/404 work · security boundaries respected (server-side auth, no secrets in client) · errors recoverable · performance reasonable · build/tests green where configured · no dead code or meaningless abstractions in changed areas.

## Using this skill outside the base repository

- The four bundled files are the portable standard; the folder is self-contained — copy it to another machine/tool as-is.
- For a fresh project without the base: create `src/`, `tests/`, `specs/`, `docs/constitution.md` and an `AGENTS.md` with the hierarchy above, then run the 7 phases.
- Spec/plan/task templates live in the base repo (`specs/001-nombre-feature-mvp/`); reproduce the same sections if starting bare (EARS-numbered RFs, RF→module→verification mapping, "Done when:" per task).

## Installation in other tools

| Tool | Where |
|------|-------|
| OpenCode (this repo) | Automatic — `.opencode/skills/` is scanned at startup |
| OpenCode (global) | Copy this folder to `~/.config/opencode/skills/` |
| Claude Code | Copy this folder to `.claude/skills/` (project) or `~/.claude/skills/` (global) |
| Codex CLI / tools without skills | Use `AGENTS.md` as the contract and `anti-vibecode-prompt.md` as the portable instruction set |

Restart OpenCode after adding or changing skills; running sessions keep the old configuration until restart.
