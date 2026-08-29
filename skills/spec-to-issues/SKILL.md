---
name: spec-to-issues
description: Turn an approved spec's tasks.md into a proposed, human-approved GitHub issue breakdown — sized for a 15-minute review, labeled per the canonical glossary, and ordered so fanout can safely parallelize disjoint work.
---

# spec-to-issues — decomposition, the flagged gap this repo ships to fill

Use once `tasks.md` (and its sibling `spec.md`/`plan.md`/`features/*.feature`)
exists for an approved feature. Proposes the issue breakdown and waits for
explicit human approval before creating anything on GitHub — this is FR-001
in `specs/github-task-workflow.md`, this repo's own previously-flagged,
now-filled gap.

## Procedure
1. Read `tasks.md`, `spec.md`, `plan.md`, and `features/*.feature` for the
   feature. Group tasks into candidate issues:
   - Default 1:1 (one task → one issue) unless multiple tasks are tightly
     coupled (same file(s), can't be reviewed independently) — group those
     1:many under a single issue.
   - Apply the sizing heuristic: every issue's deliverable must be
     reviewable by a human in under 15 minutes. Split an oversized task into
     multiple issues rather than shipping one large diff; never merge tasks
     together just to cut issue count if doing so breaks the 15-minute bound.
2. Compute dependency ordering from each candidate issue's expected file
   footprint (cross-reference `tasks.md`'s own task dependencies plus
   `plan.md`/`spec.md` for touched files). Mark any pair of issues that touch
   overlapping files as sequential, not parallel-safe; everything else is
   fanout-parallel-safe. This ordering is what `fanout` consumes to decide
   what it can dispatch in the same wave.
3. Assign labels per `specs/labels.md`'s glossary — exactly one work-type
   label (`spec`/`code`/`docs`/`content`) per issue, plus `needs-approval`
   (not `agent-ready` yet — see step 8). Never invent a label outside the
   glossary; propose a glossary change there first if a genuinely new
   category is needed.
4. Attach the standing acceptance criteria to every issue's body explicitly,
   not as an informal norm: detailed comments, tests included (code issues),
   and Mermaid diagrams wherever the change benefits from one (FR-008 in
   `specs/github-task-workflow.md`).
5. Present the full proposed breakdown to the human as one read-back — every
   issue's title, body, labels, acceptance criteria, and the
   dependency/parallelism ordering from step 2. This is a SECOND, distinct
   approval gate from `requirements-gather`'s: that one approved *what* to
   build; this one approves *how it's split into issues*. Zero issues exist
   on GitHub until this is approved.
6. Wait for explicit approval, same convention as `requirements-gather` —
   anything short of an explicit yes is a request for changes; loop back to
   step 1 for whatever was flagged, then re-present the FULL breakdown again
   before asking again.
7. Once approved, create the issues, one `sys_os_shell` call per issue:
   `gh issue create --repo <owner/repo> --title '<title>' --body '<body>'
   --label '<type-label>' --label 'needs-approval'`. Confirm the target repo
   matches the remote before creating anything — never create issues in a
   repo that doesn't match (mirrors `speckit-taskstoissues`'s own caution).
8. Once every issue is filed, flip each from `needs-approval` to
   `agent-ready`: `sys_os_shell("gh issue edit <n> --remove-label
   needs-approval --add-label agent-ready")`. This is the signal the poller
   (or a direct `fanout` dispatch) picks up.
9. Report back to the human: the created issue URLs, grouped by which
   fanout wave they belong to per the dependency ordering from step 2.

## Notes
- This skill never dispatches implementation itself — it only creates and
  labels issues. Handing parallel-safe issues to `fanout` (or leaving them
  for the poller) is a separate step, not part of this skill's job.
- `agent-ready` is applied only AFTER human approval (step 8), never at
  creation time (step 7) — this is what makes the approval gate real rather
  than cosmetic. An issue that's `agent-ready` the moment it's created has
  skipped the gate FR-001 requires.
- The dependency ordering from step 2 is advisory to `fanout`, not enforced
  by GitHub itself — nothing stops a human or another tool from dispatching
  two file-overlapping issues in parallel by hand. State the ordering
  clearly in both the read-back and the final report so that risk is
  visible, not silent.
- Non-code deliverables (specs, docs, content) flow through the exact same
  steps, distinguished only by their work-type label (FR-010) — don't
  special-case them into a different procedure.
- If `tasks.md` already reflects a single, small, unambiguous piece of work,
  steps 1–2 may collapse to one issue — don't manufacture a breakdown where
  none is needed.
