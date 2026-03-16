# Thread Briefs

## Shared Startup Checklist

Every thread should:

1. Read `README.md`, `OWNERSHIP.md`, `THREAD_BRIEFS.md`, `TASK_BOARD.md`, `COMM_LOG.md`, `HANDOFFS.md`, and `THREADS.json`.
2. Claim only work that matches its ownership.
3. Start or resume the thread's long-lived branch/worktree and sync it with the configured base branch.
4. Write a kickoff line in `COMM_LOG.md`.
5. Finish with a handoff for review, testing, or merge action.

## Default Demo Template

This repo ships with a compact 5-thread template so the coordination kit can demo itself out of the box:

- `thread0` / `00-Product`: product scope, task board, acceptance criteria, and release coordination
- `thread1` / `01-Backend`: Python automation, hooks, review backend, and export pipeline
- `thread2` / `02-Board`: native StatusBoard UI, sample data, and collaboration UX
- `thread3` / `03-Review`: review decisions, blocker findings, and merge gate output
- `thread4` / `04-Readme`: README, onboarding, demo narrative, and operator documentation

## thread0 / 00-Product

- Focus: backlog quality, handoff clarity, acceptance criteria, and release sequencing

## thread1 / 01-Backend

- Focus: bootstrap, hooks, guardrails, automation scripts, and review/runtime backend behavior

## thread2 / 02-Board

- Focus: StatusBoard SwiftUI frontend, thread guidance UX, sample snapshots, and board usability

## thread3 / 03-Review

- Focus: bugs, regressions, test gaps, and merge safety

## thread4 / 04-Readme

- Focus: README, docs, onboarding, release notes, and demo explainers
