# Task Board

Status: `TODO` | `IN_PROGRESS` | `BLOCKED` | `DONE`

Policy note: producer threads start from the configured base branch, work on `codex/threadX-<scope>`, and merge back only after `thread3` publishes `ALLOW_MERGE_TO_BASE`.

| ID | Thread | Task | Owner | Status | Depends On | Output |
|---|---|---|---|---|---|---|
| T0-SETUP-001 | thread0 | Configure target repo path and install hooks | thread0 | TODO | - | local config + installed hooks |
| T0-OPS-002 | thread0 | Audit target repo branches against coordination policy | thread0 | TODO | T0-SETUP-001 | audit report |
| T1-BRANCH-001 | thread1 | Start backend work from a clean branch/worktree | thread1 | TODO | T0-SETUP-001 | `codex/thread1-<scope>` |
| T2-BRANCH-001 | thread2 | Start frontend work from a clean branch/worktree | thread2 | TODO | T0-SETUP-001 | `codex/thread2-<scope>` |
| T3-GATE-001 | thread3 | Maintain explicit review gate decisions for every merge-back | thread3 | TODO | T0-SETUP-001 | handoff with gate decision |
| T4-TEST-001 | thread4 | Keep regression evidence aligned with approved thread changes | thread4 | TODO | T0-SETUP-001 | test evidence handoff |
| T11-DOC-001 | thread11 | Keep README and workflow docs aligned with the live process | thread11 | TODO | T0-SETUP-001 | updated docs |
