#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from common import git, load_config

MARKER = "# managed-by-codex-coordination-kit"


def hook_path(repo: Path, hook_name: str) -> Path:
    return Path(git(repo, "rev-parse", "--git-path", f"hooks/{hook_name}"))


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
    parser = argparse.ArgumentParser(description="Install coordination post-commit hooks.")
    parser.parse_args()

    config = load_config()
    root = config.coordination_root
    coord_command = f'python3 {shlex.quote(str(root / "scripts" / "auto_branch_claim.py"))} || true'
    target_command = f'python3 {shlex.quote(str(root / "scripts" / "auto_review_gate.py"))} || true'

    coord_hook = install(root, "post-commit", coord_command)
    target_hook = install(config.target_repo, "post-commit", target_command)

    print(f"Installed coordination hook: {coord_hook}")
    print(f"Installed target hook: {target_hook}")


if __name__ == "__main__":
    main()
