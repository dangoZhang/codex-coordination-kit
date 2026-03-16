#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess

from common import load_config, now_stamp, thread_map


def sanitize(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return re.sub(r"-+", "-", value).strip("-")


def branch_for_thread(thread_id: str) -> str:
    return f"codex/{thread_id}"


def parse_task_board(task_board_path: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in open(task_board_path, "r", encoding="utf-8").read().splitlines():
        if not line.startswith("|") or "|---" in line:
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) != 7 or cells[0] == "ID":
            continue
        rows.append(
            {
                "id": cells[0],
                "thread": cells[1],
                "task": cells[2],
                "status": cells[4],
            }
        )
    return rows


def main() -> None:
    try:
        config = load_config()
    except SystemExit:
        return
    threads = thread_map(config.coordination_root)
    task_board = config.coordination_root / "TASK_BOARD.md"
    comm_log = config.coordination_root / "COMM_LOG.md"
    flow_script = config.coordination_root / "thread_branch_flow.sh"

    branches = set(
        line
        for line in subprocess.run(
            ["git", "-C", str(config.target_repo), "for-each-ref", "refs/heads", "--format=%(refname:short)"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if line
    )
    created: list[tuple[str, str, str]] = []

    for row in parse_task_board(str(task_board)):
        meta = threads.get(row["thread"])
        if not meta or not meta.get("auto_branch"):
            continue
        if row["status"] != "IN_PROGRESS":
            continue

        branch_name = branch_for_thread(row["thread"])
        legacy_prefix = f"{branch_name}-"
        if branch_name in branches or any(branch.startswith(legacy_prefix) for branch in branches):
            continue

        scope = sanitize(f"{row['id']}-{row['task']}")[:48]
        subprocess.run(
            ["bash", str(flow_script), "start", "--thread", row["thread"], "--scope", scope],
            cwd=str(config.coordination_root),
            check=True,
        )
        branches.add(branch_name)
        created.append((row["thread"], branch_name, row["id"]))

    if created:
        with comm_log.open("a", encoding="utf-8") as handle:
            for thread_id, branch_name, task_id in created:
                handle.write(
                    f"\n[{now_stamp()}] [thread0] [type: update] "
                    f"Auto-created target-repo branch `{branch_name}` for `{thread_id}` after `{task_id}` became `IN_PROGRESS`.\n"
                )


if __name__ == "__main__":
    main()
