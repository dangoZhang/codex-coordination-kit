# Codex Project Instructions

<!-- managed-by-codex-coordination-kit -->

When Codex is launched inside this repository, use this repo-local contract in addition to any user prompt.

Startup order:

1. Read `AGENTS.md`.
2. Read `.agent/coordination.json`.
3. Inspect only the files relevant to the assigned lane before editing.

Implementation rules:

- Backend work belongs in backend or service modules.
- Frontend work belongs in UI and asset files.
- Tests belong under the project test directories.
- Documentation belongs in README and docs content.
- Prefer minimal, reviewable patches.

Safety rules:

- Never expose local auth state from `~/.codex/`.
- Never hard-code account identifiers, API keys, cookies, or personal filesystem paths into tracked files.
- If a change depends on local-only environment state, document the requirement instead of committing the secret.
