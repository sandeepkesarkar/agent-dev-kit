# agent-dev-kit

A spec-first, small-PR, cross-vendor-reviewed workflow for getting AI coding
agents to do real work safely — plus a working reference implementation of
that workflow on top of [Omnigent](https://github.com/omnigent-ai/omnigent)
and its Polly orchestrator.

## The pattern

The core idea is independent of any specific tool:

1. **Spec-first decomposition.** Work starts as an approved spec, which a
   decomposition step breaks into small, independently reviewable units
   (GitHub issues). Nothing is created without a human approving the
   breakdown first.
2. **GitHub issues + labels as the task ledger.** Every unit of work — code,
   docs, specs, or other content — is a labeled GitHub issue. Labels encode
   both *type* (`code`, `docs`, `spec`, `content`) and *workflow state*
   (`agent-ready`, `in-progress`, `needs-approval`). See
   [`specs/labels.md`](specs/labels.md).
3. **One implementer, one different-vendor reviewer, every PR.** An agent
   implements a task and opens its own PR. A *different* agent — always a
   different vendor, never the implementer reviewing itself — checks that PR
   against its acceptance contract before it's marked ready for human review.
   Same-vendor self-review is never sufficient; cross-vendor review is not an
   optional extra step, it's the actual review gate.
4. **Human-gated merge only.** No automation ever merges a PR. A human reads
   the PR description, the tests, and the cross-vendor review comment, and
   merges by hand — or doesn't.

This repo's shipped default for step 3 is **Claude Code implements, Codex
reviews** — a concrete, opinionated instance of "different vendor reviews,"
not a placeholder. See [`skills/cross-review/SKILL.md`](skills/cross-review/SKILL.md).

Full mechanics — issue lifecycle, sizing heuristics, required PR contents —
are in [`specs/github-task-workflow.md`](specs/github-task-workflow.md).

## Reference implementation: Omnigent / Polly

This repo ships a complete, working implementation of the pattern above using
[Omnigent](https://github.com/omnigent-ai/omnigent)'s Polly multi-agent
orchestrator:

- **`config.yaml`** (repo root) — Polly's own orchestrator config: the
  seven-worker roster, dispatch rules, guardrails.
- **`agents/`** — one sub-agent bundle per coding vendor: `claude_code`,
  `codex`, `opencode`, `cursor`, `hermes`, `agy`, `pi`. Each implements,
  reviews, or explores a scoped task in its own git worktree.
- **`skills/`** — the three orchestration skills Polly composes at runtime:
  - [`cross-review`](skills/cross-review/SKILL.md) — verify a PR's diff with
    an independent, different-vendor sub-agent.
  - [`fanout`](skills/fanout/SKILL.md) — run independent subtasks in
    parallel, each in its own worktree, each opening its own PR.
  - [`investigate`](skills/investigate/SKILL.md) — delegate read-only
    investigation/debugging/audit work and synthesize only from returned
    reports.

Omnigent and Polly are this repo's reference implementation of the general
pattern above, not the point of the repo. Swap in a different orchestrator or
vendor pairing and the same pattern still holds.

## The 3-repo model

This repo is meant to be consumed, not forked per-project:

1. **`agent-dev-kit`** (this repo) — generic, reusable, MIT-licensed, has no
   knowledge of any specific machine, deployment, or budget.
2. **Your personal/org infrastructure repo** — machine-specific and personal
   setup (which machine runs the poller, cost caps, secrets, install paths).
   It consumes this repo exactly like a project repo does; it doesn't fork it.
3. **Your project repos** — the codebases the workflow actually runs
   against. Each one consumes this repo the same way.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full reasoning,
including why skills and agent bundles are distributed differently (an
Omnigent bundle-loader constraint, confirmed from its own parser source).

## Wiring up a consumer repo

Two separate mechanisms, because skills and agent bundles have different
discovery requirements.

### 1. Skills — global symlink (shared across every project on the machine)

Skills use Omnigent's native machine-global skill discovery: anything under
`~/.agents/skills/` is picked up automatically, in any project. One checkout
of this repo's `skills/` serves every project on the machine; updates are a
manual `git pull`, visible everywhere immediately.

```bash
# One-time, per machine — not per project:
git clone https://github.com/<you>/agent-dev-kit.git ~/src/agent-dev-kit
mkdir -p ~/.agents/skills
ln -s ~/src/agent-dev-kit/skills ~/.agents/skills/agent-dev-kit

# Later, to update:
cd ~/src/agent-dev-kit && git pull
```

### 2. Agent bundles — pinned git submodule (per repo)

Omnigent's bundle loader requires a bundle root to physically contain
`config.yaml` at its own top level, with `agents/<name>/config.yaml` as
direct children — no indirection, no parent-walking. A global symlink can't
satisfy that, so agent bundles are vendored per-repo via a submodule instead,
independently pinned:

```bash
# Inside your consumer repo:
git submodule add https://github.com/<you>/agent-dev-kit.git .agents/agent-dev-kit
git submodule update --init

mkdir -p .omnigent
cat > .omnigent/config.yaml <<'EOF'
default_agent: .agents/agent-dev-kit
EOF

git add .gitmodules .agents/agent-dev-kit .omnigent/config.yaml
git commit -m "Wire up agent-dev-kit as the default Omnigent agent bundle"

# Later, to pull in a newer pinned version:
cd .agents/agent-dev-kit && git pull origin main && cd -
git add .agents/agent-dev-kit
git commit -m "Bump agent-dev-kit submodule"
```

Add your own `guardrails.policies.cost_budget` block to `config.yaml` (or a
repo-local override) — this repo ships without one deliberately, since a $
cap is inherently personal to your deployment.

## License

MIT — see [LICENSE](LICENSE).
