# Architecture

## The 3-repo model

This workflow spans three kinds of repo, each with a distinct job:

1. **`agent-dev-kit`** (this repo) — the canonical, generic source. Skills,
   sub-agent bundle configs, and workflow specs, written so a stranger with no
   context on any specific machine or project can adopt them. Nothing here
   knows about any particular deployment, budget, or secret.
2. **A personal/org infrastructure repo** (e.g. an internal `dev-infrastructure`
   repo) — everything machine-specific and personal: which physical or virtual
   machine runs the poller, cost caps, secrets, install paths, cron/launchd
   wiring. That repo *consumes* `agent-dev-kit` the same way any project repo
   does — it does not fork or duplicate this repo's content, it wires up to
   it via the two distribution mechanisms below and then layers its own
   deltas (e.g. a tighter `cost_budget` policy) on top, documented at the
   point of divergence.
3. **Project repos** — the actual codebases this workflow is running against.
   Each one consumes `agent-dev-kit` the same way the infrastructure repo
   does.

The split exists so that generic, reusable workflow definitions can evolve
independently of, and be shared freely across, any number of personal or
project deployments — including by people who are not the original author.

## Two distribution mechanisms, and why they differ

Consumers pull two different kinds of content from this repo, through two
different mechanisms, because the two kinds of content have fundamentally
different discovery and versioning requirements.

### Skills → global symlink (native discovery, unpinned, shared)

Skills (`skills/<name>/SKILL.md`) are reached by symlinking
`~/.agents/skills/agent-dev-kit` to a local checkout of this repo. Omnigent
has a real, native, machine-global skill-discovery mechanism — it looks under
`~/.agents/skills/` (analogous to `~/.claude/skills/` for Claude Code) and
picks up any skill it finds there, regardless of which repo or bundle
invoked it. Because that discovery is genuinely global:

- One checkout serves every project on the machine.
- Updates are manual (`git pull` in the checkout) and immediately visible
  everywhere — there is no per-repo pin.
- This is the right trade-off for skills specifically because skill content
  (prose procedures like `cross-review`, `fanout`, `investigate`) is meant to
  be identical across every project a person works in; a person's workflow
  discipline doesn't usually want to differ project-to-project the way
  dependency versions do.

### Sub-agent bundles → pinned git submodule (per-repo, versioned)

Sub-agent bundle configs (`config.yaml` at this repo's root, plus
`agents/<name>/config.yaml`) are reached via a git submodule checked out at
`.agents/agent-dev-kit/` inside each consumer repo, with the consumer's own
`.omnigent/config.yaml` pointing `default_agent` at that submodule path.

This is the ONLY viable mechanism, not a stylistic choice, because of a
concrete constraint in Omnigent's own bundle loader: **the parser requires an
agent bundle root to physically contain `config.yaml` at its root, with
`agents/<name>/config.yaml` as direct children** — no `config_path`
indirection, no walking up from a nested path, no symlink-then-redirect. This
was confirmed by reading Omnigent's own bundle-resolution source, not
inferred from docs. Because the bundle root must be a real, physical
directory containing `config.yaml` at its top level, a global unpinned
symlink (as used for skills) cannot serve this purpose — the bundle loader
needs a concrete, addressable root per consuming repo, and a git submodule is
the standard mechanism for "a versioned, pinned copy of another repo's
content, living at a fixed path inside this repo."

The practical consequence: every consumer repo can pin a different commit of
`agent-dev-kit`'s agent bundles (so a breaking change to, say, `codex`'s
harness config doesn't silently roll out to every project at once), while
still sharing exactly the same skill prose everywhere via the global symlink.

## Why not submodule everything, or symlink everything?

- Submoduling skills too would mean every consumer repo re-pins skill prose
  independently, defeating the point of skills being a shared, always-current
  discipline — and it would fight Omnigent's own global discovery path rather
  than using it.
- Symlinking bundles globally is not possible: Omnigent's bundle loader has
  no global-bundle discovery mechanism analogous to `~/.agents/skills/`, and
  even if one existed, a single global bundle would prevent per-repo pinning,
  which is exactly what makes bundle changes safe to roll out gradually.

## Reference implementation: Omnigent / Polly

The workflow this repo describes is general — spec-first decomposition,
small human-reviewable issues, one implementer vendor and one different-vendor
reviewer per PR, human-gated merge, GitHub issues + labels as the ledger. This
repo ships **Polly on Omnigent** as the reference implementation of that
pattern (root `config.yaml`, the seven `agents/*/config.yaml` bundles, and the
three skills), with Claude Code as the default implementer and Codex as the
default cross-vendor reviewer. A different orchestrator or vendor pairing
could implement the same general pattern; this repo just ships one concrete,
working instance of it.
