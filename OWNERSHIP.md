# Ownership

## thread0 / 00-Product

- Owns: product scope, task board quality, acceptance criteria, and the default demo narrative
- Delivers: coherent `TASK_BOARD.md`, clear handoff requests, and release-ready prioritization

## thread1 / 01-Backend

- Owns: Python scripts, hook orchestration, review/runtime backend, and integration wiring
- Constraints:
  - start from the configured base branch
  - keep work on the long-lived `codex/thread1` branch
  - do not develop directly on the base branch

## thread2 / 02-Board

- Owns: the macOS StatusBoard frontend, sample snapshots, and board interaction quality
- Constraints:
  - start from the configured base branch
  - keep work on the long-lived `codex/thread2` branch

## thread3 / 03-Review

- Owns: review decisions, merge risk, and the only allowed merge gate
- Delivers:
  - `ALLOW_MERGE_TO_BASE`
  - `BLOCK_MERGE_TO_BASE`

## thread4 / 04-Readme

- Owns: README, onboarding, demo docs, release notes, and operator instructions
- Constraints:
  - tracked doc changes stay on the long-lived `codex/thread4` branch
