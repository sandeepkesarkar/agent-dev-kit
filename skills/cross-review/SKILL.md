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
2. Run the deterministic gates first — tests / lint / typecheck, diff
   coverage, and integration tests, all via `sys_os_shell`, all BEFORE the
   reviewer is ever dispatched:
   - **Tests / lint / typecheck**: whatever the repo's own commands are.
   - **Diff coverage** (not whole-repo coverage — a PR can't retroactively
     cover legacy code it didn't touch, and this repo's own consumers may
     have large, unrelated baselines): `coverage run -m pytest && coverage
     xml && diff-cover coverage.xml --compare-branch=main --fail-under=97`
     (the `diff-cover` package computes percent-covered specifically over the
     PR's added/changed lines). Gate at 97%.
   - **Integration tests**: run the project's integration suite if one
     exists (e.g. `pytest tests/integration -v`) — check for a documented
     integration-test entrypoint in the repo rather than guessing at a path.
   If ANY of these are red or below threshold, re-dispatch the implementer to
   drive it green first; don't involve the reviewer yet.
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
  doesn't actually assert the thing it claims to. Diff coverage must be
  ≥97% of the PR's added/changed lines — this is the numeric gate enforced
  in Procedure step 2, not a separate qualitative judgment call.

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

### 3. Python engineering
Applies whenever the diff touches `.py` files. Deliberately a fixed, bounded
checklist of concrete, mechanically checkable items — not an open-ended
"check for best practices" instruction. Extend it by adding a new bullet
here when a NEW category proves worth catching repeatedly; don't let the
reviewer improvise beyond this list for this dimension.
- **Mutable default arguments** — `def f(x=[]):` / `def f(x={}):`. Must
  default to `None` and initialize inside the function body.
- **Bare/broad exception handling** — `except:` or `except Exception:` that
  swallows an error with no re-raise, no logging, and no specific handling.
  Catch the narrowest exception type the call can actually raise.
- **Exception chaining** — re-raising inside an `except` block without
  `raise NewError(...) from e`; a bare `raise NewError(...)` there discards
  the original traceback.
- **Resource handling** — files, sockets, DB connections, or locks acquired
  without a `with` block, relying on manual `.close()`/`.release()` that gets
  skipped on an exception path.
- **Missing type hints** — new/changed public functions or methods lack type
  hints in a file/module that otherwise uses them consistently. Check
  neighboring code in the same file first — don't impose hints on a codebase
  that doesn't use them.
- **`is` vs `==`** — comparing to `None`, `True`, `False`, or a singleton
  with `==` instead of `is`.
- **Mutable global/module-level state** — introduced without a documented
  reason; a hidden source of cross-test or cross-request contamination.
- **Blocking calls inside `async def`** — a synchronous blocking call
  (network I/O, disk I/O, `time.sleep`) inside an `async` function with no
  `asyncio.to_thread`/async-client wrapper — stalls the event loop for every
  other concurrent task.
- **`print()` in production code paths** — instead of the project's logger,
  outside CLI entry points and tests.
- **Wildcard imports** — `from module import *` anywhere in the diff.
- **Shadowing builtins** — a variable or parameter named `id`, `type`,
  `list`, `dict`, `str`, etc., in a way that could confuse a later reader or
  break a nearby use of the real builtin.

### 4. Debuggability
Language-agnostic — applies to every diff, not just Python. The goal: a
human (or the next agent) can diagnose a failure from logs alone, without
having to reproduce it locally first. Also fixed and bounded, same rule as
Python engineering above — don't improvise beyond this list for this
dimension:
- **Silent error paths** — an `except`/error-handling branch (any language)
  that suppresses, swallows, or rethrows an error without logging enough to
  diagnose it later: what operation was running, what inputs/ids were
  involved, and what specifically failed.
- **Unlogged external calls and state changes** — a new external API call,
  DB write, queue publish, or other side-effecting operation with no log
  statement marking that it happened. Silence here is what makes production
  incidents undebuggable after the fact.
- **Context-free log messages** — a log statement that says an event
  happened but omits the identifying data (task/request/entity id, the
  specific input) needed to correlate it with one occurrence among many.
- **Wrong log level** — a genuine failure logged at `debug`/`info` (invisible
  in a production log floor) or a routine, expected event logged at
  `error`/`warning` (trains responders to ignore real alerts).
- **New non-trivial branches with no trace** — a new conditional path with
  meaningfully different behavior (not a one-line guard clause) added with
  no log statement indicating which branch was taken.
- Cross-reference, don't duplicate: secrets/PII showing up IN a log line is
  Security's "Secrets handling"/"PII handling" bullets, not this dimension —
  flag it once, under Security.

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
- Step 2's diff-coverage gate requires the `diff-cover` package available in
  the implementer's environment (`pip install diff-cover`) and a `main`
  branch reachable from the worktree for `--compare-branch`. If either is
  missing, fix the environment rather than skipping the gate — a silently
  skipped coverage gate is worse than a blocked PR.
- Steps 2 (tests/lint/typecheck/diff-coverage/integration) and 3 (Codex
  dispatch) already satisfy R6, R7, and R9 of the pipeline's 11 requirements
  by construction — every PR gets these gates and a cross-vendor review
  before a human ever sees it, in that fixed order, with no separate
  on-demand skill a model could skip invoking.
