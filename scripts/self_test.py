#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
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


def write_fake_codex(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] != "exec":
        return 0

    output_path = None
    idx = 1
    while idx < len(args):
        current = args[idx]
        if current == "-o" and idx + 1 < len(args):
            output_path = Path(args[idx + 1])
            idx += 2
            continue
        if current in {"--cd", "--output-schema"} and idx + 1 < len(args):
            idx += 2
            continue
        idx += 1

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "decision": "ALLOW_MERGE_TO_BASE",
                    "summary": "fake codex review passed",
                    "findings": [],
                    "tests_recommended": []
                },
                ensure_ascii=False,
                indent=2,
            ) + "\\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def wait_for_file(path: Path, timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return
        time.sleep(0.2)
    raise SystemExit(f"Timed out waiting for file: {path}")


def register_project(control_root: Path, target_repo: Path, fake_codex: Path) -> None:
    run(
        [
            "bash",
            str(control_root / "register_project.sh"),
            "--target-repo",
            str(target_repo),
            "--codex-bin",
            str(fake_codex),
        ],
        cwd=control_root,
    )
    if (target_repo / ".gitignore").exists():
        status = run(["git", "status", "--short", "--", ".gitignore"], cwd=target_repo)
        if status.stdout.strip():
            run(["git", "add", ".gitignore"], cwd=target_repo)
            run(["git", "commit", "-m", "register codex coordination"], cwd=target_repo)


def exercise_thread_flow(control_root: Path, target_repo: Path, kickoff_note: str, review_ref: str, finish_note: str) -> None:
    run(["bash", str(control_root / "doctor.sh"), "--require-hooks"], cwd=control_root)
    run(
        [
            "bash",
            str(control_root / "thread_branch_flow.sh"),
            "start",
            "--thread",
            "thread2",
            "--scope",
            "board-pass",
        ],
        cwd=control_root,
    )
    scoped_branch = "codex/thread2-board-pass"
    scoped_worktree = target_repo / ".codex-worktrees" / scoped_branch.replace("/", "__")
    if run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{scoped_branch}"], cwd=target_repo, check=False).returncode != 0:
        raise SystemExit("Scoped thread2 branch should be created during self-test")
    if not scoped_worktree.exists():
        raise SystemExit("Scoped thread2 worktree should exist during self-test")

    run(
        [
            "bash",
            str(control_root / "thread_branch_flow.sh"),
            "start",
            "--thread",
            "thread1",
        ],
        cwd=control_root,
    )
    branch = "codex/thread1-mainline"
    worktree_root = target_repo / ".codex-worktrees" / branch.replace("/", "__")
    (worktree_root / "backend.txt").write_text("first change\n", encoding="utf-8")
    run(["git", "add", "backend.txt"], cwd=worktree_root)
    blocked_commit = run(["git", "commit", "-m", "should be blocked"], cwd=worktree_root, check=False)
    if blocked_commit.returncode == 0:
        raise SystemExit("pre-commit guard did not block commit without task claim / kickoff")

    run(
        [
            "python3",
            str(control_root / "scripts" / "coord_task_event.py"),
            "start",
            "--thread",
            "thread1",
            "--task",
            "T1-BACKEND-001",
            "--note",
            kickoff_note,
        ],
        cwd=control_root,
    )
    run(["git", "commit", "-m", "guard cleared"], cwd=worktree_root)

    commit_sha = run(["git", "rev-parse", "HEAD"], cwd=worktree_root).stdout.strip()
    review_path = control_root / "reviews" / f"{branch.replace('/', '__')}__{commit_sha}.json"
    wait_for_file(review_path)

    report = json.loads(review_path.read_text(encoding="utf-8"))
    if report["decision"] != "ALLOW_MERGE_TO_BASE":
        raise SystemExit(f"Unexpected review decision: {report['decision']}")

    handoffs_text = (control_root / "HANDOFFS.md").read_text(encoding="utf-8")
    if commit_sha not in handoffs_text:
        raise SystemExit("Automated review did not append a handoff record")

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
            "T1-BACKEND-001",
            "--note",
            finish_note,
            "--cleanup-source",
        ],
        cwd=control_root,
    )
    if run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=target_repo, check=False).returncode != 0:
        raise SystemExit("Persistent thread1 branch should be preserved after finish")
    if not worktree_root.exists():
        raise SystemExit("Persistent thread1 worktree should remain after finish")

    exported = run(["python3", str(control_root / "scripts" / "export_status.py")], cwd=control_root)
    payload = json.loads(exported.stdout)
    if not payload.get("threads"):
        raise SystemExit("No threads exported from self-test snapshot")


def main() -> None:
    source_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="codex-coordination-self-test-") as temp_dir:
        temp_root = Path(temp_dir)
        fake_codex = temp_root / "fake-codex"
        write_fake_codex(fake_codex)

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

        register_project(control_root, target_repo, fake_codex)
        exercise_thread_flow(
            control_root=control_root,
            target_repo=target_repo,
            kickoff_note="self-test kickoff",
            review_ref="H-T3-THREAD1-SELFTEST",
            finish_note="self test merge",
        )

        self_root = temp_root / "self-control"
        copy_control_plane(source_root, self_root)
        self_root.joinpath("runtime").mkdir(parents=True, exist_ok=True)
        init_git_repo(self_root)
        run(["git", "add", "."], cwd=self_root)
        run(["git", "commit", "-m", "seed self control plane"], cwd=self_root)

        register_project(self_root, self_root, fake_codex)
        exercise_thread_flow(
            control_root=self_root,
            target_repo=self_root,
            kickoff_note="self-register kickoff",
            review_ref="H-T3-THREAD1-SELFREGISTER",
            finish_note="self-register merge",
        )

        print("Self-test passed.")
        print(f"Control root: {control_root}")
        print(f"Target repo: {target_repo}")
        print(f"Self-register root: {self_root}")


if __name__ == "__main__":
    main()
