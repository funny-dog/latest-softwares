"""Auto-merge verified non-major Dependabot PRs after Sync Latest Software passes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

import yaml

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ALLOWED_AUTHORS = frozenset({"dependabot[bot]", "app/dependabot"})
ALLOWED_UPDATE_TYPES = frozenset(
    {
        "version-update:semver-minor",
        "version-update:semver-patch",
    }
)
BLOCKING_CONCLUSIONS = frozenset(
    {
        "FAILURE",
        "TIMED_OUT",
        "CANCELLED",
        "ACTION_REQUIRED",
        "STARTUP_FAILURE",
        "STALE",
    }
)


def parse_dependabot_updates(commit_messages: list[str]) -> list[dict[str, str]]:
    """Extract updated-dependencies metadata entries from Dependabot commit messages."""
    updates: list[dict[str, str]] = []
    for message in commit_messages:
        marker = "\nupdated-dependencies:"
        idx = message.find(marker)
        if idx == -1 and not message.startswith("updated-dependencies:"):
            continue
        start = 0 if message.startswith("updated-dependencies:") else idx + 1
        snippet = message[start:]
        end = snippet.find("\n...")
        if end != -1:
            snippet = snippet[:end]
        try:
            parsed = yaml.safe_load(snippet)
        except yaml.YAMLError:
            continue
        if not isinstance(parsed, dict):
            continue
        entries = parsed.get("updated-dependencies")
        if not isinstance(entries, list):
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            name = item.get("dependency-name")
            update_type = item.get("update-type")
            if isinstance(name, str) and isinstance(update_type, str):
                updates.append(
                    {
                        "dependency-name": name,
                        "update-type": update_type,
                    }
                )
    return updates


def evaluate_pr_for_auto_merge(
    pr: dict[str, Any],
    updates: list[dict[str, str]],
) -> tuple[bool, str]:
    """Return (should_merge, reason) for a PR candidate."""
    author = (pr.get("author") or {}).get("login", "")
    if author not in ALLOWED_AUTHORS:
        return False, f"跳过：PR 作者 '{author}' 不是 Dependabot"

    if pr.get("state") != "OPEN":
        return False, f"跳过：PR 状态为 {pr.get('state')}"

    if pr.get("isDraft"):
        return False, "跳过：PR 处于 Draft 状态"

    if pr.get("baseRefName") != "main":
        return False, f"跳过：目标分支为 {pr.get('baseRefName')}，非 main"

    if pr.get("mergeable") == "CONFLICTING":
        return False, "跳过：PR 存在合并冲突"

    if not updates:
        return False, "跳过：未解析到 Dependabot updated-dependencies 元数据"

    disallowed = [
        f"{u['dependency-name']} ({u['update-type']})"
        for u in updates
        if u.get("update-type") not in ALLOWED_UPDATE_TYPES
    ]
    if disallowed:
        return False, f"跳过：包含非 minor/patch 更新：{', '.join(disallowed)}"

    checks = pr.get("statusCheckRollup") or []
    pr_checks_passed = False
    for check in checks:
        name = check.get("name") or check.get("context") or "unknown"
        status = check.get("status")
        conclusion = check.get("conclusion")
        if status and status != "COMPLETED":
            return False, f"跳过：检查 '{name}' 尚未完成（{status}）"
        if conclusion in BLOCKING_CONCLUSIONS:
            return False, f"跳过：检查 '{name}' 未通过（{conclusion}）"
        if name == "pr-checks" and conclusion == "SUCCESS":
            pr_checks_passed = True

    if not pr_checks_passed:
        return False, "跳过：未找到已通过的 pr-checks 检查结果"

    summary = ", ".join(f"{u['dependency-name']} ({u['update-type']})" for u in updates)
    return True, f"符合自动合并条件：{summary}"


def _run_gh(args: list[str]) -> str:
    proc = subprocess.run(
        ["gh", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def find_open_pr_by_sha(repo: str, head_sha: str) -> dict[str, Any] | None:
    """Find an open PR targeting main whose HEAD matches head_sha."""
    raw = _run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--base",
            "main",
            "--json",
            "number,title,state,isDraft,baseRefName,headRefOid,mergeable,author,statusCheckRollup",
            "--limit",
            "30",
        ]
    )
    prs = json.loads(raw)
    for pr in prs:
        if pr.get("headRefOid") == head_sha:
            return pr
    return None


def fetch_pr_commit_messages(repo: str, number: int) -> list[str]:
    raw = _run_gh(["api", f"repos/{repo}/pulls/{number}/commits"])
    commits = json.loads(raw)
    return [
        commit["commit"]["message"]
        for commit in commits
        if isinstance(commit, dict)
        and isinstance((commit.get("commit") or {}).get("message"), str)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="GitHub repository in owner/name format",
    )
    parser.add_argument(
        "--head-sha",
        default=os.environ.get("HEAD_SHA", ""),
        help="Commit SHA from workflow_run.head_sha",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.repo or not args.head_sha:
        print("缺少 --repo 或 --head-sha 参数", file=sys.stderr)
        return 1

    pr = find_open_pr_by_sha(args.repo, args.head_sha)
    if pr is None:
        print(f"未找到 head SHA 为 {args.head_sha} 的 open PR，跳过。")
        return 0

    number = int(pr["number"])
    messages = fetch_pr_commit_messages(args.repo, number)
    updates = parse_dependabot_updates(messages)
    should_merge, reason = evaluate_pr_for_auto_merge(pr, updates)
    print(f"PR #{number} ({pr.get('title', '')}): {reason}")

    if not should_merge:
        return 0

    if args.dry_run:
        print(f"[dry-run] 将执行 gh pr merge {number} --squash --delete-branch")
        return 0

    _run_gh(
        [
            "pr",
            "merge",
            str(number),
            "--repo",
            args.repo,
            "--squash",
            "--delete-branch",
        ]
    )
    print(f"已自动 squash 合并 PR #{number}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
