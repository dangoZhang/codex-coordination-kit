#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import re
import subprocess
from pathlib import Path

from common import current_worktree, load_config, now_compact, now_date, now_stamp, thread_map


def detect_thread(branch: str, threads: dict[str, dict]) -> str | None:
    match = re.match(r"^codex/(thread[0-9]+)-[a-z0-9-]+$", branch)
    if not match:
        return None
    thread_id = match.group(1)
    return thread_id if thread_id in threads else None


def current_branch(target_repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(target_repo), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def current_commit(target_repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(target_repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def git_ok(target_repo: Path, *args: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["git", "-C", str(target_repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    text = (result.stdout or result.stderr).strip()
    return result.returncode == 0, text


def branch_head_sha(target_repo: Path, branch: str) -> str | None:
    ok, text = git_ok(target_repo, "rev-parse", f"refs/heads/{branch}")
    return text if ok and text else None


def append_failure_log(comm_log: Path, branch: str, message: str) -> None:
    with comm_log.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n[{now_stamp()}] [thread3] [type: blocker] "
            f"Automated review failed for `{branch}`: {message}\n"
        )


def append_timeout_log(comm_log: Path, branch: str, commit_sha: str, timeout_seconds: int) -> None:
    with comm_log.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n[{now_stamp()}] [thread3] [type: blocker] "
            f"Automated review timed out after {timeout_seconds}s for `{branch}` commit `{commit_sha}`. "
            f"Resubmit manually or reduce the diff size.\n"
        )


def run_codex_review(
    target_repo: Path,
    output_file: Path,
    branch: str,
    commit_sha: str,
    config,
) -> dict:
    changed_files = subprocess.run(
        ["git", "-C", str(target_repo), "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    changed_block = "\n".join(f"- {name}" for name in changed_files[:40]) if changed_files else "- (unable to resolve changed files)"
    prompt = f"""
You are acting as thread3 / 03-Review for this repository.
Review commit {commit_sha} on branch {branch}.
Prioritize bugs, behavioral regressions, merge risk, and missing tests.
Focus first on the files changed in this commit and anything directly coupled to them:
{changed_block}
Return JSON only following the provided schema.
Use decision ALLOW_MERGE_TO_BASE only when there are no blocking findings.
"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists():
        return json.loads(output_file.read_text(encoding="utf-8"))
    command = [
        *config.codex_command,
        "exec",
        "--cd",
        str(target_repo),
        *config.codex_exec_args,
        "--output-schema",
        str(config.coordination_root / "schemas" / "review_gate.schema.json"),
        "-o",
        str(output_file),
        prompt,
    ]
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=config.review_timeout_seconds,
    )
    return json.loads(output_file.read_text(encoding="utf-8"))


def sanitize_branch_name(branch: str) -> str:
    return branch.replace("/", "__")


def runtime_dir(config) -> Path:
    return config.coordination_root / "runtime"


def request_state_path(config, branch: str) -> Path:
    path = runtime_dir(config) / "review_requests"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{sanitize_branch_name(branch)}.json"


def lock_path(config, branch: str) -> Path:
    path = runtime_dir(config) / "review_locks"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{sanitize_branch_name(branch)}.lock"


def write_review_request_state(config, branch: str, commit_sha: str, source_thread: str) -> None:
    request_state_path(config, branch).write_text(
        json.dumps(
            {
                "branch": branch,
                "commit_sha": commit_sha,
                "source_thread": source_thread,
                "requested_at": now_stamp(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def read_review_request_state(config, branch: str) -> dict:
    path = request_state_path(config, branch)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def rewrite_request_path(config, branch: str, commit_sha: str) -> Path:
    return config.coordination_root / "rewrite_requests" / f"{sanitize_branch_name(branch)}__{commit_sha}.md"


def rewrite_attempt_count(config, branch: str) -> int:
    pattern = f"{sanitize_branch_name(branch)}__*.md"
    return len(list((config.coordination_root / "rewrite_requests").glob(pattern)))


def append_records(
    config,
    branch: str,
    commit_sha: str,
    source_thread: str,
    result: dict,
) -> str:
    threads = thread_map(config.coordination_root)
    source_name = threads.get(source_thread, {}).get("name", source_thread)
    handoff_id = f"H-T3-{source_thread.upper()}-AUTO-{now_compact()}"
    decision = result["decision"]
    findings = result.get("findings", [])
    summary = result.get("summary", "").strip()
    handoffs = config.coordination_root / "HANDOFFS.md"
    comm_log = config.coordination_root / "COMM_LOG.md"
    report_path = f"reviews/{branch.replace('/', '__')}__{commit_sha}.json"

    with handoffs.open("a", encoding="utf-8") as handle:
        handle.write(
            f"""

## Handoff: `{handoff_id}`
- From: `thread3`
- To: `{source_thread}`
- Date: `{now_date()}`
- Related Task IDs: `-`
- Summary: Automated 03-Review result for commit `{commit_sha}` on branch `{branch}` from `{source_name}`.
- Files/Artifacts:
  - Review report: `{report_path}`
  - Gate decision: `{decision}`
- Verification done:
  - Codex non-interactive review executed via `codex exec --output-schema`.
- Risks/Open questions:
  - {summary if summary else "No additional summary provided."}
- Requested action:
  - {"Proceed to merge-back." if decision == "ALLOW_MERGE_TO_BASE" else "Address findings and resubmit for review."}
"""
        )
        if findings:
            handle.write("  - Findings:\n")
            for finding in findings:
                handle.write(f"    - [{finding['severity']}] {finding['file']}: {finding['note']}\n")

    with comm_log.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n[{now_stamp()}] [thread3] [type: handoff] "
            f"Automated 03-Review completed for `{branch}` commit `{commit_sha}` from `{source_thread}` with decision `{decision}` via `{handoff_id}`.\n"
        )
    return handoff_id


def write_rewrite_request(
    config,
    branch: str,
    commit_sha: str,
    source_thread: str,
    result: dict,
    handoff_id: str,
) -> tuple[Path, int]:
    path = rewrite_request_path(config, branch, commit_sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path, rewrite_attempt_count(config, branch)

    attempt = rewrite_attempt_count(config, branch) + 1
    findings = result.get("findings", [])
    summary = result.get("summary", "").strip() or "No additional summary provided."
    lines = [
        f"# Rewrite Request: {source_thread}",
        "",
        f"- Thread: `{source_thread}`",
        f"- Branch: `{branch}`",
        f"- Blocked commit: `{commit_sha}`",
        f"- Review handoff: `{handoff_id}`",
        f"- Attempt: `{attempt}`",
        f"- Summary: {summary}",
        "",
        "## Findings",
        "",
    ]
    if findings:
        for finding in findings:
            lines.append(f"- [{finding['severity']}] `{finding['file']}`: {finding['note']}")
    else:
        lines.append("- No structured findings were returned; inspect the review summary and report.")
    lines.extend(
        [
            "",
            "## Rewrite Goal",
            "",
            "Address the blocking findings on the current thread branch, keep changes minimal, run focused validation, and create a new commit so the review hook can run again.",
            "",
            "## Report Artifact",
            "",
            f"- `reviews/{sanitize_branch_name(branch)}__{commit_sha}.json`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path, attempt


def append_rewrite_log(comm_log: Path, source_thread: str, branch: str, request_path: Path, attempt: int, message: str) -> None:
    with comm_log.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n[{now_stamp()}] [{source_thread}] [type: update] "
            f"{message} Branch `{branch}`, rewrite request `{request_path.relative_to(request_path.parents[1])}`, attempt `{attempt}`.\n"
        )


def build_rewrite_prompt(
    config,
    active_repo: Path,
    branch: str,
    commit_sha: str,
    source_thread: str,
    result: dict,
    handoff_id: str,
    request_path: Path,
    attempt: int,
) -> str:
    findings = result.get("findings", [])
    findings_text = "\n".join(
        f"- [{finding['severity']}] {finding['file']}: {finding['note']}" for finding in findings
    ) or "- No structured findings were returned; inspect the summary and the report artifact."
    summary = result.get("summary", "").strip() or "No additional summary provided."
    return f"""
You are re-entering as {source_thread} on branch {branch}.
Thread3 blocked commit {commit_sha} via handoff {handoff_id}.

Current worktree:
- repo root: {active_repo}
- branch: {branch}

Blocking summary:
{summary}

Blocking findings:
{findings_text}

Coordination artifacts:
- rewrite request: {request_path}
- review report: {config.coordination_root / 'reviews' / f'{sanitize_branch_name(branch)}__{commit_sha}.json'}
- coordination root: {config.coordination_root}

Required actions:
1. Fix the blocking findings with the smallest safe change set on the current branch.
2. Run focused validation for the touched files.
3. If you made a fix, create a new commit on the current branch describing the rewrite.
4. Do not switch branches or merge to {config.base_branch}.
5. Keep the branch reviewable; do not introduce unrelated cleanup.

This is automatic rewrite attempt {attempt} of at most {config.max_auto_rewrite_attempts}.
"""


def run_auto_rewrite(
    config,
    active_repo: Path,
    branch: str,
    commit_sha: str,
    source_thread: str,
    result: dict,
    handoff_id: str,
    request_path: Path,
    attempt: int,
) -> tuple[bool, str]:
    prompt = build_rewrite_prompt(
        config=config,
        active_repo=active_repo,
        branch=branch,
        commit_sha=commit_sha,
        source_thread=source_thread,
        result=result,
        handoff_id=handoff_id,
        request_path=request_path,
        attempt=attempt,
    )
    command = [
        *config.codex_command,
        "exec",
        "--cd",
        str(active_repo),
        *config.codex_exec_args,
        prompt,
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return False, str(exc)
    except subprocess.CalledProcessError as exc:
        output = (exc.stderr or exc.stdout or "").strip()
        return False, output[-400:] if output else "codex exec rewrite failed"
    output = (completed.stdout or completed.stderr or "").strip()
    return True, output[-400:] if output else "rewrite invocation completed"


def maybe_auto_finish(config, branch: str, handoff_id: str, decision: str) -> None:
    if decision != "ALLOW_MERGE_TO_BASE" or not config.auto_finish_on_approve:
        return
    result = subprocess.run(
        [
            "bash",
            str(config.coordination_root / "thread_branch_flow.sh"),
            "finish",
            "--branch",
            branch,
            "--review-ref",
            handoff_id,
            "--cleanup-source",
        ],
        cwd=str(config.coordination_root),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        append_failure_log(
            config.coordination_root / "COMM_LOG.md",
            branch,
            f"Auto finish failed after `{handoff_id}`: {(result.stderr or result.stdout or '').strip()[-400:] or 'thread_branch_flow finish failed'}",
        )


def maybe_auto_rewrite(
    config,
    active_repo: Path,
    branch: str,
    commit_sha: str,
    source_thread: str,
    result: dict,
    handoff_id: str,
) -> None:
    if result["decision"] != "BLOCK_MERGE_TO_BASE":
        return

    request_path, attempt = write_rewrite_request(config, branch, commit_sha, source_thread, result, handoff_id)
    append_rewrite_log(
        config.coordination_root / "COMM_LOG.md",
        source_thread,
        branch,
        request_path,
        attempt,
        "Thread3 issued an automatic rewrite request after a blocked review.",
    )

    if not config.auto_rewrite_on_block:
        return
    if attempt > config.max_auto_rewrite_attempts:
        append_failure_log(
            config.coordination_root / "COMM_LOG.md",
            branch,
            f"Auto rewrite skipped because branch reached max_auto_rewrite_attempts={config.max_auto_rewrite_attempts}",
        )
        return

    ok, detail = run_auto_rewrite(
        config=config,
        active_repo=active_repo,
        branch=branch,
        commit_sha=commit_sha,
        source_thread=source_thread,
        result=result,
        handoff_id=handoff_id,
        request_path=request_path,
        attempt=attempt,
    )
    message = "Auto rewrite invocation completed." if ok else "Auto rewrite invocation failed."
    append_rewrite_log(
        config.coordination_root / "COMM_LOG.md",
        source_thread,
        branch,
        request_path,
        attempt,
        f"{message} Detail: {detail}",
    )


def process_review_request(
    config,
    active_repo: Path,
    branch: str,
    source_thread: str,
    requested_sha: str,
) -> None:
    output_file = config.coordination_root / "reviews" / f"{branch.replace('/', '__')}__{requested_sha}.json"
    comm_log = config.coordination_root / "COMM_LOG.md"

    try:
        result = run_codex_review(active_repo, output_file, branch, requested_sha, config)
    except FileNotFoundError as exc:
        append_failure_log(comm_log, branch, str(exc))
        return
    except subprocess.TimeoutExpired:
        append_timeout_log(comm_log, branch, requested_sha, config.review_timeout_seconds)
        return
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        append_failure_log(comm_log, branch, stderr[-400:] if stderr else "codex exec failed")
        return

    handoff_id = append_records(config, branch, requested_sha, source_thread, result)

    latest_sha = branch_head_sha(active_repo, branch)
    if latest_sha != requested_sha:
        if latest_sha:
            write_review_request_state(config, branch, latest_sha, source_thread)
        return

    maybe_auto_rewrite(config, active_repo, branch, requested_sha, source_thread, result, handoff_id)
    maybe_auto_finish(config, branch, handoff_id, result["decision"])


def main() -> None:
    try:
        config = load_config()
    except SystemExit:
        return
    active_repo = current_worktree(config.target_repo)
    threads = thread_map(config.coordination_root)
    branch = current_branch(active_repo)
    if branch == config.base_branch:
        return

    source_thread = detect_thread(branch, threads)
    if not source_thread or source_thread == "thread3":
        return

    write_review_request_state(config, branch, current_commit(active_repo), source_thread)

    with lock_path(config, branch).open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return

        while True:
            request = read_review_request_state(config, branch)
            requested_sha = request.get("commit_sha") or branch_head_sha(active_repo, branch)
            requested_thread = request.get("source_thread") or source_thread
            if not requested_sha:
                return

            output_file = config.coordination_root / "reviews" / f"{branch.replace('/', '__')}__{requested_sha}.json"
            if output_file.exists():
                latest_sha = branch_head_sha(active_repo, branch)
                if latest_sha == requested_sha:
                    return
                if latest_sha:
                    write_review_request_state(config, branch, latest_sha, requested_thread)
                continue

            process_review_request(config, active_repo, branch, requested_thread, requested_sha)
            latest_sha = branch_head_sha(active_repo, branch)
            if latest_sha == requested_sha or latest_sha is None:
                return
            write_review_request_state(config, branch, latest_sha, requested_thread)


if __name__ == "__main__":
    main()
