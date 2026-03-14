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
                f"You are `{row['name']}` and own `{row['role']}`.",
                "Read these coordination files before doing work:",
                "- README.md",
                "- OWNERSHIP.md",
                "- THREAD_BRIEFS.md",
                "- TASK_BOARD.md",
                "- COMM_LOG.md",
                "- HANDOFFS.md",
                "- THREADS.json",
                "Only take work that matches your ownership.",
                "Before editing tracked target-repo files, create a fresh branch/worktree from the configured base branch:",
                f"bash thread_branch_flow.sh start --thread {row['id']} --scope <scope>",
                "Write a kickoff entry in COMM_LOG.md, keep status current in TASK_BOARD.md, and finish with a handoff.",
                "Do not merge back without an explicit thread3 gate decision.",
                "```",
                "",
            ]
        )

    (root / "THREAD_STARTER_PROMPTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
