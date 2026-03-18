#!/usr/bin/env python3
from __future__ import annotations

from common import coordination_root, load_config, load_threads, repo_instruction_paths


def default_persistent_branches(threads: list[dict[str, object]]) -> dict[str, str]:
    if any(str(row.get("id")) == "thread1" for row in threads):
        return {"thread1": "codex/thread1-mainline"}
    return {}


def main() -> None:
    root = coordination_root()
    threads = load_threads(root)
    config = None
    try:
        config = load_config(root)
        base_branch = config.base_branch
    except SystemExit:
        base_branch = "<base-branch>"
    persistent_branches = config.persistent_branches if config is not None else default_persistent_branches(threads)
    repo_instruction_text = ""
    if config is not None:
        paths = repo_instruction_paths(config.target_repo)
        if paths:
            repo_instruction_text = ", ".join(f"`{path}`" for path in paths)
    lines = [
        "# Thread Starter Prompts",
        "",
        "Each section below can be copied into the matching Codex thread.",
        "",
    ]

    for row in threads:
        persistent_branch = persistent_branches.get(row["id"])
        if persistent_branch:
            start_command = (
                f'bash scripts/thread_branch_flow.sh start --thread {row["id"]} --task <TASK_ID> --note "kickoff note"'
            )
            branch_instruction = (
                f"4. Reuse the configured persistent branch `{persistent_branch}` and sync it with "
                f"`{base_branch}` before coding:"
            )
        else:
            start_command = (
                f'bash scripts/thread_branch_flow.sh start --thread {row["id"]} --scope <scope> --task <TASK_ID> --note "kickoff note"'
            )
            branch_instruction = (
                f"4. Start a fresh scoped branch/worktree from `{base_branch}` with:"
            )
        lines.extend(
            [
                f"## {row['name']} / `{row['id']}`",
                "",
                "```text",
                f"You are `{row['name']}` (`{row['id']}`) and own `{row['role']}`.",
                "",
                "Before coding:",
                "1. Read README.md, OWNERSHIP.md, THREAD_BRIEFS.md, TASK_BOARD.md, COMM_LOG.md, HANDOFFS.md, and THREADS.json.",
                (
                    f"2. In the target repo, also read {repo_instruction_text} before editing."
                    if repo_instruction_text
                    else "2. Only claim work that stays inside your ownership lane."
                ),
                "3. Only claim work that stays inside your ownership lane.",
                branch_instruction,
                f"   {start_command}",
                "5. Do not commit until TASK_BOARD.md is IN_PROGRESS for your task and COMM_LOG.md has a kickoff line containing the task ID.",
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

    (root / "THREAD_STARTER_PROMPTS.md").write_text(
        "\n".join(line for line in lines if line != ""),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
