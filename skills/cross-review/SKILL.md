---
name: cross-review
description: Verify an implementer's diff with an INDEPENDENT, different-vendor sub-agent (diff plus contract only); turn blocking issues into fix-tasks and loop until clean.
---

# cross-review — independent verification

The implementer never signs off on its own work — a different vendor does,
and review is a sub-agent that returns a structured report, not a transcript
anyone needs to read through.

This bundle ships with an opinionated default: **Claude implements, Codex
reviews.** Same-vendor self-review is never allowed — the reviewer must
always be a different vendor than the implementer. Codex is pinned as the
default reviewer (not picked opportunistically from whatever's available)
because a fixed reviewer identity makes review quality and behavior
predictable across runs; see Procedure step 3 for the explicit,
non-silent fallback when Codex isn't available.

## Procedure
1. Get the task's diff — `sys_os_shell("gh pr diff <pr>")` (or
   `git -C .worktrees/<task_id> diff main...HEAD`).
2. Run the deterministic gates first — tests / lint / typecheck via
   `sys_os_shell`. If red, re-dispatch the implementer to drive it green first;
   don't involve the reviewer yet.
   If a pytest result's count must be recorded or reconciled, collect ground
   truth with `python -m pytest --collect-only -q <same files>` against the
   exact file set/command/commit the implementer reported. Never use
   `grep -c 'def test_'` as a pytest count: it counts functions, not collected
   cases, and misses parametrized case expansion.
3. Dispatch **`codex`** as reviewer — pinned by default, not chosen from the
   available roster. Exception: if the implementer itself was `codex`, or
   `codex` isn't in this run's roster preflight, fall back to any other
   AVAILABLE different-vendor worker (`claude_code`, `opencode`, `cursor`,
   `hermes`, `agy`, `pi`) and say so explicitly in your report — a silent
   substitution defeats the point of pinning a reviewer in the first place.
   Use a task-based title such as `review-auth-refactor`, never the raw vendor
   name:
   `sys_session_send(agent="codex", title="review-<task_slug>",
   args={purpose: "review", input: "<the diff> + <the acceptance contract> +
   <the Standing review dimensions below>. Review against BOTH the
   task-specific contract AND every dimension currently listed under
   Standing review dimensions. Report blocking / non-blocking / suggestions,
   grouped by dimension. Do not edit code."})`. Give it the diff as text — do
   NOT point it at the implementer's worktree. Fetch the diff and emit the
   `sys_session_send` call in the SAME turn you decide to review — never end a
   turn having only announced "I'll load cross-review and fetch the diff" with
   no tool call (that dropped turn stalls the run; nothing dispatches and no
   inbox wake arrives). Once the reviewer dispatch is in flight, end your turn;
   collect the inbox-delivered structured report with `sys_read_inbox` when it
   returns. Use `sys_session_get_history` only to debug an empty or unclear
   review result.
4. The reviewer SURFACES issues; it does not fix them.
5. For each **blocking** issue: add a fix-task to the registry scoped to the
   same worktree, and send the concrete fixes back to the SAME implementer
   conversation via `sys_session_send` — reuse the original implementer's
   `agent` + `title` (or address it by `session_id`) with
   `purpose: "implement"`, so the worker keeps its worktree/branch context and
   updates its existing PR. A new title would spawn a fresh worker with no
   memory of the task. Then loop to step 1.
6. When gates are green AND there are zero blocking issues, the PR passes
   review — mark it ready in the registry (with its PR URL) and leave it for
   the human to merge. The orchestrator does NOT merge it.
7. If the contract can't be satisfied after a few loops, stop and escalate to
   the user with specifics.

## Standing review dimensions

Applied on every dispatch, in addition to (never instead of) the task's own
acceptance contract. Extensible: add a new numbered dimension below as a new
need surfaces — no other change to this skill or to the orchestrator's config
is needed for that to take effect on the next dispatch.

### 1. Engineering
- **Correctness** — logic errors, edge cases, race conditions, error handling
  that swallows or misreports failure.
- **Simplification / reuse** — unneeded abstraction, duplicated logic that
  should call existing code, over-engineering relative to what the task asked.
- **Efficiency** — avoidable N+1s, redundant work, wrong complexity for the
  data size involved.
- **Test coverage** — new behavior without a test exercising it; a test that
  doesn't actually assert the thing it claims to.

### 2. Security
Baseline OWASP-shaped checks, plus this framework's own governance requirements:
- **Injection classes** — command injection, SQL injection, XSS, path
  traversal, unsafe deserialization.
- **Secrets handling** — credentials/tokens/keys logged, printed, committed,
  or passed as CLI args instead of env/file with restricted permissions.
- **PII handling** — personal data (names, contact info, location/EXIF, chat
  content) logged or persisted somewhere it shouldn't be.
- **Authn/authz** — missing or bypassable checks on who can trigger an action
  (e.g. an admin-allowlist checked once and cached past its validity, a
  webhook without signature verification).
- **Blast radius** — anything destructive (data deletion, force-push,
  irreversible external API calls) that isn't gated behind human approval
  where the task calls for one.

## Notes
- Cross-review requires a reviewer from a DIFFERENT vendor than the implementer,
  so it needs at least two AVAILABLE workers (per the roster preflight). If
  only one worker — or only one vendor that can review this implementer's PR —
  is available on the machine, you CANNOT run independent cross-vendor review:
  don't dispatch a reviewer that can't boot, say so explicitly, and pull in the
  human at the plan gate.
- Give the reviewer ONLY the diff + contract — never the implementer's
  transcript or worktree. The cross-vendor independence is the whole point.
- Review is a coding sub-agent (`claude_code`/`codex`/`opencode`/`cursor`/`hermes`/`agy`/`pi`) dispatched with
  `purpose: "review"` — a DIFFERENT vendor from the one that built the diff. It
  reports issues and never edits; only the implementer opens a PR, so a stray
  reviewer edit never reaches the deliverable.
- Non-blocking issues / suggestions go in the registry as follow-ups; they
  don't block the PR.
