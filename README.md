# Codex Coordination Kit

[中文说明](README.zh-CN.md)

Codex Coordination Kit turns a plain git repo into a multi-thread Codex workflow with:

- an isolated coordination control plane repo
- task board, comm log, and handoff records
- branch and worktree policy enforcement
- hook-driven auto branch creation on task claim
- hook-driven Codex review gates on thread branch commits
- machine-readable status export for dashboards or bots

The project is a reusable, open-source rewrite of a live private coordination workspace. Hard-coded repo paths were removed and replaced with a local gitignored config file plus bootstrap scripts.

## Preview

Actual macOS StatusBoard preview window, captured with sanitized sample data:

![Sanitized board preview](docs/images/board-preview.png)

## What Lives Here

- `THREADS.json`: active Codex thread registry
- `TASK_BOARD.md`: work queue with ownership and status
- `COMM_LOG.md`: kickoff, blocker, and update log
- `HANDOFFS.md`: formal review and merge handoffs
- `thread_branch_flow.sh`: start, audit, and finish branch/worktree flow
- `install_hooks.sh`: installs post-commit hooks into both repos
- `scripts/auto_branch_claim.py`: creates worktrees when `IN_PROGRESS` tasks are claimed
- `scripts/auto_review_gate.py`: runs `codex exec` reviews against thread branches
- `scripts/export_status.py`: emits JSON for dashboards or custom boards
- `tools/StatusBoard/`: macOS menu bar app for a native status board
- `rewrite_requests/`: gitignored rewrite recall artifacts emitted after blocked reviews

## Repo Model

This repo is the control plane. Your product repo stays separate.

The control plane keeps governance, logs, and automation. The product repo keeps tracked application code. Thread work happens in worktrees created from the target repo base branch.

## Quick Start

1. Clone this repo where you want the control plane to live.
2. Bootstrap it against your target repo.
3. Install hooks.
4. Regenerate starter prompts if you change `THREADS.json`.

```bash
cd /path/to/codex-coordination-kit
./bootstrap.sh --target-repo /path/to/target-repo
./install_hooks.sh
python3 scripts/generate_starter_prompts.py
python3 scripts/export_status.py
```

Bootstrap writes `coordination.config.json`, which is gitignored so local paths stay out of the public repo.

Start the native macOS board:

```bash
tools/StatusBoard/run.sh
```

Open the board in a normal preview window instead of the menu bar extra:

```bash
tools/StatusBoard/run.sh --preview-window
```

Run the board against the bundled sanitized sample snapshot:

```bash
CODEX_COORDINATION_SNAPSHOT_FILE=tools/StatusBoard/SampleData/sample_status.json \
tools/StatusBoard/run.sh --preview-window
```

The board shows the duration of the last completed thread run, measured from the latest `kickoff` log to the latest follow-up log for that same run. Thread registration and collaboration guidance open in detached windows, so you do not lose the form when the menubar popover closes.

## Standard Workflow

1. Claim a task in `TASK_BOARD.md` and move it to `IN_PROGRESS`.
2. Let the coordination repo hook auto-create a compliant branch, or create one manually:

```bash
bash thread_branch_flow.sh start --thread thread11 --scope docs-refresh
```

3. Work only inside the generated target-repo worktree.
4. Commit on the thread branch.
5. Let the target repo hook trigger an automated Codex review.
6. If the review handoff includes `ALLOW_MERGE_TO_BASE`, merge manually or enable `auto_finish_on_approve` in local config.

Audit current branches:

```bash
bash thread_branch_flow.sh audit
```

Merge after an approved handoff:

```bash
bash thread_branch_flow.sh finish \
  --branch codex/thread11-docs-refresh \
  --review-ref H-T3-THREAD11-AUTO-20260314123456 \
  --cleanup-source
```

## Hook Behavior

`install_hooks.sh` installs `post-commit` hooks in both repos:

- coordination repo `post-commit`: scans `TASK_BOARD.md` for `IN_PROGRESS` rows and auto-creates thread worktrees for threads with `auto_branch: true`
- target repo `post-commit`: runs `codex exec --output-schema` against the current thread branch and writes the gate result into `reviews/`, `HANDOFFS.md`, and `COMM_LOG.md`
- if a review returns `BLOCK_MERGE_TO_BASE`, the kit emits a rewrite request under `rewrite_requests/` and can optionally re-invoke the applicant thread with `codex exec`
- the review hook keeps a per-branch lock under `runtime/` so repeated commits do not launch overlapping reviews, and it will automatically chase the newest commit on the same branch if a newer commit lands while review is still running

The installer preserves an existing `post-commit` hook by moving it to `post-commit.pre-codex-coordination` and chaining to it.

## Does This Require A Codex Login

The kit itself does not bundle credentials and does not log in for you.

- If `codex exec` already works on the machine where hooks run, no extra login step is needed for this repo.
- If that machine is not authenticated yet, the automated review hook will not be able to run Codex reviews until the local Codex CLI is logged in.
- `coordination.config.json` is gitignored and should contain only local paths and runtime options, never tokens.

## Privacy

- The repo tracks no local machine paths by default.
- Bootstrap writes machine-specific settings into the ignored `coordination.config.json`.
- The preview image comes from the real SwiftUI StatusBoard app and uses sanitized sample data only.
- Avoid publishing personal git author metadata when open-sourcing your own fork. Using a generic bot identity or a GitHub noreply address is safer than a personal email.

## Configuration

Tracked file: `coordination.config.example.json`

Local runtime file: `coordination.config.json`

Fields:

- `target_repo`: absolute path to the product repo
- `base_branch`: branch used as the merge base, usually `main` or `master`
- `worktree_root`: absolute path for generated worktrees
- `codex_command`: command prefix used to invoke Codex, for example `["codex"]`
- `codex_exec_args`: extra args added before the review prompt, for example a model flag
- `auto_finish_on_approve`: whether an approved review should immediately run `finish`
- `auto_rewrite_on_block`: whether a blocked review should automatically re-invoke the applicant thread on the current worktree
- `max_auto_rewrite_attempts`: loop guard for auto rewrite retries on the same branch
- `review_timeout_seconds`: timeout for a single automated review invocation before the hook logs a blocker and exits

## Git Notes

- Keep this repo separate from the target repo when possible.
- If `worktree_root` is inside the target repo, bootstrap will add it to the target repo `.gitignore`.
- If the control plane repo itself is nested under the target repo, bootstrap will also add the coordination folder to the target repo `.gitignore`.
- This repo does not assume `master`; the base branch is configurable.

## Publishing

The repo is ready to be published as a public template or a normal public repo. Only generic defaults are tracked. All machine-specific paths stay in the ignored local config file.
