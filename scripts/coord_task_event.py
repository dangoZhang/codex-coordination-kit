#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from common import load_config, now_stamp


@dataclass
class TaskRow:
    id: str
    thread: str
    title: str
    owner: str
    status: str
    depends_on: str
    output: str
    line_no: int


def parse_task_rows(task_board: Path) -> tuple[list[str], list[TaskRow]]:
    lines = task_board.read_text(encoding="utf-8").splitlines()
    tasks: list[TaskRow] = []
    for idx, line in enumerate(lines, start=1):
        if not line.startswith("|") or "|---" in line:
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) != 7 or cells[0] == "ID":
            continue
        tasks.append(
            TaskRow(
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
    return lines, tasks


def find_task(tasks: list[TaskRow], thread: str, task_id: str | None, target_statuses: tuple[str, ...]) -> TaskRow:
    if task_id:
        for task in tasks:
            if task.thread == thread and task.id == task_id:
                return task
        raise SystemExit(f"Task not found for {thread}: {task_id}")

    candidates = [task for task in tasks if task.thread == thread and task.status in target_statuses]
    if not candidates:
        raise SystemExit(f"No task for {thread} with status in {target_statuses}")
    return candidates[-1]


def rewrite_task_status(task_board: Path, task: TaskRow, new_status: str) -> None:
    lines, _tasks = parse_task_rows(task_board)
    line_index = task.line_no - 1
    lines[line_index] = (
        f"| {task.id} | {task.thread} | {task.title} | {task.owner} | {new_status} | {task.depends_on} | {task.output} |"
    )
    task_board.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_log(comm_log: Path, thread: str, kind: str, message: str) -> None:
    with comm_log.open("a", encoding="utf-8") as fh:
        fh.write(f"[{now_stamp()}] [{thread}] [type: {kind}] {message}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update TASK_BOARD.md and COMM_LOG.md together.")
    parser.add_argument("action", choices=["start", "finish", "block", "retry"])
    parser.add_argument("--thread", required=True)
    parser.add_argument("--task")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    config = load_config()
    task_board = config.coordination_root / "TASK_BOARD.md"
    comm_log = config.coordination_root / "COMM_LOG.md"
    _lines, tasks = parse_task_rows(task_board)

    note = args.note.strip()
    if args.action == "start":
        task = find_task(tasks, args.thread, args.task, ("TODO", "BLOCKED", "IN_PROGRESS"))
        rewrite_task_status(task_board, task, "IN_PROGRESS")
        msg = f"Claimed {task.id} on `{task.thread}`"
        msg += f" - {note}" if note else f" - {task.title}"
        append_log(comm_log, args.thread, "kickoff", msg + ".")
        return

    if args.action == "finish":
        task = find_task(tasks, args.thread, args.task, ("IN_PROGRESS", "BLOCKED"))
        rewrite_task_status(task_board, task, "DONE")
        msg = f"Completed {task.id}"
        msg += f" - {note}" if note else f" - {task.title}"
        append_log(comm_log, args.thread, "update", msg + ".")
        return

    if args.action == "block":
        task = find_task(tasks, args.thread, args.task, ("IN_PROGRESS", "TODO"))
        rewrite_task_status(task_board, task, "BLOCKED")
        msg = f"Blocked {task.id}"
        msg += f" - {note}" if note else f" - {task.title}"
        append_log(comm_log, args.thread, "blocker", msg + ".")
        return

    task = find_task(tasks, args.thread, args.task, ("BLOCKED", "TODO", "IN_PROGRESS"))
    rewrite_task_status(task_board, task, "IN_PROGRESS")
    msg = f"Resumed {task.id}"
    msg += f" - {note}" if note else f" - {task.title}"
    append_log(comm_log, args.thread, "update", msg + ".")


if __name__ == "__main__":
    main()
