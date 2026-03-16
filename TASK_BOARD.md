# Task Board

Status: `TODO` | `IN_PROGRESS` | `BLOCKED` | `DONE`

Policy note: `thread1` uses the persistent backend branch `codex/thread1-mainline`, syncs it with the configured base branch before each work session, and keeps it after merge-back. Other producer threads use scoped branches like `codex/threadX-<scope>` and merge back only after `thread3` publishes `ALLOW_MERGE_TO_BASE`.

This tracked template ships with a 5-thread demo backlog for the coordination kit itself. Replace it if your project needs different roles.

| ID | Thread | Task | Owner | Status | Depends On | Output |
|---|---|---|---|---|---|---|
| T0-PM-001 | thread0 | Keep the 5-thread demo backlog, acceptance criteria, and release priorities current | thread0 | TODO | - | updated task board + handoff plan |
| T1-BACKEND-001 | thread1 | Harden bootstrap, hooks, review runtime, and existing-project registration flow | thread1 | TODO | T0-PM-001 | validated backend automation |
| T2-BOARD-001 | thread2 | Improve StatusBoard UX, sample status data, and thread guidance clarity | thread2 | TODO | T0-PM-001 | updated board frontend |
| T3-GATE-001 | thread3 | Maintain explicit review decisions for every merge-back | thread3 | TODO | T0-PM-001 | handoff with gate decision |
| T4-DOCS-001 | thread4 | Keep README, onboarding, and demo docs aligned with the live workflow | thread4 | TODO | T0-PM-001 | updated docs |
