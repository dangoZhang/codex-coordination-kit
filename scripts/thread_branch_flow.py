#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from common import git, load_config, load_threads


def sanitize_scope(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def canonical_branch(thread_id: str) -> str:
    return f"codex/{thread_id}"


def branch_matches_thread(branch: str, thread_id: str | None = None) -> bool:
    match = re.match(r"^codex/(thread[0-9]+)(?:-[a-z0-9][a-z0-9-]*)?$", branch)
    if not match:
        return False
    return thread_id is None or match.group(1) == thread_id


def branch_thread_id(branch: str) -> str | None:
    match = re.match(r"^codex/(thread[0-9]+)(?:-[a-z0-9][a-z0-9-]*)?$", branch)
    return match.group(1) if match else None


def is_thread_branch(branch: str) -> bool:
    return branch_thread_id(branch) is not None


def thread_worktrees(target_repo: Path) -> dict[str, str]:
    worktrees_raw = git(target_repo, "worktree", "list", "--porcelain").splitlines()
    worktrees: dict[str, str] = {}
    current_path = ""
    for line in worktrees_raw:
        if line.startswith("worktree "):
            current_path = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            branch = line.split(" ", 1)[1].replace("refs/heads/", "")
            worktrees[branch] = current_path
    return worktrees


def select_thread_branch(target_repo: Path, thread_id: str) -> str | None:
    branches = [
        line
        for line in git(target_repo, "for-each-ref", "refs/heads", "--format=%(refname:short)").splitlines()
        if line and branch_matches_thread(line, thread_id)
    ]
    canonical = canonical_branch(thread_id)
    if canonical in branches:
        return canonical
    if len(branches) == 1:
        return branches[0]
    if len(branches) > 1:
        raise SystemExit(
            f"Multiple existing branches found for {thread_id}: {', '.join(branches)}. "
            f"Consolidate them before starting more work."
        )
    return None


def sync_thread_branch(config, branch: str, worktree: Path) -> str:
    if git(worktree, "status", "--porcelain", check=False):
        raise SystemExit(f"Thread worktree is dirty: {worktree}")

    upstream = config.base_branch
    fetch = subprocess.run(
        ["git", "-C", str(config.target_repo), "fetch", "origin", config.base_branch],
        capture_output=True,
        text=True,
    )
    if fetch.returncode == 0:
        upstream = f"origin/{config.base_branch}"

    sync = subprocess.run(
        ["git", "-C", str(worktree), "merge", "--no-edit", upstream],
        capture_output=True,
        text=True,
    )
    if sync.returncode != 0:
        detail = (sync.stderr or sync.stdout or "").strip()
        raise SystemExit(
            f"Failed to sync `{branch}` with `{upstream}`. Resolve the base-sync conflict in `{worktree}` first. "
            f"{detail[-400:] if detail else ''}".strip()
        )
    return upstream


def thread_exists(thread_id: str, threads: list[dict]) -> bool:
    return any(row["id"] == thread_id for row in threads)


def resolve_thread_name(name: str, threads: list[dict]) -> str:
    for row in threads:
        if row["name"] == name:
            return row["id"]
    raise SystemExit(f"Unknown thread name: {name}")


def verify_review_ref(coord_root: Path, review_ref: str) -> None:
    handoffs = (coord_root / "HANDOFFS.md").read_text(encoding="utf-8")
    comm_log = (coord_root / "COMM_LOG.md").read_text(encoding="utf-8")
    if review_ref not in handoffs and review_ref not in comm_log:
        raise SystemExit(f"Review ref not found: {review_ref}")

    in_block = False
    for line in handoffs.splitlines():
        if line.startswith("## Handoff: "):
            in_block = f"`{review_ref}`" in line
            continue
        if in_block and "ALLOW_MERGE_TO_BASE" in line:
            return

    for line in comm_log.splitlines():
        if review_ref in line and "ALLOW_MERGE_TO_BASE" in line:
            return

    raise SystemExit(f"Review ref exists but has no ALLOW_MERGE_TO_BASE marker: {review_ref}")


def maybe_record_task_event(config, action: str, thread: str, task: str | None, note: str | None) -> None:
    if not task and not note:
        return
    command = [
        "python3",
        str(config.coordination_root / "scripts" / "coord_task_event.py"),
        action,
        "--thread",
        thread,
    ]
    if task:
        command.extend(["--task", task])
    if note:
        command.extend(["--note", note])
    subprocess.run(command, cwd=str(config.coordination_root), check=True)


def start_branch(thread: str | None, thread_name: str | None, scope: str, task: str | None, note: str | None) -> None:
    config = load_config()
    threads = load_threads(config.coordination_root)
    if not thread and thread_name:
        thread = resolve_thread_name(thread_name, threads)
    if not thread:
        raise SystemExit("--thread or --thread-name is required")
    if not thread_exists(thread, threads):
        raise SystemExit(f"Unknown thread id: {thread}")

    scope = sanitize_scope(scope)
    if not scope:
        raise SystemExit("Scope is empty after sanitization")

    branch = select_thread_branch(config.target_repo, thread) or canonical_branch(thread)
    worktree = config.worktree_root / branch.replace("/", "__")

    git(config.target_repo, "show-ref", "--verify", "--quiet", f"refs/heads/{config.base_branch}")
    config.worktree_root.mkdir(parents=True, exist_ok=True)

    existing_worktrees = thread_worktrees(config.target_repo)
    if branch not in existing_worktrees and worktree.exists():
        raise SystemExit(f"Worktree path already exists outside git worktree metadata: {worktree}")

    created = False
    if branch in existing_worktrees:
        worktree = Path(existing_worktrees[branch]).resolve()
    else:
        branch_exists = subprocess.run(
            ["git", "-C", str(config.target_repo), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
        ).returncode == 0
        command = ["git", "-C", str(config.target_repo), "worktree", "add"]
        if branch_exists:
            command.extend([str(worktree), branch])
        else:
            command.extend(["-b", branch, str(worktree), config.base_branch])
            created = True
        subprocess.run(command, check=True)

    upstream = sync_thread_branch(config, branch, worktree)
    maybe_record_task_event(config, "start", thread, task, note)

    print("Ready:")
    print(f"  branch: {branch}")
    print(f"  worktree: {worktree}")
    print(f"  session_scope: {scope}")
    print(f"  synced_from: {upstream}")
    print(f"  created: {created}")


def audit_branches() -> None:
    config = load_config()
    thread_ids = {row["id"] for row in load_threads(config.coordination_root)}
    current_branch = git(config.target_repo, "branch", "--show-current")
    dirty = "dirty" if git(config.target_repo, "status", "--porcelain", check=False) else "clean"
    merged = set(
        line
        for line in git(
            config.target_repo,
            "branch",
            "--merged",
            config.base_branch,
            "--format=%(refname:short)",
        ).splitlines()
        if line
    )
    branches = [line for line in git(config.target_repo, "for-each-ref", "refs/heads", "--format=%(refname:short)").splitlines() if line]
    worktrees_raw = git(config.target_repo, "worktree", "list", "--porcelain").splitlines()
    worktrees: dict[str, str] = {}
    current_path = ""
    for line in worktrees_raw:
        if line.startswith("worktree "):
            current_path = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            branch = line.split(" ", 1)[1].replace("refs/heads/", "")
            worktrees[branch] = current_path

    print(f"Target repo: {config.target_repo}")
    print(f"Base branch: {config.base_branch}")
    print(f"Current branch: {current_branch}")
    print(f"Worktree status: {dirty}")
    print()
    print(f"{'BRANCH':44} {'POLICY':8} {'MERGED':8} WORKTREE")
    print(f"{'------':44} {'------':8} {'------':8} --------")

    for branch in branches:
        if branch == config.base_branch:
            policy = "BASE"
        else:
            match = re.match(r"^codex/(thread[0-9]+)(?:-[a-z0-9][a-z0-9-]*)?$", branch)
            policy = "OK" if match and match.group(1) in thread_ids else "LEGACY"
        merged_flag = "yes" if branch in merged else "no"
        worktree = worktrees.get(branch, "-")
        print(f"{branch:44} {policy:8} {merged_flag:8} {worktree}")


def finish_branch(branch: str, review_ref: str, cleanup_source: bool, task: str | None, note: str | None) -> None:
    config = load_config()
    verify_review_ref(config.coordination_root, review_ref)
    subprocess.run(
        ["git", "-C", str(config.target_repo), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        check=True,
    )

    already_merged = subprocess.run(
        ["git", "-C", str(config.target_repo), "merge-base", "--is-ancestor", branch, config.base_branch],
        capture_output=True,
        text=True,
    )
    if already_merged.returncode == 0:
        print(f"Already merged: {branch}")
        return

    current_branch = git(config.target_repo, "branch", "--show-current")
    merge_dir = config.target_repo
    temp_worktree: Path | None = None

    if current_branch == config.base_branch:
        if git(config.target_repo, "status", "--porcelain", check=False):
            raise SystemExit(f"Target repo {config.base_branch} worktree is dirty")
    else:
        worktrees_raw = git(config.target_repo, "worktree", "list", "--porcelain").splitlines()
        if any(line == f"branch refs/heads/{config.base_branch}" for line in worktrees_raw):
            raise SystemExit(f"{config.base_branch} is already checked out in another worktree; clean or switch it first")
        config.worktree_root.mkdir(parents=True, exist_ok=True)
        temp_worktree = config.worktree_root / f"_merge_{config.base_branch}_{__import__('datetime').datetime.now().strftime('%Y%m%d%H%M%S')}"
        subprocess.run(
            ["git", "-C", str(config.target_repo), "worktree", "add", str(temp_worktree), config.base_branch],
            check=True,
        )
        merge_dir = temp_worktree

    if git(merge_dir, "status", "--porcelain", check=False):
        raise SystemExit(f"Merge worktree is dirty: {merge_dir}")

    subprocess.run(["git", "-C", str(merge_dir), "merge", "--no-ff", "--no-edit", branch], check=True)

    if cleanup_source and not is_thread_branch(branch):
        worktrees_raw = git(config.target_repo, "worktree", "list", "--porcelain").splitlines()
        source_path = ""
        current_path = ""
        for line in worktrees_raw:
            if line.startswith("worktree "):
                current_path = line.split(" ", 1)[1]
            elif line == f"branch refs/heads/{branch}":
                source_path = current_path
                break

        if source_path and Path(source_path).resolve().is_relative_to(config.worktree_root.resolve()):
            subprocess.run(["git", "-C", str(config.target_repo), "worktree", "remove", source_path, "--force"], check=False)
        subprocess.run(["git", "-C", str(config.target_repo), "branch", "-D", branch], check=False)

    print("Merged:")
    print(f"  branch: {branch}")
    print(f"  into: {config.base_branch}")
    print(f"  review: {review_ref}")
    print(f"  merge_worktree: {merge_dir}")
    print(f"  cleanup_source: {cleanup_source and not is_thread_branch(branch)}")
    if cleanup_source and is_thread_branch(branch):
        print("  source_branch_preserved: long-lived thread branch")
    if temp_worktree:
        print("Remove temp merge worktree after verification:")
        print(f'  git -C "{config.target_repo}" worktree remove "{temp_worktree}"')

    thread = branch_thread_id(branch)
    if thread:
        maybe_record_task_event(config, "finish", thread, task, note)


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex thread branch/worktree workflow.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start")
    start.add_argument("--thread")
    start.add_argument("--thread-name")
    start.add_argument("--scope", required=True)
    start.add_argument("--task")
    start.add_argument("--note")

    sub.add_parser("audit")

    finish = sub.add_parser("finish")
    finish.add_argument("--branch", required=True)
    finish.add_argument("--review-ref", required=True)
    finish.add_argument("--cleanup-source", action="store_true")
    finish.add_argument("--task")
    finish.add_argument("--note")

    args = parser.parse_args()
    if args.cmd == "start":
        start_branch(args.thread, args.thread_name, args.scope, args.task, args.note)
    elif args.cmd == "audit":
        audit_branches()
    else:
        finish_branch(args.branch, args.review_ref, args.cleanup_source, args.task, args.note)


if __name__ == "__main__":
    main()
