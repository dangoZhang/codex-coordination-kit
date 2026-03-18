#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import command_exists, coordination_root, git, git_ref_exists, load_config, load_threads, repo_instruction_paths, run

HOOK_MARKER = "# managed-by-codex-coordination-kit"


def hook_path(repo: Path, hook_name: str) -> Path:
    raw = Path(git(repo, "rev-parse", "--git-path", f"hooks/{hook_name}"))
    return raw if raw.is_absolute() else repo / raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Codex Coordination installation.")
    parser.add_argument(
        "--require-hooks",
        action="store_true",
        help="Fail when the expected control-plane and target-repo hooks are missing.",
    )
    parser.add_argument(
        "--skip-codex",
        action="store_true",
        help="Skip checking that the configured codex executable exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = coordination_root()

    checks: list[tuple[str, bool, str]] = []
    failures = 0

    def record(name: str, ok: bool, detail: str) -> None:
        nonlocal failures
        checks.append((name, ok, detail))
        if not ok:
            failures += 1

    for required in (
        "THREADS.json",
        "TASK_BOARD.md",
        "COMM_LOG.md",
        "HANDOFFS.md",
        "THREAD_STARTER_PROMPTS.md",
        "scripts/bootstrap.sh",
        "scripts/doctor.sh",
        "scripts/install_hooks.py",
        "scripts/install_hooks.sh",
        "scripts/register_project.sh",
        "scripts/export_status.py",
        "scripts/thread_branch_flow.sh",
    ):
        path = root / required
        record(f"file:{required}", path.exists(), str(path))

    try:
        run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"])
        record("coordination-git", True, str(root))
    except Exception as exc:
        record("coordination-git", False, str(exc))

    try:
        config = load_config(root)
        record("config", True, str(config.config_path))
    except SystemExit as exc:
        record("config", False, str(exc))
        config = None

    if config is not None:
        try:
            run(["git", "-C", str(config.target_repo), "rev-parse", "--is-inside-work-tree"])
            record("target-git", True, str(config.target_repo))
        except Exception as exc:
            record("target-git", False, str(exc))

        base_ok = git_ref_exists(config.target_repo, f"refs/heads/{config.base_branch}") or git_ref_exists(
            config.target_repo, f"refs/remotes/origin/{config.base_branch}"
        )
        record("base-branch", base_ok, config.base_branch)

        try:
            threads = load_threads(root)
            record("threads", bool(threads), f"{len(threads)} threads")
        except Exception as exc:
            record("threads", False, str(exc))

        instruction_paths = repo_instruction_paths(config.target_repo)
        record(
            "repo-agent-config",
            bool(instruction_paths),
            ", ".join(instruction_paths) if instruction_paths else "missing AGENTS.md / .codex / .agent config",
        )

        if not args.skip_codex:
            codex_bin = config.codex_command[0] if config.codex_command else "codex"
            record("codex-bin", command_exists(codex_bin), codex_bin)

        try:
            exported = run(["python3", str(root / "scripts" / "export_status.py")], cwd=root)
            payload = json.loads(exported.stdout)
            ok = bool(payload.get("threads"))
            detail = f"{len(payload.get('threads', []))} threads exported"
            record("status-export", ok, detail)
        except Exception as exc:
            record("status-export", False, str(exc))

        if args.require_hooks:
            expected_hooks = [
                ("coord-post-commit", hook_path(root, "post-commit")),
                ("target-pre-commit", hook_path(config.target_repo, "pre-commit")),
                ("target-post-commit", hook_path(config.target_repo, "post-commit")),
                ("target-pre-push", hook_path(config.target_repo, "pre-push")),
            ]
            for name, path in expected_hooks:
                ok = path.exists() and HOOK_MARKER in path.read_text(encoding="utf-8")
                record(name, ok, str(path))

    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
