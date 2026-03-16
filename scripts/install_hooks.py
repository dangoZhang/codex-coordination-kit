#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from common import git, load_config

MARKER = "# managed-by-codex-coordination-kit"


def hook_path(repo: Path, hook_name: str) -> Path:
    raw = Path(git(repo, "rev-parse", "--git-path", f"hooks/{hook_name}"))
    return raw if raw.is_absolute() else repo / raw


def build_hook(managed_command: str, backup_name: str | None) -> str:
    backup_block = ""
    if backup_name:
        backup_block = f"""if [ -x "$(dirname "$0")/{backup_name}" ]; then
  "$(dirname "$0")/{backup_name}" "$@"
fi

"""

    return f"""#!/usr/bin/env bash
set -euo pipefail
{MARKER}

{backup_block}{managed_command}
"""


def install(repo: Path, hook_name: str, managed_command: str) -> Path:
    path = hook_path(repo, hook_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_name = f"{hook_name}.pre-codex-coordination" if path.with_name(f"{hook_name}.pre-codex-coordination").exists() else None

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if MARKER in existing:
        pass
    elif existing.strip():
        backup_name = f"{hook_name}.pre-codex-coordination"
        backup_path = path.with_name(backup_name)
        if not backup_path.exists():
            path.rename(backup_path)
    else:
        backup_name = None

    content = build_hook(managed_command, backup_name)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Install coordination hooks for the control-plane and target repo.")
    parser.parse_args()

    config = load_config()
    root = config.coordination_root
    hook_log_dir = root / "runtime" / "hook_logs"
    coord_command = f'python3 {shlex.quote(str(root / "scripts" / "auto_branch_claim.py"))} || true'
    target_guard_command = f'python3 {shlex.quote(str(root / "scripts" / "coord_commit_guard.py"))}'
    target_post_command = (
        f'mkdir -p {shlex.quote(str(hook_log_dir))}\n'
        f'nohup python3 {shlex.quote(str(root / "scripts" / "auto_review_gate.py"))} '
        f'>> {shlex.quote(str(hook_log_dir / "auto_review_post_commit.log"))} 2>&1 &'
    )
    target_push_command = (
        f'mkdir -p {shlex.quote(str(hook_log_dir))}\n'
        f'nohup python3 {shlex.quote(str(root / "scripts" / "auto_review_gate.py"))} '
        f'>> {shlex.quote(str(hook_log_dir / "auto_review_pre_push.log"))} 2>&1 &'
    )

    coord_hook = install(root, "post-commit", coord_command)
    target_pre_commit_hook = install(config.target_repo, "pre-commit", target_guard_command)
    target_post_commit_hook = install(config.target_repo, "post-commit", target_post_command)
    target_pre_push_hook = install(config.target_repo, "pre-push", target_push_command)

    print(f"Installed coordination hook: {coord_hook}")
    print(f"Installed target pre-commit hook: {target_pre_commit_hook}")
    print(f"Installed target post-commit hook: {target_post_commit_hook}")
    print(f"Installed target pre-push hook: {target_pre_push_hook}")


if __name__ == "__main__":
    main()
