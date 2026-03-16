#!/usr/bin/env python3
from __future__ import annotations

from common import coordination_root, load_config, load_threads


def main() -> None:
    root = coordination_root()
    try:
        config = load_config(root)
        base_branch = config.base_branch
    except SystemExit:
        base_branch = "<base-branch>"
    threads = load_threads(root)
    lines = [
        "# Thread Starter Prompts",
        "",
        "Each section below can be copied into the matching Codex thread.",
        "",
    ]

    for row in threads:
        lines.extend(
            [
                f"## {row['name']} / `{row['id']}`",
                "",
                "```text",
                f"You are `{row['name']}` (`{row['id']}`) and own `{row['role']}`.",
                "",
                "Before coding:",
                "1. Read README.md, OWNERSHIP.md, THREAD_BRIEFS.md, TASK_BOARD.md, COMM_LOG.md, HANDOFFS.md, and THREADS.json.",
                "2. Only claim work that stays inside your ownership lane.",
                f"3. Start a fresh branch/worktree from the configured base branch `{base_branch}`:",
                f'   bash thread_branch_flow.sh start --thread {row["id"]} --scope <scope> --task <TASK_ID> --note "kickoff note"',
                "4. Do not commit until TASK_BOARD.md is IN_PROGRESS for your task and COMM_LOG.md has a kickoff line containing the task ID.",
                "",
                "While working:",
                "- Keep TASK_BOARD.md and COMM_LOG.md current.",
                "- Stay on your assigned branch/worktree.",
                "- Finish with a clear handoff when the branch is ready.",
                "",
                "If thread3 blocks the branch:",
                "- Read the newest review report in reviews/.",
                "- Read the newest rewrite request in rewrite_requests/.",
                "- Make the smallest safe fix on the same branch.",
                "- Run focused validation and create a new commit.",
                "- Do not merge back without an explicit thread3 gate decision.",
                "```",
                "",
            ]
        )

    (root / "THREAD_STARTER_PROMPTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
