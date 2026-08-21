# Spec: GitHub Task Workflow

**Status**: Reference spec — the generic workflow shape this repo ships as a default

## Purpose

All work — code and non-code alike (specs, docs, content) — is created as
GitHub issues and executed by agents through GitHub. Human judgment enters at
exactly two points: **approving the issue breakdown**, and **reviewing/merging
PRs**. Everything else — implementation, cross-vendor review, narration — is
delegated to agents.

## Scope

- Applies to any repo that adopts this workflow (see this repo's README for
  the distribution model — global skill symlink + pinned agent-bundle
  submodule).
- Applies to **all** work types, not just code: specs, docs, and content flow
  through the same issue-based process, distinguished only by label.

## Implementation status

This spec describes the target shape of the full workflow. This repo
currently ships the **execution and review** half — `agent-ready` issue →
worker agent → PR → cross-vendor review (see `skills/fanout/SKILL.md` and
`skills/cross-review/SKILL.md`) → human merge. It does **not** yet ship the
**decomposition** half (spec → proposed issue breakdown → human approval →
issues filed). Everywhere below that reads as a MUST for decomposition
(FR-001, FR-009, SC-001) describes the intended target, not a shipped
capability — see the Bootstrapping Note at the bottom of this spec. Treat
those specific items as roadmap requirements; everything else in this spec
(labels, worker pickup, PR contents, human-merge-only, cross-vendor review)
is implemented and shipped in this repo today.

## Out of Scope (this iteration)

Scoped to the **poller/automation** iteration of this workflow — i.e. what a
scheduled worker agent does or doesn't do on its own. This is not a
statement about the orchestrator this repo ships as its reference
implementation: Polly (`config.yaml` + `agents/`) is itself a multi-worker
orchestrator with routing and model-advice logic, and shipping it is not a
contradiction of the items below — those describe a *future automated
triage layer* sitting in front of the human-approved issue queue, not the
existing dispatch-to-a-declared-roster orchestrator.

- Event-driven pickup (webhooks/GitHub Actions) — later evolution of the
  pickup mechanism.
- An orchestrator agent that autonomously triages and dispatches work
  *without* a human first approving the issue breakdown — later evolution.
- Auto-merge of any kind.
- Multi-model routing (including local models) — routing logic should not
  preclude this later, but it isn't built now.

## Roles

- **Human maintainer**: approves issue breakdowns before they're created;
  reviews and merges every PR.
- **Decomposition agent**: reads a spec, proposes an issue breakdown, waits
  for approval before creating anything.
- **Worker agent**: polls for `agent-ready` issues, does the work, opens a PR,
  narrates.

## Scenarios

### 1. Spec → issues (P1)
Given an approved spec doc, when the maintainer invokes the "split spec into
issues" skill, then it proposes a breakdown (titles, bodies, labels,
acceptance criteria) for review — no issues exist on GitHub yet.
Given the maintainer approves the breakdown, when they confirm, then the
skill creates the issues with the correct labels.

### 2. Agent picks up work (P1)
Given an issue labeled `agent-ready`, when the polling agent runs (on
whatever cadence the consumer wires up — hourly cron/launchd, a CI schedule,
or a manual trigger), then it claims the issue, does the work, and opens a PR
that references the issue.

### 3. Human reviews and merges (P1)
Given an open PR from a worker agent, when the maintainer reviews it, then
they can read a one-line summary comment on the issue and a full PR
description, see tests included for any code change, see Mermaid diagrams
wherever the change benefits from one (GitHub renders these natively), and —
for code PRs — see a cross-vendor review comment covering Engineering and
Security already posted. The maintainer merges by hand; there is no
auto-merge path.

### 4. Issue sizing (P2)
Given a spec being decomposed, each resulting issue's deliverable must be
reviewable by a human in under 15 minutes. This is the sizing heuristic the
decomposition agent applies.

## Functional Requirements

- **FR-001** *(not yet implemented — see Implementation status above)*: The
  decomposition agent MUST propose an issue breakdown from a spec and MUST
  NOT create any issue without explicit human approval of the breakdown.
- **FR-002**: Every issue MUST carry at least one type label (`spec`, `code`,
  `docs`, `content`) plus applicable workflow-state labels (`agent-ready`,
  `needs-approval`) — see [labels.md](labels.md).
- **FR-003**: The label glossary MUST be centralized in this repo's
  `specs/labels.md`; consumer repos reference it rather than keeping their
  own copy.
- **FR-004**: The worker agent MUST run on some polling cadence appropriate to
  the consumer's environment, with a manual trigger also supported for
  on-demand checks. This spec is deliberately silent on the concrete scheduler
  (cron, launchd, a CI cron trigger, a hosted scheduler) — that choice is
  environment-specific and belongs in the consumer repo, not here.
- **FR-005**: All merges MUST be performed by a human. No automated merging,
  in any repo, for any issue type.
- **FR-006**: Every PR from a worker agent MUST include: a one-line summary
  comment on the source issue, a full PR description, tests for any code
  change, and Mermaid diagrams wherever the change benefits from one.
- **FR-007**: Model routing MUST default to this repo's shipped default
  (Claude implements, Codex reviews — see the root `config.yaml` and
  `skills/cross-review/SKILL.md`), and MUST be architected so multi-vendor /
  multi-model routing can be extended later without a workflow redesign.
- **FR-008**: "Detailed comments," "tests included" (code issues), and
  "Mermaid diagrams where applicable" MUST appear as standing acceptance
  criteria on every issue the decomposition agent creates — not just as an
  informal norm.
- **FR-009** *(not yet implemented — see Implementation status above)*: The
  spec→issues capability MUST be packaged as a reusable, invocable
  skill/command — the front door to this workflow — usable from any consumer
  repo.
- **FR-010**: The workflow MUST handle non-code deliverables (specs, docs,
  content) through the same issue-based flow, distinguished only by label.
- **FR-011**: Every code PR MUST carry a cross-vendor review (from a vendor
  other than the implementer, covering at minimum Engineering and Security)
  before being labeled `needs-approval`. See `skills/cross-review/SKILL.md`
  for the shipped default (Codex reviews Claude's diffs) and its explicit
  fallback rule.

## Key Entities

- **Issue** — unit of work; carries type + state labels, acceptance criteria,
  and a link back to the spec it was decomposed from.
- **Label glossary** — canonical label list and meaning; single source of
  truth in `specs/labels.md`.
- **Worker agent** — the polling process that claims `agent-ready` issues and
  produces PRs.
- **Decomposition skill** — turns an approved spec into a proposed issue
  breakdown; nothing is created until the human approves it.

## Success Criteria

- **SC-001** *(not yet met — depends on FR-001/FR-009, not yet implemented)*:
  A spec goes from "approved" to "issues filed on GitHub" via a single skill
  invocation plus one human approval step.
- **SC-002**: 100% of agent-authored PRs carry the required narration (issue
  comment + PR description) before merge.
- **SC-003**: Every merged PR was reviewable in under 15 minutes (spot-checked
  against the sizing heuristic).
- **SC-004**: Zero auto-merges — every merge in the GitHub audit log has a
  human actor.
- **SC-005**: This spec is itself decomposable into issues and executable
  through the workflow it describes (dogfooding).
- **SC-006**: Zero code PRs reach `needs-approval` without a cross-vendor
  review comment already attached.

## Assumptions

- Issues and PRs live on the consumer's existing GitHub repo — no separate
  ticketing system.
- The worker agent runs via an Omnigent + agent-bundle setup (this repo's
  `config.yaml` + `agents/`) with `gh` CLI access and repo write permissions.
- The concrete polling cadence (hourly, on every push, manual-only, etc.) is
  a consumer-environment decision, not part of this spec.
- This spec assumes no prior workflow in the consumer repo; issue-based
  execution is additive.

## Bootstrapping Note

The decomposition skill described in FR-001/FR-009 doesn't exist in this
repo yet — it's a known gap, not an oversight (see Implementation status
above). Until it's built, a spec's first pass into issues has to be done by
hand, or with ad-hoc agent help but no packaged skill. Once the skill exists
here, it becomes the front door this workflow is designed around; until
then, everything downstream of "an `agent-ready` issue exists" (worker
pickup, PR, cross-vendor review, human merge) works today regardless of how
that issue got created.
