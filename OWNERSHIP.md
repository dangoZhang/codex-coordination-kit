# Ownership

## thread0 / 00-Build

- Owns: this coordination repo, hook automation, branch policy, dashboards
- Delivers: integrity of `TASK_BOARD.md`, `COMM_LOG.md`, `HANDOFFS.md`, and workflow scripts

## thread1 / 01-Backbone

- Owns: backend and service logic in the target repo
- Constraints:
  - start from the configured base branch
  - work on `codex/thread1-<scope>`
  - do not develop directly on the base branch

## thread2 / 02-Front

- Owns: frontend surface area in the target repo
- Constraints:
  - start from the configured base branch
  - work on `codex/thread2-<scope>`

## thread3 / 03-Review

- Owns: review decisions, merge risk, and the only allowed merge gate
- Delivers:
  - `ALLOW_MERGE_TO_BASE`
  - `BLOCK_MERGE_TO_BASE`

## thread4 / 04-Test

- Owns: tests, experiment records, and reproducibility evidence

## thread5 / 05-Demo

- Owns: demo flow, runbooks, and operational checks

## thread6 / 06-Paper

- Owns: validation evidence, external-facing proof, and reviewer handoff inputs

## thread7 / 07-Data

- Owns: data assets, data quality checks, and normalization logic

## thread9 / 09-Research

- Owns: technical exploration, architecture spikes, and longer-horizon workflow improvements
- Constraints:
  - tracked changes still require `codex/thread9-<scope>`

## thread11 / 11-Readme

- Owns: README, docs, onboarding notes, and workflow documentation
- Constraints:
  - tracked doc changes require `codex/thread11-<scope>`
