#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess

from common import load_config
from coord_task_event import parse_task_rows


def git(repo, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    config = load_config()
    branch = git(config.target_repo, "branch", "--show-current")
    match = re.match(r"^codex/(thread[0-9]+)-[a-z0-9-]+$", branch)
    if not match:
        return

    thread_id = match.group(1)
    if thread_id == "thread3":
        return

    task_board = config.coordination_root / "TASK_BOARD.md"
    comm_log = config.coordination_root / "COMM_LOG.md"
    _lines, tasks = parse_task_rows(task_board)
    in_progress = [task for task in tasks if task.thread == thread_id and task.status == "IN_PROGRESS"]
    if not in_progress:
        raise SystemExit(
            f"{branch}: missing IN_PROGRESS task in TASK_BOARD.md for {thread_id}. "
            f"Run `python3 {config.coordination_root / 'scripts/coord_task_event.py'} start --thread {thread_id} --task <TASK_ID> --note \"<scope>\"` first."
        )

    current_task = in_progress[-1]
    kickoff_ok = False
    for line in comm_log.read_text(encoding="utf-8").splitlines():
        if f"[{thread_id}] [type: kickoff]" in line and current_task.id in line:
            kickoff_ok = True
            break
    if kickoff_ok:
        return

    raise SystemExit(
        f"{branch}: missing kickoff log for {current_task.id} in COMM_LOG.md. "
        f"Run `python3 {config.coordination_root / 'scripts/coord_task_event.py'} start --thread {thread_id} --task {current_task.id} --note \"<scope>\"` first."
    )


if __name__ == "__main__":
    main()
