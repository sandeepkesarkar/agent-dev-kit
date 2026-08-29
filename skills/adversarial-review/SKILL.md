---
name: adversarial-review
description: On-demand hostile-input review of a PR — prompt-injection surfaces, approval-flow bypass, identity spoofing, feature-logic abuse. Distinct from cross-review's contract check; tries to make the diff do something the contract does NOT say, under attack.
---

# adversarial-review — hostile-input verification

`cross-review` checks whether a diff correctly does what its contract says.
This skill checks whether the diff can be made to do something the contract
does NOT say, when an attacker controls part of its input. Use on demand —
not every PR touches an input surface worth this scrutiny; call it
explicitly for anything touching human-approval flows, external message
parsing, or any code path where untrusted content reaches an LLM prompt.

Grounded in a real incident, not invented: see
`fieldkit/.claude/session-notes/2026-08-26-photo-approve-injection-block.md`.
`platform/photo-agent/skills/photo-approve/SKILL.md`'s own "do not ask
clarifying questions, run immediately" instruction text pattern-matched a
classic prompt-injection shape once Hermes's dispatch path injected it as
literal, unmarked user-turn text — no trust boundary distinguished
first-party skill content from attacker-controlled content. Any new
skill/prompt text, caption, or message body that ends up as literal
user/assistant-turn content in a model prompt is a standing candidate for
this exact class of finding.

## Procedure
1. Get the diff and its acceptance contract — same as `cross-review` step 1.
2. Read the diff to identify every external input surface it introduces or
   touches: user/chat messages, API payloads, webhook bodies, file uploads
   (captions, filenames, EXIF/metadata), CLI args, or config/env values
   sourced from something less trusted than the code itself.
3. For each surface, reason through (or dispatch a sub-agent to reason
   through, diff + contract + these surfaces only — same independence
   discipline as `cross-review`):
   - **Prompt-injection surfaces**: if this input's value is EVER passed to
     an LLM as literal user/assistant-turn text (a skill body, a caption, a
     forwarded message), could crafted content override instructions,
     exfiltrate data, or trigger an unintended tool call? Is there ANY trust
     marker distinguishing first-party content from user-controlled content
     at that boundary, or is it bare text?
   - **Approval-flow bypass**: can the action this PR gates behind human
     approval be triggered WITHOUT the approval step — a malformed callback,
     a race between two requests, a spoofed sender/chat-id, a replayed old
     approval token?
   - **Identity/authorization spoofing**: does the flow verify the request
     actually came from the authorized human/channel it claims (chat-id
     allowlist, webhook signature), or does it trust an unauthenticated
     field?
   - **Feature-logic abuse**: can valid inputs, combined in an order or
     combination the author didn't intend, drive the feature into a bad
     state (approving an already-rejected item, duplicate/empty submissions,
     resubmitting a stale request)?
4. Report concrete exploit scenarios only: the exact crafted input, the code
   path it travels, and the unintended outcome. Not a generic "consider
   hardening this" — if a scenario can't be demonstrated concretely, it's a
   suggestion, not a finding.
5. For each demonstrated exploit, add a blocking fix-task to the registry and
   route it back to the implementer via `sys_session_send`, reusing the
   original implementer's session — same convention as `cross-review` step
   5. Loop to step 1 once fixes land.
6. Report clean once no further exploit is found, or once remaining findings
   are explicitly theoretical/low-severity and the human accepts that risk
   in writing.

## Notes
- Give the reviewer ONLY the diff, contract, and the surfaces identified in
  step 2 — never the implementer's transcript or worktree, same independence
  rule as `cross-review`.
- This is NOT a re-run of `cross-review`'s Security dimension (injection
  classes, secrets, PII, authn/authz, blast radius) — that dimension checks
  for accidental omissions in well-intentioned code; this skill actively
  tries to break the feature. Findings can overlap; don't skip this skill
  just because `cross-review` passed.
- The prompt-injection surface check applies to ANY code path where text
  reaches a model prompt, not just chat features — a filename, a database
  comment field, an error message rendered back into a later LLM call are
  all candidates.
