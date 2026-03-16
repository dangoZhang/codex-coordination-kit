#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import command_exists, coordination_root, git, git_ref_exists, repo_relative_path, run


def detect_remote_base_branch(target_repo: Path) -> str | None:
    symbolic = git(target_repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if symbolic.startswith("origin/"):
        return symbolic.split("/", 1)[1]

    remote_refs = {
        line.split("/", 1)[1]
        for line in git(target_repo, "for-each-ref", "refs/remotes/origin", "--format=%(refname:short)", check=False).splitlines()
        if line.startswith("origin/") and line != "origin/HEAD"
    }
    for name in ("main", "master"):
        if name in remote_refs:
            return name
    return None


def detect_base_branch(target_repo: Path) -> str:
    for name in ("main", "master"):
        if git_ref_exists(target_repo, f"refs/heads/{name}"):
            return name

    remote_base = detect_remote_base_branch(target_repo)
    if remote_base:
        return remote_base

    current = git(target_repo, "branch", "--show-current", check=False)
    if current:
        return current
    raise SystemExit("Could not detect a base branch. Pass --base-branch explicitly.")


def ensure_local_base_branch(target_repo: Path, base_branch: str) -> bool:
    if git_ref_exists(target_repo, f"refs/heads/{base_branch}"):
        return False
    if not git_ref_exists(target_repo, f"refs/remotes/origin/{base_branch}"):
        raise SystemExit(
            f"Configured base branch `{base_branch}` does not exist locally or at `origin/{base_branch}`."
        )

    result = run(
        [
            "git",
            "-C",
            str(target_repo),
            "branch",
            "--track",
            base_branch,
            f"origin/{base_branch}",
        ],
        check=False,
    )
    if result.returncode != 0 and not git_ref_exists(target_repo, f"refs/heads/{base_branch}"):
        raise SystemExit(
            f"Failed to create local base branch `{base_branch}` from `origin/{base_branch}`: "
            f"{(result.stderr or result.stdout).strip()}"
        )
    return True


def ensure_gitignore_entries(target_repo: Path, entries: list[str]) -> list[str]:
    if not entries:
        return []

    gitignore = target_repo / ".gitignore"
    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    added: list[str] = []
    existing = set(lines)
    for entry in entries:
        if entry and entry not in existing:
            lines.append(entry)
            existing.add(entry)
            added.append(entry)

    if added:
        content = "\n".join(lines).rstrip() + "\n"
        gitignore.write_text(content, encoding="utf-8")
    return added


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap Codex Coordination Kit against an existing git project."
    )
    parser.add_argument("--target-repo", required=True, help="Absolute or relative path to the target git repo.")
    parser.add_argument("--base-branch", help="Base branch used for new worktrees and merge-back.")
    parser.add_argument("--worktree-root", help="Override the generated worktree root.")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable name or path.")
    parser.add_argument(
        "--codex-exec-arg",
        action="append",
        default=[],
        help="Extra argument passed through to `codex exec`. Repeat as needed.",
    )
    parser.add_argument("--auto-finish-on-approve", action="store_true", help="Auto-merge approved branches.")
    parser.add_argument(
        "--auto-rewrite-on-block",
        action="store_true",
        help="Automatically re-invoke the applicant thread after a blocked review.",
    )
    parser.add_argument(
        "--max-auto-rewrite-attempts",
        type=int,
        default=2,
        help="Maximum automatic rewrite retries for the same branch.",
    )
    parser.add_argument(
        "--review-timeout-seconds",
        type=int,
        default=600,
        help="Timeout for a single automated review invocation.",
    )
    parser.add_argument(
        "--install-hooks",
        action="store_true",
        help="Install coordination hooks immediately after writing local config.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run a post-bootstrap health check and fail if the registration is incomplete.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root = coordination_root()
    target_repo = Path(args.target_repo).expanduser().resolve()
    if not target_repo.exists():
        raise SystemExit(f"Target repo does not exist: {target_repo}")

    run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"])
    run(["git", "-C", str(target_repo), "rev-parse", "--is-inside-work-tree"])

    base_branch = args.base_branch or detect_base_branch(target_repo)
    created_local_base = ensure_local_base_branch(target_repo, base_branch)

    worktree_root = (
        Path(args.worktree_root).expanduser().resolve()
        if args.worktree_root
        else target_repo / ".codex-worktrees"
    )
    config = {
        "target_repo": str(target_repo),
        "base_branch": base_branch,
        "worktree_root": str(worktree_root),
        "codex_command": [args.codex_bin],
        "codex_exec_args": list(args.codex_exec_arg),
        "auto_finish_on_approve": args.auto_finish_on_approve,
        "auto_rewrite_on_block": args.auto_rewrite_on_block,
        "max_auto_rewrite_attempts": max(0, args.max_auto_rewrite_attempts),
        "review_timeout_seconds": max(30, args.review_timeout_seconds),
    }
    config_path = root / "coordination.config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    entries: list[str] = []
    worktree_entry = repo_relative_path(target_repo, worktree_root, assume_directory=True)
    if worktree_entry:
        entries.append(worktree_entry)
    coord_entry = repo_relative_path(target_repo, root, assume_directory=True)
    if coord_entry:
        entries.append(coord_entry)
    added = ensure_gitignore_entries(target_repo, entries)

    run(["python3", str(root / "scripts" / "generate_starter_prompts.py")], cwd=root)

    if args.install_hooks:
        run(["python3", str(root / "scripts" / "install_hooks.py")], cwd=root)
    if args.doctor:
        doctor_command = ["python3", str(root / "scripts" / "doctor.py")]
        if args.install_hooks:
            doctor_command.append("--require-hooks")
        run(doctor_command, cwd=root)

    print(f"Wrote local config: {config_path}")
    print(f"Target repo: {target_repo}")
    print(f"Base branch: {base_branch}")
    if created_local_base:
        print(f"Created local tracking branch: {base_branch}")
    print(f"Worktree root: {worktree_root}")
    if not command_exists(args.codex_bin):
        print(f"Warning: codex executable not found on PATH: {args.codex_bin}")
    if added:
        print("Updated target repo .gitignore with:")
        for entry in added:
            print(f"  - {entry}")
        print("Commit the target repo .gitignore on the base branch before your first merge-back.")
    else:
        print("Target repo .gitignore did not need changes.")
    if args.install_hooks:
        print("Installed coordination hooks.")
    if args.doctor:
        print("Doctor check passed.")


if __name__ == "__main__":
    main()
