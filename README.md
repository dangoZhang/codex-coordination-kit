# Codex Coordination

[中文说明](README.zh-CN.md)

Codex Coordination turns a normal git repository into a multi-thread Codex workflow with a separate control plane, automated review gates, and a native macOS status board.

It is designed for real project use, not just prompts:

- separate control repo and product repo
- task board, comm log, handoff records
- thread branch and worktree automation
- hook-driven `codex exec` review gate
- repo-local guidance via `AGENTS.md`, `.codex/AGENTS.md`, `.agent/coordination.json`
- status export for board, bots, or custom tooling

## Preview

Real StatusBoard window with sanitized sample data:

![StatusBoard preview](docs/images/board-preview.png)

## Why This Exists

Most Codex collaboration setups break down in the same places:

- thread ownership is unclear
- branches drift and conflict
- reviews are easy to skip
- local machine paths leak into tracked files
- repo-specific rules are not enforced consistently

This project solves that with a reusable control plane and installable repo-level rules. The target repo stays clean, while the coordination repo handles process, logs, hooks, and review flow.

## Core Pieces

- `THREADS.json`: thread registry
- `TASK_BOARD.md`: task queue and ownership
- `COMM_LOG.md`: kickoff, blocker, and progress log
- `HANDOFFS.md`: review and merge handoffs
- `thread_branch_flow.sh`: start, audit, and finish branch flow
- `register_project.sh`: one-step setup for an existing repo
- `doctor.sh`: health check for config, hooks, and status export
- `tools/StatusBoard/`: native macOS board

## Quick Start

```bash
cd /path/to/codex-coordination
./register_project.sh --target-repo /path/to/target-repo
python3 scripts/generate_starter_prompts.py
tools/StatusBoard/run.sh
```

What registration does:

- writes local `coordination.config.json`
- installs hooks into the coordination repo and target repo
- installs `AGENTS.md`, `.codex/AGENTS.md`, `.agent/coordination.json` into the target repo
- runs `doctor` so setup failures are visible immediately

If the target repo only has `origin/main` or `origin/master`, bootstrap creates the local tracking branch automatically.

## Default Demo

The tracked template ships with a self-hosted 5-thread demo:

- `thread0`: product / coordinator
- `thread1`: backend automation
- `thread2`: board frontend
- `thread3`: review gate
- `thread4`: README / docs

`thread1` uses a persistent branch by default:

- `codex/thread1-mainline`

Every new task syncs that branch to the latest base branch first. Other producer threads still use scoped branches such as `codex/thread2-board-polish`.

## Standard Flow

1. Claim a task in `TASK_BOARD.md`.
2. Start a thread branch or let hooks create it.
3. Work only inside the generated target-repo worktree.
4. Commit on the thread branch.
5. Let hooks trigger automated Codex review.
6. Merge after `ALLOW_MERGE_TO_BASE`, manually or via `auto_finish_on_approve`.

Scoped thread example:

```bash
bash thread_branch_flow.sh start --thread thread2 --scope board-polish --task T2-BOARD-001 --note "kickoff note"
```

Persistent `thread1` example:

```bash
bash thread_branch_flow.sh start --thread thread1 --task T1-BACKEND-001 --note "kickoff note"
```

Merge after review:

```bash
bash thread_branch_flow.sh finish \
  --branch codex/thread2-board-polish \
  --review-ref H-T3-THREAD2-AUTO-20260314123456 \
  --task T2-BOARD-001
```

## Hooks And Review Gate

Installed hooks enforce the collaboration loop:

- coordination repo `post-commit`: auto-creates worktrees for claimed tasks
- target repo `pre-commit`: blocks commits without a valid in-progress task and kickoff log
- target repo `post-commit`: runs asynchronous `codex exec --output-schema` review
- target repo `pre-push`: re-triggers review as a safety net

Blocked reviews can optionally emit rewrite requests and automatically re-invoke the applicant thread. The review runner also keeps per-branch locks so repeated commits do not start overlapping reviews.

## Repo-Level Codex Rules

The target repo gets three installable files:

- `AGENTS.md`
- `.codex/AGENTS.md`
- `.agent/coordination.json`

These files are the main mechanism for repo-specific behavior. They define ownership boundaries, collaboration rules, and privacy constraints without leaking local account state or machine-specific auth files.

If a target repo already has custom versions of these files and they are not managed by this project, bootstrap preserves them instead of overwriting them.

## Health Check

```bash
./doctor.sh --require-hooks
python3 scripts/self_test.py
```

`doctor` verifies:

- required coordination files
- target repo wiring
- base branch availability
- repo-level agent config presence
- `codex` executable availability
- status export health
- installed hooks

## StatusBoard Notes

The macOS board shows the duration of the last completed run for each thread, not “how long ago it ran”. Registration and collaboration help panels open in detached windows so they do not disappear when the menu bar popover closes.

## Privacy

- machine-specific settings live in ignored `coordination.config.json`
- no credentials are bundled into this repo
- no account information is written into `AGENTS.md`, `.codex`, or `.agent`
- preview assets use sanitized sample data only

If `codex exec` already works on the machine, no extra login is required for this project. If that machine is not authenticated, automated review cannot run until the local Codex CLI is logged in.
