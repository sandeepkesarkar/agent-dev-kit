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

### Skills → global symlinks, one per skill (native discovery, unpinned, shared)

Skills (`skills/<name>/SKILL.md`) are reached by symlinking each individual
skill directory under `~/.agents/skills/` — e.g.
`~/.agents/skills/cross-review -> <checkout>/skills/cross-review` — to a
local checkout of this repo. Omnigent has a real, native, machine-global
skill-discovery mechanism (`omnigent.spec.parser.discover_host_skills`,
confirmed by reading the installed package's source and by running it
directly against a real symlinked directory): it scans the **immediate
children** of `~/.agents/skills/` (analogous to `~/.claude/skills/` for
Claude Code), and requires each child to directly contain its own
`SKILL.md`. That means the symlink has to land at exactly that depth — a
single symlink to this repo's whole `skills/` directory (one level too
shallow) is silently invisible to the parser, since it never finds
`<symlink>/SKILL.md` at the child level. Confirmed both ways empirically:
a per-skill symlink layout was discovered correctly (3/3 skills), the
single-directory layout was not. Symlinks themselves are not the problem —
the parser's `is_dir()`/`.exists()` calls follow them fine — only the depth
mattered. Because discovery is otherwise genuinely global:

- One checkout serves every project on the machine.
- Updates are manual (`git pull` in the checkout) and immediately visible
  everywhere — there is no per-repo pin.
- This is the right trade-off for skills specifically because skill content
  (prose procedures like `cross-review`, `fanout`, `investigate`) is meant to
  be identical across every project a person works in; a person's workflow
  discipline doesn't usually want to differ project-to-project the way
  dependency versions do.

### Sub-agent bundles → pinned git submodule (per-repo, versioned, recommended)

Sub-agent bundle configs (`config.yaml` at this repo's root, plus
`agents/<name>/config.yaml`) are reached via a git submodule checked out at
`.agents/agent-dev-kit/` inside each consumer repo, with the consumer's own
`.omnigent/config.yaml` pointing `default_agent` at that submodule path.

This choice is driven by a real constraint in Omnigent's own bundle loader,
confirmed by reading `omnigent.spec.parser.parse` /
`_discover_sub_agents` / `omnigent.spec.__init__._find_omnigent_yaml_in_dir`:
**the parser requires an agent bundle root to contain `config.yaml` at its
own top level, with `agents/<name>/config.yaml` as direct children** — no
`config_path` indirection, no walking up from a nested path. That part of
the original claim holds.

What does **not** hold, and was corrected after empirical verification: the
loader does not reject symlinks. We ran `omnigent.spec.parser.parse` and
`omnigent.spec.validator.validate` directly against a bundle root that was
itself a symlink to a real checkout (`.agents/agent-dev-kit -> ~/src/agent-dev-kit`),
and it parsed and validated cleanly — all 7 sub-agents and all 3 bundled
skills discovered correctly. The loader's `agent_dir.is_dir()` /
`config_yaml.exists()` calls are plain `pathlib` calls, which follow symlinks
by default; there's no explicit `is_symlink()` check anywhere in the
discovery path that would reject one. So a bare symlink to a shared local
checkout *does* work as a bundle root today — it is a simpler alternative,
not a broken one.

We still recommend the **git submodule** over a bare symlink, because it's
about independent versioning, not loader compatibility: a submodule lets
each consumer repo pin a different commit of `agent-dev-kit`'s agent bundles
(so a breaking change to, say, `codex`'s harness config rolls out to one
repo at a time), whereas a symlink to one shared local checkout ties every
consumer repo using that checkout to whatever commit it happens to be on —
the same trade-off skills deliberately accept via the global symlink. For
bundles specifically, independent per-repo pinning is worth the extra
submodule step; for skills, sharing one always-current copy is the point.

## Why not submodule everything, or symlink everything?

- Submoduling skills too would mean every consumer repo re-pins skill prose
  independently, defeating the point of skills being a shared, always-current
  discipline — and it would fight Omnigent's own global discovery path rather
  than using it.
- Symlinking bundles globally (one shared bundle for every project on the
  machine, the way skills work) is possible mechanically but undesirable:
  Omnigent's bundle loader has no global-bundle discovery mechanism analogous
  to `~/.agents/skills/` — a bundle is always addressed by an explicit
  `default_agent` path per consumer repo — and even if it did, a single
  global bundle would prevent per-repo pinning, which is exactly what makes
  bundle changes safe to roll out gradually. A per-repo symlink (rather than
  a per-repo submodule) remains a legitimate lighter-weight option for a
  single-user, single-checkout setup that doesn't need independent pinning.

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
