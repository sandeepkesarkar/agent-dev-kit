---
name: security-review
description: On-demand security review of a PR (wraps Claude Code's built-in /security-review) or of the whole system (custom sweep using the same vulnerability taxonomy, since the built-in skill has no whole-repo mode). PR-scoped and whole-system modes.
---

# security-review — PR-scoped wrap, whole-system custom sweep

Two distinct modes sharing one vulnerability taxonomy. Checked against
Claude Code's actual built-in `/security-review` skill before building
anything (see Notes) — PR-scoped mode wraps it directly; whole-system mode
is custom, because the built-in skill has no whole-repo mode at all.

## Shared vulnerability taxonomy (both modes)
Input validation (SQL/command/XXE/NoSQL injection, path traversal); authn/
authz (bypass, privilege escalation, session flaws, JWT vulnerabilities);
crypto & secrets (hardcoded credentials, weak algorithms); injection & code
execution (RCE, pickle/YAML/eval injection, XSS); data exposure (sensitive
logging, PII, API/debug-info leakage). Explicitly excluded, matching the
built-in skill's own scope discipline — don't expand it here: DoS, rate
limiting, memory safety in memory-safe languages, test-only code issues.

## Procedure — PR-scoped mode (default)
1. Dispatch a `claude_code` sub-agent — NOT vendor-flexible, since the
   built-in `/security-review` skill only exists in Claude Code —
   `sys_session_send(agent="claude_code",
   title="security-review-<task_slug>", args={purpose: "review", input: "Run
   /security-review against this PR's pending changes."})`, scoped to the
   PR's actual worktree/branch. This skill needs real repo context (its own
   `origin/HEAD` diff, existing-pattern research) — unlike `cross-review`'s
   diff-only independence rule, don't try to hand it just a text diff.
2. Collect the structured report via `sys_read_inbox` — each finding comes
   back as `Vuln N: [CATEGORY]: file:line` with Severity (HIGH/MEDIUM/LOW),
   Confidence (0.0–1.0, pre-filtered to ≥0.8 by the built-in skill itself),
   Description, Exploit Scenario, Recommendation.
3. Treat HIGH and MEDIUM severity as blocking; LOW as a non-blocking
   follow-up in the registry. For each blocking finding, add a fix-task and
   route it back to the implementer's session via `sys_session_send` — same
   convention as `cross-review` step 5. Loop to step 1 once fixed.
4. Report clean when no HIGH/MEDIUM findings remain.

## Procedure — whole-system mode (on-demand, expensive — not run per-PR)
5. Partition the target repo into bounded scopes (top-level modules or
   directories — mirror `investigate`'s decomposition discipline: prefer
   several bounded tasks over one sprawling one).
6. Dispatch one sub-agent per scope, `purpose: "review"`, applying the exact
   shared taxonomy above against the ACTUAL code in that scope — not a diff.
   Whole-system mode exists precisely because PR-scoped review, in both this
   skill and `cross-review`'s Security dimension, never sees code that
   merged before this pipeline existed. Vendor doesn't need to be
   `claude_code` here — this isn't wrapping the built-in skill, it's applying
   the taxonomy directly. Ask for the same structured `Vuln N:` report shape
   as step 2, for consistency.
7. Collect all scopes' reports via `sys_read_inbox`, aggregate, and dedupe
   findings that overlap across scope boundaries (e.g. a shared utility
   module flagged by two different callers' scopes).
8. Present the aggregated report to the human. Whole-system mode does NOT
   auto-loop into fix-tasks the way PR-scoped mode does — findings here can
   span unrelated, already-merged work with no single implementer session to
   route a fix to. The human decides what becomes a new tracked issue.

## Notes
- Checked before building: Claude Code's built-in `/security-review` is
  strictly diff-scoped (current branch vs `origin/HEAD`, hard-required — it
  errors without that remote ref) with NO whole-system mode of any kind.
  That's why whole-system mode here is a custom sweep, not a second wrap —
  there is nothing in the built-in skill to wrap for that half of the
  requirement.
- PR-scoped mode is pinned to `claude_code` regardless of who implemented
  the PR — unlike `cross-review`, cross-vendor independence isn't the axis
  here; the built-in skill's existence on that one vendor is.
- Whole-system mode's per-scope dispatch does NOT need to be `claude_code` —
  any available reviewer can apply the shared taxonomy as an explicit
  checklist, since nothing there depends on the built-in skill mechanically.
- Distinct from `cross-review`'s Security dimension and `adversarial-review`:
  cross-review's dimension is a lighter-weight, always-on OWASP-shaped pass
  on every diff; `adversarial-review` hunts for hostile-input exploits;
  this skill's PR-scoped mode is the deeper, purpose-built vulnerability
  scan; whole-system mode is the only one of the three that ever looks past
  the current diff at all.
- Confidence-filtering at ≥0.8 already happens inside the built-in skill for
  PR-scoped mode — don't re-filter or second-guess its confidence scores,
  parse severity for blocking/non-blocking only.
