#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        output = "\n".join(part for part in ((result.stdout or "").strip(), (result.stderr or "").strip()) if part)
        raise SystemExit(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{output}")
    return result


def copy_control_plane(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
            ".git",
            "coordination.config.json",
            ".DS_Store",
            ".build",
            "__pycache__",
            "runtime",
            "reviews",
            "rewrite_requests",
        ),
    )


def init_git_repo(path: Path, branch: str = "main") -> None:
    run(["git", "init", "-b", branch], cwd=path)
    run(["git", "config", "user.name", "Codex Test"], cwd=path)
    run(["git", "config", "user.email", "codex-test@example.invalid"], cwd=path)


def write_allow_handoff(control_root: Path, review_ref: str) -> None:
    handoffs = control_root / "HANDOFFS.md"
    handoffs.write_text(
        handoffs.read_text(encoding="utf-8")
        + (
            f"\n\n## Handoff: `{review_ref}`\n"
            "- From: `thread3`\n"
            "- To: `thread1`\n"
            "- Verification done:\n"
            "  - manual smoke\n"
            "- Requested action:\n"
            "  - ALLOW_MERGE_TO_BASE\n"
        ),
        encoding="utf-8",
    )


def main() -> None:
    source_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="codex-coordination-self-test-") as temp_dir:
        temp_root = Path(temp_dir)
        control_root = temp_root / "control"
        target_repo = temp_root / "target"

        copy_control_plane(source_root, control_root)
        control_root.joinpath("runtime").mkdir(parents=True, exist_ok=True)

        init_git_repo(control_root)
        run(["git", "add", "."], cwd=control_root)
        run(["git", "commit", "-m", "seed control plane"], cwd=control_root)

        target_repo.mkdir()
        init_git_repo(target_repo)
        (target_repo / "README.md").write_text("# Demo Target\n", encoding="utf-8")
        run(["git", "add", "README.md"], cwd=target_repo)
        run(["git", "commit", "-m", "seed target"], cwd=target_repo)

        run(
            [
                "bash",
                str(control_root / "register_project.sh"),
                "--target-repo",
                str(target_repo),
                "--codex-bin",
                "/usr/bin/true",
            ],
            cwd=control_root,
        )
        if (target_repo / ".gitignore").exists():
            run(["git", "add", ".gitignore"], cwd=target_repo)
            run(["git", "commit", "-m", "register codex coordination"], cwd=target_repo)

        run(
            [
                "python3",
                str(control_root / "scripts" / "coord_task_event.py"),
                "start",
                "--thread",
                "thread1",
                "--task",
                "T1-BRANCH-001",
                "--note",
                "self-test kickoff",
            ],
            cwd=control_root,
        )
        run(["python3", str(control_root / "scripts" / "auto_branch_claim.py")], cwd=control_root)

        branch = next(
            line
            for line in run(
                ["git", "-C", str(target_repo), "for-each-ref", "refs/heads", "--format=%(refname:short)"],
            ).stdout.splitlines()
            if line.startswith("codex/thread1-")
        )
        worktree_root = target_repo / ".codex-worktrees" / branch.replace("/", "__")
        (worktree_root / "backend.txt").write_text("backend change\n", encoding="utf-8")
        run(["git", "add", "backend.txt"], cwd=worktree_root)
        run(["git", "commit", "-m", "self test change"], cwd=worktree_root)

        review_ref = "H-T3-THREAD1-SELFTEST"
        write_allow_handoff(control_root, review_ref)
        run(
            [
                "bash",
                str(control_root / "thread_branch_flow.sh"),
                "finish",
                "--branch",
                branch,
                "--review-ref",
                review_ref,
                "--task",
                "T1-BRANCH-001",
                "--note",
                "self test merge",
                "--cleanup-source",
            ],
            cwd=control_root,
        )

        exported = run(["python3", str(control_root / "scripts" / "export_status.py")], cwd=control_root)
        payload = json.loads(exported.stdout)
        if not payload.get("threads"):
            raise SystemExit("No threads exported from self-test snapshot")

        print("Self-test passed.")
        print(f"Control root: {control_root}")
        print(f"Target repo: {target_repo}")


if __name__ == "__main__":
    main()
