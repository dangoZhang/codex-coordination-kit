#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import coordination_root, git, repo_relative_path, run


def detect_base_branch(target_repo: Path) -> str:
    for name in ("main", "master"):
        result = run(
            ["git", "-C", str(target_repo), "show-ref", "--verify", "--quiet", f"refs/heads/{name}"],
            check=False,
        )
        if result.returncode == 0:
            return name

    current = git(target_repo, "branch", "--show-current", check=False)
    if current:
        return current
    raise SystemExit("Could not detect a local base branch. Pass --base-branch explicitly.")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a local Codex coordination config.")
    parser.add_argument("--target-repo", required=True, help="Absolute or relative path to the target git repo.")
    parser.add_argument("--base-branch", help="Base branch used for new worktrees and merge-back.")
    parser.add_argument("--worktree-root", help="Override the generated worktree root.")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable name or path.")
    parser.add_argument("--auto-finish-on-approve", action="store_true", help="Auto-merge approved branches.")
    args = parser.parse_args()

    root = coordination_root()
    target_repo = Path(args.target_repo).expanduser().resolve()
    if not target_repo.exists():
        raise SystemExit(f"Target repo does not exist: {target_repo}")

    run(["git", "-C", str(target_repo), "rev-parse", "--is-inside-work-tree"])
    base_branch = args.base_branch or detect_base_branch(target_repo)
    worktree_root = Path(args.worktree_root).expanduser().resolve() if args.worktree_root else target_repo / ".codex-worktrees"

    config = {
        "target_repo": str(target_repo),
        "base_branch": base_branch,
        "worktree_root": str(worktree_root),
        "codex_command": [args.codex_bin],
        "codex_exec_args": [],
        "auto_finish_on_approve": args.auto_finish_on_approve,
    }
    config_path = root / "coordination.config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    entries: list[str] = []
    worktree_entry = repo_relative_path(target_repo, worktree_root)
    if worktree_entry:
        entries.append(worktree_entry)
    coord_entry = repo_relative_path(target_repo, root)
    if coord_entry:
        entries.append(coord_entry)
    added = ensure_gitignore_entries(target_repo, entries)

    run(["python3", str(root / "scripts" / "generate_starter_prompts.py")], cwd=root)

    print(f"Wrote local config: {config_path}")
    print(f"Target repo: {target_repo}")
    print(f"Base branch: {base_branch}")
    print(f"Worktree root: {worktree_root}")
    if added:
        print("Updated target repo .gitignore with:")
        for entry in added:
            print(f"  - {entry}")
    else:
        print("Target repo .gitignore did not need changes.")


if __name__ == "__main__":
    main()
