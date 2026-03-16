#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional

from common import git, load_config, load_threads


@dataclass
class Task:
    id: str
    thread: str
    title: str
    owner: str
    status: str
    depends_on: str
    output: str
    line_no: int


def parse_task_board(path) -> list[Task]:
    tasks: list[Task] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.startswith("|") or "|---" in line:
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) != 7 or cells[0] == "ID":
            continue
        tasks.append(
            Task(
                id=cells[0],
                thread=cells[1],
                title=cells[2],
                owner=cells[3],
                status=cells[4],
                depends_on=cells[5],
                output=cells[6],
                line_no=idx,
            )
        )
    return tasks


def parse_comm_log(path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    kickoff_latest: dict[str, dict] = {}
    last_invocation: dict[str, dict] = {}
    active_kickoff: dict[str, tuple[dict, datetime]] = {}
    in_code_block = False
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not line.startswith("["):
            continue
        try:
            first = line.index("] [")
            ts = line[1:first]
            rest = line[first + 3 :]
            second = rest.index("] [type: ")
            thread = rest[:second]
            rest2 = rest[second + len("] [type: ") :]
            third = rest2.index("] ")
            kind = rest2[:third]
            msg = rest2[third + 2 :]
        except ValueError:
            continue
        try:
            parsed_ts = datetime.strptime(ts, "%Y-%m-%d %H:%M")
        except ValueError:
            parsed_ts = None
        latest[thread] = {
            "timestamp": ts,
            "type": kind,
            "message": msg,
            "line_no": idx,
        }
        if kind == "kickoff":
            kickoff = {
                "timestamp": ts,
                "message": msg,
                "line_no": idx,
            }
            kickoff_latest[thread] = kickoff
            if parsed_ts:
                active_kickoff[thread] = (kickoff, parsed_ts)
            else:
                active_kickoff.pop(thread, None)
            continue

        kickoff_row, start_ts = active_kickoff.get(thread, (None, None))
        if not kickoff_row or not start_ts or not parsed_ts or parsed_ts < start_ts:
            continue
        last_invocation[thread] = {
            "start_timestamp": kickoff_row["timestamp"],
            "end_timestamp": ts,
            "elapsed_seconds": max(int((parsed_ts - start_ts).total_seconds()), 0),
            "end_type": kind,
            "start_line_no": kickoff_row["line_no"],
            "end_line_no": idx,
        }

    return {
        "latest": latest,
        "kickoff_latest": kickoff_latest,
        "last_invocation": last_invocation,
    }


def select_task(thread_id: str, tasks: list[Task]) -> Optional[Task]:
    thread_tasks = [task for task in tasks if task.thread == thread_id]
    for status in ("BLOCKED", "IN_PROGRESS", "TODO", "DONE"):
        matches = [task for task in thread_tasks if task.status == status]
        if matches:
            return matches[-1]
    return None


def branch_matches_thread(branch: str, thread_id: str) -> bool:
    return branch == f"codex/{thread_id}" or branch.startswith(f"codex/{thread_id}-")


def persistent_branch_for_thread(config, thread_id: str) -> str | None:
    return config.persistent_branches.get(thread_id)


def expected_branch_prefix(config, thread_id: str) -> str:
    return persistent_branch_for_thread(config, thread_id) or f"codex/{thread_id}-"


def main() -> None:
    config = load_config()
    task_board = config.coordination_root / "TASK_BOARD.md"
    comm_log = config.coordination_root / "COMM_LOG.md"
    tasks = parse_task_board(task_board)
    logs = parse_comm_log(comm_log)

    local_branches = [
        line
        for line in git(config.target_repo, "for-each-ref", "refs/heads", "--format=%(refname:short)|%(objectname:short)|%(subject)").splitlines()
        if line
    ]
    remote_branches = [
        line
        for line in git(config.target_repo, "for-each-ref", "refs/remotes/origin", "--format=%(refname:short)", check=False).splitlines()
        if line
    ]
    worktree_rows = git(config.target_repo, "worktree", "list", "--porcelain").splitlines()
    worktrees: dict[str, str] = {}
    current_path = None
    for line in worktree_rows:
        if line.startswith("worktree "):
            current_path = line.split(" ", 1)[1]
        elif line.startswith("branch ") and current_path:
            worktrees[line.split(" ", 1)[1].replace("refs/heads/", "")] = current_path
            current_path = None

    current_branch = git(config.target_repo, "branch", "--show-current")
    dirty = bool(git(config.target_repo, "status", "--porcelain", check=False))

    counts = {"BLOCKED": 0, "IN_PROGRESS": 0, "TODO": 0, "DONE": 0}
    thread_defs = load_threads(config.coordination_root)
    threads = []

    for row in thread_defs:
        thread_id = row["id"]
        task = select_task(thread_id, tasks)
        if task:
            counts[task.status] = counts.get(task.status, 0) + 1
        persistent_branch = persistent_branch_for_thread(config, thread_id)
        prefix = expected_branch_prefix(config, thread_id)
        local_matches = [item.split("|")[0] for item in local_branches if branch_matches_thread(item.split("|")[0], thread_id)]
        remote_matches = [item for item in remote_branches if branch_matches_thread(item.split("origin/", 1)[-1], thread_id)]
        threads.append(
            {
                "thread": thread_id,
                "slot": row["slot"],
                "display_name": row["name"],
                "role": row["role"],
                "auto_branch": row["auto_branch"],
                "task": asdict(task) if task else None,
                "last_log": logs["latest"].get(thread_id),
                "runtime_start": logs["kickoff_latest"].get(thread_id),
                "last_invocation": logs["last_invocation"].get(thread_id),
                "branches": {
                    "expected_prefix": prefix,
                    "persistent_branch": persistent_branch,
                    "local": [{"name": branch, "worktree": worktrees.get(branch)} for branch in local_matches],
                    "remote": remote_matches,
                },
            }
        )

    legacy_local = []
    valid_threads = {row["id"] for row in thread_defs}
    for row in local_branches:
        branch = row.split("|")[0]
        if branch == config.base_branch:
            continue
        if not branch.startswith("codex/thread"):
            legacy_local.append(branch)
            continue
        tail = branch[len("codex/thread") :]
        idx = tail.split("-", 1)[0]
        if not idx.isdigit() or f"thread{idx}" not in valid_threads:
            legacy_local.append(branch)

    print(
        json.dumps(
            {
                "coordination_root": str(config.coordination_root),
                "target_repo_root": str(config.target_repo),
                "base_branch": config.base_branch,
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "repo": {
                    "current_branch": current_branch,
                    "dirty": dirty,
                    "legacy_local_branches": legacy_local,
                },
                "totals": {
                    "blocked": counts.get("BLOCKED", 0),
                    "in_progress": counts.get("IN_PROGRESS", 0),
                    "todo": counts.get("TODO", 0),
                    "done": counts.get("DONE", 0),
                },
                "threads": threads,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
