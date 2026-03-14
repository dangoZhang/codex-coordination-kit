#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from common import load_config, now_compact, now_date, now_stamp, thread_map


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


def append_failure_log(comm_log: Path, branch: str, message: str) -> None:
    with comm_log.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n[{now_stamp()}] [thread3] [type: blocker] "
            f"Automated review failed for `{branch}`: {message}\n"
        )


def run_codex_review(
    target_repo: Path,
    output_file: Path,
    branch: str,
    commit_sha: str,
    config,
) -> dict:
    prompt = f"""
You are acting as thread3 / 03-Review for this repository.
Review commit {commit_sha} on branch {branch}.
Prioritize bugs, behavioral regressions, merge risk, and missing tests.
Return JSON only following the provided schema.
Use decision ALLOW_MERGE_TO_BASE only when there are no blocking findings.
"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
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
    subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(output_file.read_text(encoding="utf-8"))


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


def maybe_auto_finish(config, branch: str, handoff_id: str, decision: str) -> None:
    if decision != "ALLOW_MERGE_TO_BASE" or not config.auto_finish_on_approve:
        return
    subprocess.run(
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
    )


def main() -> None:
    try:
        config = load_config()
    except SystemExit:
        return
    threads = thread_map(config.coordination_root)
    branch = current_branch(config.target_repo)
    if branch == config.base_branch:
        return

    source_thread = detect_thread(branch, threads)
    if not source_thread or source_thread == "thread3":
        return

    commit_sha = current_commit(config.target_repo)
    output_file = config.coordination_root / "reviews" / f"{branch.replace('/', '__')}__{commit_sha}.json"
    comm_log = config.coordination_root / "COMM_LOG.md"

    try:
        result = run_codex_review(config.target_repo, output_file, branch, commit_sha, config)
    except FileNotFoundError as exc:
        append_failure_log(comm_log, branch, str(exc))
        return
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        append_failure_log(comm_log, branch, stderr[-400:] if stderr else "codex exec failed")
        return

    handoff_id = append_records(config, branch, commit_sha, source_thread, result)
    maybe_auto_finish(config, branch, handoff_id, result["decision"])


if __name__ == "__main__":
    main()
