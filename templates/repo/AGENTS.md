# Demo Repo Agent Guide

<!-- managed-by-codex-coordination-kit -->

This repository is designed to be worked on by Codex threads and automated review agents.

Read these repository-local config files before making changes:

- `.codex/AGENTS.md`
- `.agent/coordination.json`

Working rules:

- Treat backend code, frontend code, tests, docs, and skills as separate ownership lanes.
- Keep changes scoped. Do not mix unrelated frontend, backend, and documentation edits in one patch unless the task requires it.
- Prefer fixing or extending tests alongside behavior changes.
- Do not commit secrets, personal tokens, local absolute paths, or machine-specific account data.
- Preserve the collaboration workflow driven by the external coordination control plane and its task / handoff logs.
