#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    command_exists,
    coordination_root,
    git,
    git_ref_exists,
    load_threads,
    repo_instruction_paths,
    repo_relative_path,
    run,
)

MANAGED_MARKERS = (
    "managed-by-codex-coordination-kit",
    '"managed_by": "codex-coordination-kit"',
)


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


def default_persistent_branches(root: Path) -> dict[str, str]:
    try:
        threads = load_threads(root)
    except Exception:
        return {}
    if any(row.get("id") == "thread1" for row in threads):
        return {"thread1": "codex/thread1-mainline"}
    return {}


def parse_persistent_branches(values: list[str], root: Path) -> dict[str, str]:
    if not values:
        return default_persistent_branches(root)

    mapping: dict[str, str] = {}
    for value in values:
        thread_id, separator, branch = value.partition("=")
        thread_id = thread_id.strip()
        branch = branch.strip()
        if separator != "=" or not thread_id or not branch:
            raise SystemExit(f"Invalid --persistent-branch value: {value!r}. Use THREAD_ID=codex/threadX-mainline.")
        mapping[thread_id] = branch
    return mapping


def template_root(root: Path) -> Path:
    return root / "templates" / "repo"


def install_repo_instruction_templates(root: Path, target_repo: Path) -> tuple[list[str], list[str]]:
    source_root = template_root(root)
    copies = [
        ("AGENTS.md", "AGENTS.md"),
        (".codex/AGENTS.md", ".codex/AGENTS.md"),
        (".agent/coordination.json", ".agent/coordination.json"),
    ]
    installed: list[str] = []
    preserved: list[str] = []

    for src_rel, dst_rel in copies:
        src = source_root / src_rel
        dst = target_repo / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        rel = repo_relative_path(target_repo, dst) or dst_rel
        if not dst.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            installed.append(rel)
            continue

        existing = dst.read_text(encoding="utf-8")
        if any(marker in existing for marker in MANAGED_MARKERS):
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            installed.append(rel)
        else:
            preserved.append(rel)

    return installed, preserved


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
        "--persistent-branch",
        action="append",
        default=[],
        help="Keep a thread on a reusable branch with THREAD_ID=BRANCH. Repeat as needed.",
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
    persistent_branches = parse_persistent_branches(list(args.persistent_branch), root)

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
        "persistent_branches": persistent_branches,
    }
    config_path = root / "coordination.config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    installed_instruction_files, preserved_instruction_files = install_repo_instruction_templates(root, target_repo)

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
    if persistent_branches:
        print("Persistent branches:")
        for thread_id, branch in sorted(persistent_branches.items()):
            print(f"  - {thread_id}: {branch}")
    if not command_exists(args.codex_bin):
        print(f"Warning: codex executable not found on PATH: {args.codex_bin}")
    if added:
        print("Updated target repo .gitignore with:")
        for entry in added:
            print(f"  - {entry}")
        print("Commit the target repo .gitignore on the base branch before your first merge-back.")
    else:
        print("Target repo .gitignore did not need changes.")
    if installed_instruction_files:
        print("Installed repo-level Codex agent config:")
        for entry in installed_instruction_files:
            print(f"  - {entry}")
    if preserved_instruction_files:
        print("Preserved existing repo-level agent config:")
        for entry in preserved_instruction_files:
            print(f"  - {entry}")
    active_instruction_paths = repo_instruction_paths(target_repo)
    if active_instruction_paths:
        print("Active repo-level instruction files:")
        for entry in active_instruction_paths:
            print(f"  - {entry}")
    if args.install_hooks:
        print("Installed coordination hooks.")
    if args.doctor:
        print("Doctor check passed.")


if __name__ == "__main__":
    main()
