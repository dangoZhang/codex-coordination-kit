#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CoordinationConfig:
    coordination_root: Path
    config_path: Path
    target_repo: Path
    base_branch: str
    worktree_root: Path
    codex_command: list[str]
    codex_exec_args: list[str]
    auto_finish_on_approve: bool
    auto_rewrite_on_block: bool
    max_auto_rewrite_attempts: int
    review_timeout_seconds: int
    persistent_branches: dict[str, str]


def coordination_root() -> Path:
    return Path(__file__).resolve().parents[1]


def config_path(root: Path | None = None) -> Path:
    if override := os.environ.get("CODEX_COORDINATION_CONFIG"):
        return Path(override).expanduser().resolve()
    root = root or coordination_root()
    return root / "coordination.config.json"


def load_config(root: Path | None = None) -> CoordinationConfig:
    root = root or coordination_root()
    path = config_path(root)
    if not path.exists():
        raise SystemExit(
            "Missing coordination.config.json. Run ./bootstrap.sh --target-repo /path/to/repo first."
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    target_repo = Path(raw["target_repo"]).expanduser().resolve()
    worktree_root_value = raw.get("worktree_root") or str(target_repo / ".codex-worktrees")
    worktree_root = Path(worktree_root_value).expanduser().resolve()
    codex_command = list(raw.get("codex_command") or ["codex"])
    codex_exec_args = list(raw.get("codex_exec_args") or [])

    return CoordinationConfig(
        coordination_root=root,
        config_path=path,
        target_repo=target_repo,
        base_branch=raw["base_branch"],
        worktree_root=worktree_root,
        codex_command=codex_command,
        codex_exec_args=codex_exec_args,
        auto_finish_on_approve=bool(raw.get("auto_finish_on_approve", False)),
        auto_rewrite_on_block=bool(raw.get("auto_rewrite_on_block", False)),
        max_auto_rewrite_attempts=max(0, int(raw.get("max_auto_rewrite_attempts", 2))),
        review_timeout_seconds=max(30, int(raw.get("review_timeout_seconds", 600))),
        persistent_branches=dict(raw.get("persistent_branches") or {}),
    )


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        capture_output=True,
        text=True,
    )


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = run(["git", "-C", str(repo), *args], check=check)
    return result.stdout.strip()


def git_ref_exists(repo: Path, ref: str) -> bool:
    return run(
        ["git", "-C", str(repo), "show-ref", "--verify", "--quiet", ref],
        check=False,
    ).returncode == 0


def command_exists(command: str) -> bool:
    if "/" in command:
        path = Path(command).expanduser()
        return path.exists() and os.access(path, os.X_OK)
    return shutil.which(command) is not None


def current_worktree(default_repo: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return default_repo.resolve()


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def now_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_compact() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def load_threads(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or coordination_root()
    return json.loads((root / "THREADS.json").read_text(encoding="utf-8"))


def thread_map(root: Path | None = None) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in load_threads(root)}


def repo_relative_path(parent: Path, child: Path, *, assume_directory: bool = False) -> str | None:
    try:
        rel = child.resolve().relative_to(parent.resolve())
    except ValueError:
        return None
    value = str(rel).replace("\\", "/")
    if value == ".":
        return None
    return f"{value}/" if assume_directory or child.is_dir() else value


def repo_instruction_files(target_repo: Path) -> list[Path]:
    candidates = [
        target_repo / "AGENTS.md",
        target_repo / ".codex" / "AGENTS.md",
        target_repo / ".codex" / "instructions.md",
        target_repo / ".agent" / "coordination.md",
        target_repo / ".agent" / "coordination.json",
    ]
    return [path for path in candidates if path.is_file()]


def repo_instruction_paths(target_repo: Path) -> list[str]:
    rendered: list[str] = []
    for path in repo_instruction_files(target_repo):
        rel = repo_relative_path(target_repo, path)
        rendered.append(rel or path.name)
    return rendered


def render_repo_instruction_block(target_repo: Path, max_chars: int = 12000) -> str:
    sections: list[str] = []
    remaining = max_chars
    for path in repo_instruction_files(target_repo):
        rel = repo_relative_path(target_repo, path) or path.name
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        if len(text) > 3000:
            text = text[:3000].rstrip() + "\n...[truncated]"
        section = f"File: {rel}\n{text}"
        if len(section) > remaining:
            break
        sections.append(section)
        remaining -= len(section) + 2
    return "\n\n".join(sections)
