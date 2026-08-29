---
name: requirements-gather
description: Gather a feature's requirements from a human via relentless Q&A, read them back for explicit approval, then hand the approved set to speckit for spec/plan/tasks generation.
---

# requirements-gather — front door to the spec-to-merge pipeline

Use when a human describes something they want built, in vague or partial
form. This is the front-door, turn-by-turn interactive skill — everything
downstream (`spec-to-issues`, `fanout`, `cross-review`) is async dispatch the
human walks away from.

## Procedure
1. Ask targeted questions one at a time (or in small, tightly related
   batches) — never a single giant intake form. Cover at minimum: the
   problem/user need this solves, which unit it belongs to (if the consumer
   repo has multiple specifiable units), scope boundaries (what's explicitly
   out), the acceptance signal (how a human will know it's done), and any
   existing precedent to follow (only if the human references one — don't
   assume one exists).
2. Keep looping — follow-up questions on ambiguous or incomplete answers —
   until either (a) no material ambiguity remains, or (b) a round cap is hit
   (default 8 rounds; ask the human whether to continue past it rather than
   silently stopping). Relentless means thorough, not performative — don't
   pad with question rounds once the shape is genuinely clear.
3. For anything still ambiguous when the loop ends, don't block indefinitely:
   state it as an explicit ASSUMPTION and carry it into the read-back.
4. Compose the full requirement set — confirmed answers plus explicit
   assumptions — into a single structured read-back and present it to the
   human verbatim: problem, scope, acceptance criteria, assumptions, open
   risks. Never compress it down to fragments; read back what was actually
   decided.
5. Wait for explicit approval. Treat anything short of an explicit yes
   ("approved", "yes", "go", or equivalent) as a request for changes — loop
   back to step 1 for whatever was flagged, then re-present the FULL read-back
   again (not just the delta) before asking again.
6. Once approved, hand off to speckit: dispatch a `claude_code` sub-agent to
   drive `speckit-specify` → `speckit-clarify` → `speckit-plan` →
   `speckit-tasks` against the approved requirement set —
   `sys_session_send(agent="claude_code", title="specify-<feature_slug>",
   args={purpose: "specify", input: "<approved requirement read-back
   verbatim>. Report back in exactly one of two shapes: (a) 'PAUSED:' followed
   by every [NEEDS CLARIFICATION] marker speckit-clarify raised, verbatim,
   with no other work done past that point, or (b) 'COMPLETE:' followed by
   the paths to spec.md, plan.md, sequence-diagram.md, tasks.md, and
   features/*.feature. Never mix the two or report partial completion under
   'COMPLETE'."})`. Emit this call in the same turn the approval lands —
   never end a turn having only announced the handoff. There is no platform
   status field distinguishing these two outcomes (`sys_read_inbox` only
   delivers completed payloads, and `sys_session_get_info`'s "outstanding
   approval prompts" is the unrelated cost-budget checkpoint mechanism) — the
   PAUSED/COMPLETE prefix in the report text IS the signal, the same
   convention `cross-review` already uses for its reviewer's
   blocking/non-blocking text report.
7. Collect the result via `sys_read_inbox` and read which prefix it used:
   - **`PAUSED:`** — relay the listed markers to the human verbatim in THIS
     chat as a short, scoped follow-up — don't re-run the full step 1–5 loop,
     it's a targeted question the specify chain raised, not a fresh intake.
     Once answered, re-dispatch the SAME sub-agent conversation (same
     `title`, or address by `session_id`) with the answer via
     `sys_session_send` — reuse, don't spawn a fresh worker, so the chain
     resumes from where `speckit-clarify` paused (continuing a named session
     appends a new turn to its existing conversation rather than starting
     over — the same mechanism `cross-review` step 5 relies on for its
     fix-task loop). Loop this step until a `COMPLETE:` report comes back.
   - **`COMPLETE:`** — `tasks.md` (plus `spec.md`, `plan.md`,
     `sequence-diagram.md`, `features/*.feature`) is done.
8. When a `COMPLETE:` report comes back, route `tasks.md` to `spec-to-issues`
   for an issue-breakdown proposal and a second human approval gate —
   distinct from this skill's approval in step 5. That one approves *what* to
   build; the `spec-to-issues` gate approves *how it's broken up* into
   issues.

## Notes
- This skill never itself calls `git`, `gh`, or touches the target repo — it
  only produces an approved requirement set and dispatches the specify chain.
- If the human already has a written spec/PRD, skip to step 4 (read it back
  against the same coverage checklist) rather than re-interrogating a
  document that's already fully specified.
- The round cap and coverage checklist here are deliberately generic; a
  consumer repo with its own multi-unit conventions (e.g. a monorepo with a
  shared platform plus per-client trees) should ask the unit question first,
  before anything else.
- Distinct from `spec-to-issues` (turns an approved spec into issues) and
  from the on-demand review skills (`pr-test-steps`, `adversarial-review`,
  `security-review`) — this skill's only job is producing one approved,
  unambiguous requirement set.
- Confirmed against the actual dispatch tools: there is no built-in
  paused-vs-finished completion status. The `PAUSED:`/`COMPLETE:` text
  prefix in step 6's `input` and step 7's parse of it is the entire
  mechanism — get that instruction wrong in the dispatch and there is
  nothing else catching a stalled chain.
- A bounce-back round in step 7 is a targeted, scoped question forwarded
  verbatim from `speckit-clarify` — it is NOT a reason to re-run this skill's
  full step 1–5 loop or re-approve the whole requirement set again.
