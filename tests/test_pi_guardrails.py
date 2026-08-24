"""Regression coverage for agents/pi/config.yaml's review/explore/search-only
role (issue #2).

Proves, against the REAL installed Omnigent parser/validator and policy
evaluators (never by inspecting YAML text), that:

- The full bundle still parses and validates cleanly.
- read_only_os hard-denies direct file-write tool calls.
- blast_radius hard-denies push/merge/deploy (DENY, not ASK — Pi has no
  legitimate reason to push) and the catastrophic set (force-push).
- Reads/investigation stay ALLOWED at the policy layer.
- The policy layer alone does NOT stop shell-mediated writes (documents why
  os_env.sandbox exists — this is the gap PR #3's round-2 review found).
- Pi's actual os_env.sandbox config genuinely blocks shell-mediated writes
  (redirection, sed -i, rm, git commit) at the OS level, while ordinary
  review commands (cat/grep/ls/git log/diff/blame) keep working.

Requires the ``omnigent`` package (0.10.0+) on the interpreter running this
file — install it (``uv tool install omnigent`` or equivalent) or point
``python3`` at an environment that already has it before running:

    python3 tests/test_pi_guardrails.py

Also runnable under pytest if it happens to be installed in that same
environment (plain ``test_*`` functions, no pytest-only APIs used).
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _parsed_pi_spec():
    from omnigent.spec.parser import parse

    spec = parse(REPO_ROOT)
    return spec, next(a for a in spec.sub_agents if a.name == "pi")


def test_full_bundle_parses_and_validates() -> None:
    from omnigent.spec.validator import validate

    spec, _pi = _parsed_pi_spec()
    names = sorted(a.name for a in spec.sub_agents)
    assert names == ["agy", "claude_code", "codex", "cursor", "hermes", "opencode", "pi"], names
    result = validate(spec)
    assert not result.errors, result.errors


def _pi_policy_functions():
    """Build the two live evaluators exactly as agents/pi/config.yaml configures them."""
    from omnigent.policies.builtins.orchestration import blast_radius, read_only_os

    _spec, pi = _parsed_pi_spec()
    policies = {p.name: p for p in pi.guardrails.policies}

    ro_args = policies["read_only_os"].function.arguments or {}
    bl_args = policies["blast_radius"].function.arguments or {}
    assert bl_args.get("gate_pushes") is True, bl_args
    assert bl_args.get("risky_action") == "DENY", bl_args

    return read_only_os(**ro_args), blast_radius(**bl_args)


def _tool_call(name: str, **arguments: object) -> dict:
    return {"type": "tool_call", "data": {"name": name, "arguments": arguments}}


def test_read_only_os_denies_write_tools() -> None:
    read_only_os, _blast_radius = _pi_policy_functions()
    for tool in ("Write", "Edit", "MultiEdit", "sys_os_write", "sys_os_edit", "write", "edit"):
        result = read_only_os(_tool_call(tool, path="foo.py"), {})
        assert result["result"] == "DENY", (tool, result)


def test_read_only_os_allows_reads() -> None:
    read_only_os, _blast_radius = _pi_policy_functions()
    result = read_only_os(_tool_call("sys_os_read", path="foo.py"), {})
    assert result["result"] == "ALLOW", result


def test_blast_radius_denies_push_merge_deploy() -> None:
    _read_only_os, blast_radius = _pi_policy_functions()
    for command in (
        "git push origin issue-2",
        "gh pr merge 3",
        "gh pr merge 3 --merge",
    ):
        result = blast_radius(_tool_call("sys_os_shell", command=command), {})
        assert result["result"] == "DENY", (command, result)


def test_blast_radius_denies_catastrophic_regardless() -> None:
    _read_only_os, blast_radius = _pi_policy_functions()
    for command in (
        "git push --force origin main",
        "rm -rf /",
        "git reset --hard origin/main",
    ):
        result = blast_radius(_tool_call("sys_os_shell", command=command), {})
        assert result["result"] == "DENY", (command, result)


def test_blast_radius_allows_reads_and_non_push_shell() -> None:
    """Policy layer stays permissive for legitimate investigation."""
    _read_only_os, blast_radius = _pi_policy_functions()
    for command in ("git log --oneline", "grep -rn TODO .", "ls -la"):
        result = blast_radius(_tool_call("sys_os_shell", command=command), {})
        assert result["result"] == "ALLOW", (command, result)


def test_blast_radius_alone_does_not_stop_shell_mediated_writes() -> None:
    """
    Documents the exact gap PR #3's round-2 review found: blast_radius
    pattern-matches push/merge/deploy-shaped commands, not generic writes.
    This is precisely why os_env.sandbox (tested below) has to do the real
    enforcement — this test would start failing (a good thing) only if
    blast_radius grew generic write detection; until then it records the
    boundary instead of leaving it undocumented.
    """
    _read_only_os, blast_radius = _pi_policy_functions()
    for command in (
        "printf x > file.txt",
        "sed -i '' 's/a/b/' file.txt",
        "rm file.txt",
        "git commit --allow-empty -am wip",
    ):
        result = blast_radius(_tool_call("sys_os_shell", command=command), {})
        assert result["result"] == "ALLOW", (command, result)


def _sandbox_binary_available() -> bool:
    if sys.platform == "darwin":
        return shutil.which("sandbox-exec") is not None
    if sys.platform.startswith("linux"):
        return shutil.which("bwrap") is not None
    return False


def test_os_sandbox_blocks_shell_mediated_writes_and_allows_reads() -> None:
    """
    The real boundary check: wrap actual shell commands in Pi's ACTUAL
    resolved os_env.sandbox policy (read from the bundle, not hand-built)
    against a scratch git repo, and prove writes fail as OS permission
    errors while ordinary review commands keep working.
    """
    if not _sandbox_binary_available():
        print(
            f"SKIP: no sandbox backend binary for {sys.platform!r} on this host; "
            "cannot exercise the real OS-level enforcement here."
        )
        return

    from omnigent.inner.sandbox import get_backend, resolve_sandbox

    _spec, pi = _parsed_pi_spec()
    os_env_spec = pi.os_env
    assert os_env_spec.sandbox is not None and os_env_spec.sandbox.type != "none", (
        "pi's os_env.sandbox must be a real backend (not 'none') for this test to mean anything"
    )

    with tempfile.TemporaryDirectory(prefix="pi-sandbox-test-") as tmp:
        repo = pathlib.Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / "tracked.txt").write_text("hello\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
            cwd=repo,
            check=True,
        )

        cwd = repo.resolve()
        scoped_spec = os_env_spec.__class__(**{**os_env_spec.__dict__, "cwd": str(cwd)})
        policy = resolve_sandbox(scoped_spec, cwd)
        assert policy.active, "expected an active OS sandbox for pi, got an inactive/no-op policy"
        backend = get_backend(policy.backend_type)

        def run(cmd: str) -> subprocess.CompletedProcess:
            argv = backend.wrap_launcher_argv(["/bin/sh", "-c", cmd], policy, cwd)
            return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True)

        blocked = {
            "redirect": "printf x > newfile.txt",
            "sed -i": "sed -i '' 's/hello/bye/' tracked.txt",
            "rm": "rm tracked.txt",
            "git commit -am": "git commit --allow-empty -am wip",
        }
        for label, cmd in blocked.items():
            result = run(cmd)
            assert result.returncode != 0, (label, cmd, result.stdout, result.stderr)

        allowed = {
            "cat": "cat tracked.txt",
            "grep": "grep hello tracked.txt",
            "ls": "ls -la",
            "git log": "git log --oneline",
            "git diff": "git diff",
            "git blame": "git blame tracked.txt",
        }
        for label, cmd in allowed.items():
            result = run(cmd)
            assert result.returncode == 0, (label, cmd, result.stdout, result.stderr)

        assert not (repo / "newfile.txt").exists(), "redirect write should not have landed on disk"
        assert (repo / "tracked.txt").read_text() == "hello\n", "sed -i should not have landed"


_TESTS = [
    test_full_bundle_parses_and_validates,
    test_read_only_os_denies_write_tools,
    test_read_only_os_allows_reads,
    test_blast_radius_denies_push_merge_deploy,
    test_blast_radius_denies_catastrophic_regardless,
    test_blast_radius_allows_reads_and_non_push_shell,
    test_blast_radius_alone_does_not_stop_shell_mediated_writes,
    test_os_sandbox_blocks_shell_mediated_writes_and_allows_reads,
]


if __name__ == "__main__":
    failures = []
    for test in _TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 — collect every failure before exiting
            failures.append((test.__name__, exc))
            print(f"FAIL: {test.__name__}: {exc}")
        else:
            print(f"PASS: {test.__name__}")
    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)
    print(f"\nAll {len(_TESTS)} checks passed")
