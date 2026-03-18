<p align="right">
  <strong>English</strong> | <a href="docs/README.zh-CN.md">简体中文</a>
</p>

# Codex Coordination

Codex Coordination is an open-source control plane for multi-thread Codex collaboration.

It turns a normal git repository into a governed workflow with:

- a separate coordination repo
- explicit thread ownership and task flow
- branch and worktree automation
- hook-driven `codex exec` review gates
- repo-local Codex rules via `AGENTS.md`, `.codex/AGENTS.md`, `.agent/coordination.json`
- a native macOS StatusBoard

## What It Is

This repo is not your product codebase. It is the coordination layer around it.

The coordination repo owns:

- thread registry and task board
- communication and handoff logs
- hook installation
- review automation
- starter prompts
- board status export

The target repo keeps the real application code. Producer threads work in target-repo worktrees created from the configured base branch.

## Preview

Real StatusBoard window with sanitized sample data:

![StatusBoard preview](docs/images/board-preview.png)

## How It Works

1. Register a target repo.
2. Install hooks and repo-level Codex rules into that repo.
3. Claim tasks through the coordination board.
4. Start work on a thread-specific branch/worktree.
5. Commit in the target repo.
6. Let hooks trigger automated Codex review.
7. Merge only after `ALLOW_MERGE_TO_BASE`.

The default demo ships with five threads:

- `thread0`: product / coordinator
- `thread1`: backend automation on persistent branch `codex/thread1-mainline`
- `thread2`: board frontend
- `thread3`: review gate
- `thread4`: README / docs

## Deploy

```bash
git clone https://github.com/dangoZhang/codex-coordination-kit.git codex-coordination
cd codex-coordination
./scripts/register_project.sh --target-repo /path/to/target-repo
python3 scripts/generate_starter_prompts.py
./tools/StatusBoard/run.sh
```

Registration does four things:

- writes local `coordination.config.json`
- installs hooks into the coordination repo and target repo
- installs `AGENTS.md`, `.codex/AGENTS.md`, `.agent/coordination.json` into the target repo
- runs `doctor` immediately so broken wiring fails fast

Useful follow-up commands:

```bash
./scripts/doctor.sh --require-hooks
python3 scripts/self_test.py
python3 scripts/export_status.py
```

## Daily Commands

Scoped thread:

```bash
bash scripts/thread_branch_flow.sh start --thread thread2 --scope board-polish --task T2-BOARD-001 --note "kickoff note"
```

Persistent `thread1`:

```bash
bash scripts/thread_branch_flow.sh start --thread thread1 --task T1-BACKEND-001 --note "kickoff note"
```

Merge after approval:

```bash
bash scripts/thread_branch_flow.sh finish \
  --branch codex/thread2-board-polish \
  --review-ref H-T3-THREAD2-AUTO-20260314123456 \
  --task T2-BOARD-001
```

## Structure

```text
.
├── docs/
│   ├── README.zh-CN.md
│   └── images/
├── schemas/
│   └── review_gate.schema.json
├── scripts/
│   ├── *.py
│   ├── bootstrap.sh
│   ├── doctor.sh
│   ├── install_hooks.sh
│   ├── register_project.sh
│   └── thread_branch_flow.sh
├── templates/
│   └── repo/
├── tools/
│   └── StatusBoard/
├── THREADS.json
├── TASK_BOARD.md
├── COMM_LOG.md
├── HANDOFFS.md
└── THREAD_STARTER_PROMPTS.md
```

Key folders:

- `scripts/`: all executable automation entrypoints
- `docs/`: preview image and alternate-language documentation
- `templates/repo/`: repo-level instruction files installed into target repos
- `tools/StatusBoard/`: native macOS board app
- root coordination files: tracked demo control-plane state

## Notes

- The board shows the duration of the last completed run, not “how long ago” the thread last ran.
- `thread1` uses a persistent branch to reduce long-lived merge conflict fan-out.
- If a review is blocked, the system can emit rewrite requests and optionally re-invoke the applicant thread automatically.
- No account credentials are stored in this repo. Machine-specific config stays in ignored `coordination.config.json`.

## Language Switch

GitHub does not provide a native repository README language toggle. This repo uses top-of-page language links instead, which work in the GitHub web UI through normal relative markdown links. See [GitHub Docs: About READMEs](https://docs.github.com/articles/about-readmes) and [GitHub Docs: Relative links and image paths in markdown files](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes).
