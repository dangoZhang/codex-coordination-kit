#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from common import coordination_root, load_threads


def main() -> None:
    root = coordination_root()
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
                "3. Start a fresh branch/worktree from the configured base branch:",
                f"   bash thread_branch_flow.sh start --thread {row['id']} --scope <scope>",
                "4. Write a kickoff entry in COMM_LOG.md before touching tracked target-repo files.",
                "",
                "While working:",
                "- Keep TASK_BOARD.md current.",
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
