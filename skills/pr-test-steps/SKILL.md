---
name: pr-test-steps
description: Given a PR (or its diff) and the task's acceptance contract, produce a runnable, copy-pasteable manual QA script a human can execute step by step. On-demand, callable any time before merge.
---

# pr-test-steps — manual QA script generation

Use whenever a human wants to manually verify a PR before merging — on
demand, any time, independent of whether `cross-review` has run. Produces a
script to execute, not a description of what the code does.

## Procedure
1. Get the diff and its acceptance contract: `sys_os_shell("gh pr diff <pr>")`
   plus the originating issue/task's contract (registry entry, or
   `sys_os_shell("gh issue view <n>")`).
2. Read the diff for every user-observable behavior change — new/changed UI,
   API responses, side effects, error messages, notifications. Ignore
   internal refactors with no observable difference; those get no QA step.
3. Write one QA step per observable behavior, happy path first, then the
   edge cases the acceptance contract explicitly calls out. Each step names
   the exact precondition/setup, the exact action (a command to run, a UI
   click sequence, a message to send), and the exact expected result. Never
   write a vague step like "verify it works" — a human must be able to
   follow it with zero interpretation.
4. Order steps so each can be executed independently where possible; call
   out explicitly when a step depends on a prior step's state (e.g. "using
   the same approval message from step 2").
5. Present the finished script to the human. This skill's output IS the
   deliverable — no loop, no gate, no further dispatch. The human executes
   it (or doesn't) at their own discretion.

## Notes
- Distinct from `cross-review`'s automated tests/lint/typecheck/coverage/
  integration gates — this produces a script for a HUMAN to run by hand, for
  behavior those gates can't observe (visual correctness, an actual
  Telegram/UI round-trip, a third-party API's real response).
- If the acceptance contract is missing or thin, say so explicitly rather
  than inventing scope — ask the human for the contract, or infer the
  minimum from the diff and clearly label those steps as inferred.
- Callable at any point in the pipeline — before `cross-review`, after it, or
  instead of it for a PR the human wants to eyeball personally first.
