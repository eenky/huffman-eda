#!/usr/bin/env python3
"""Repository change policy. GOVERNANCE file: only the owner may change it.

In CI this runs from `main` (pull_request_target), never from the PR's own code, so a PR
cannot weaken the checks that judge it. The PR head is read as data with `git show`.

Subcommands
  check  --base SHA --head SHA --author LOGIN    judge a PR (CI)
  verify                                         working tree matches docs/spec_lock.json
  lock   [--section N ...] [--file PATH ...]     append lock entries (spec PRs)

Environment for `check`: OWNER_LOGIN, REVIEWER_LOGIN (required, fail closed),
OWNER_APPROVED ("true" when the `owner-approved` label was applied by OWNER_LOGIN),
PEER_APPROVED ("true" when AUTHOR_LOGIN approved the PR's current head commit).
Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOCK = "docs/spec_lock.json"
SEMANTICS = "docs/SEMANTICS.md"

GOVERNANCE = (
    ".github/",
    "AGENTS.md",
    "REVIEWER.md",
    "scripts/spec_policy.py",
    "scripts/app_token.sh",
    "scripts/reviewer_verdict.sh",
    "scripts/setup_governance.sh",
)
REFERENCE = ("reference/", "tests/test_reference_diff.py")
SPEC = (SEMANTICS, LOCK, "tests/golden")  # every tests/golden*/ directory
NEUTRAL = ("tasks/", "docs/ROADMAP.md", "docs/ARCHITECTURE.md", "README.md")
WEAKENERS = re.compile(
    r"pytest\.skip|\bxfail\b|importorskip|#\s*type:\s*ignore|#\s*noqa|pragma:\s*no cover"
)
SOURCE_RE = re.compile(r"^(synthetic|book: .+)$")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _show(rev: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sections(text: str) -> dict[str, str]:
    """Map '8' -> full text of '## 8. ...' up to the next '## ' heading."""
    out: dict[str, str] = {}
    key: str | None = None
    buf: list[str] = []
    for line in text.splitlines(keepends=True):
        m = re.match(r"## (\d+)\. ", line)
        if line.startswith("## "):
            if key is not None:
                out[key] = "".join(buf)
            key, buf = (m.group(1) if m else None), []
        if key is not None:
            buf.append(line)
    if key is not None:
        out[key] = "".join(buf)
    return out


def lock_violations(
    lock: dict[str, dict[str, str]], read: Callable[[str], str | None]
) -> list[str]:
    """Check every lock entry against content provided by read(path) -> str | None."""
    errs = []
    sem = read(SEMANTICS) or ""
    secs = sections(sem)
    for num, digest in lock.get("sections", {}).items():
        if num not in secs:
            errs.append(f"locked SEMANTICS §{num} is missing")
        elif _sha(secs[num]) != digest:
            errs.append(f"locked SEMANTICS §{num} was changed")
    for path, digest in lock.get("files", {}).items():
        content = read(path)
        if content is None:
            errs.append(f"locked file {path} is missing")
        elif _sha(content) != digest:
            errs.append(f"locked file {path} was changed")
    return errs


def _is_golden(path: str) -> bool:
    """True for files inside any tests/golden*/ directory."""
    parts = path.split("/")
    return len(parts) >= 3 and parts[0] == "tests" and parts[1].startswith("golden")


def _kind(path: str) -> str:
    if _is_golden(path):
        return "spec"
    for name, prefixes in (
        ("governance", GOVERNANCE),
        ("reference", REFERENCE),
        ("spec", SPEC),
        ("neutral", NEUTRAL),
    ):
        if any(path == p or path.startswith(p) for p in prefixes):
            return name
    return "impl"


def check(base: str, head: str, author: str) -> list[str]:
    owner = os.environ.get("OWNER_LOGIN", "")
    reviewer = os.environ.get("REVIEWER_LOGIN", "")
    if not owner or not reviewer or owner == reviewer:
        return ["OWNER_LOGIN and REVIEWER_LOGIN must be set and distinct (failing closed)"]
    if author == owner:
        print(f"author {author} is the owner: policy bypassed")
        return []
    owner_approved = os.environ.get("OWNER_APPROVED") == "true"
    role = "reviewer" if author == reviewer else "author"
    peer_approved = os.environ.get("PEER_APPROVED") == "true"

    changes: list[tuple[str, str]] = []  # (status, path); renames count as delete + add
    for line in _git("diff", "--name-status", "--no-renames", base, head).splitlines():
        status, path = line.split("\t", 1)
        changes.append((status[0], path))
    kinds = {_kind(p) for _, p in changes}
    errs: list[str] = []

    # P1 scope by identity
    allowed = {"reviewer": {"reference", "spec", "neutral"}, "author": {"spec", "impl", "neutral"}}
    for _status, path in changes:
        if _kind(path) not in allowed[role]:
            errs.append(f"P1: {role} may not change {_kind(path)} path {path}")

    # P8 the reviewer never self-approves: its PRs need the author app's approval on this head
    if role == "reviewer" and not peer_approved:
        errs.append(
            "P8: a reviewer PR needs an APPROVED review from the author app on its current head"
            " commit (then add the peer-reviewed label to re-run this check)"
        )

    # P2 no mixing ground truth with code that is judged by it
    if "spec" in kinds and kinds & {"impl", "reference"}:
        errs.append("P2: a PR that changes spec/golden must not change src, tests or reference")

    # P3 frozen ground truth: existing golden files and lock entries
    base_lock = json.loads(_show(base, LOCK) or "{}")
    head_lock = json.loads(_show(head, LOCK) or "{}")
    frozen_edits = [
        f"{status} {path}" for status, path in changes if status in "MD" and _is_golden(path)
    ]
    for group in ("sections", "files"):
        for key, digest in base_lock.get(group, {}).items():
            if head_lock.get(group, {}).get(key) != digest:
                frozen_edits.append(f"lock entry {group}/{key}")
    if frozen_edits and not owner_approved:
        errs.extend(
            f"P3: frozen ground truth changed without owner-approved: {e}" for e in frozen_edits
        )

    # P4 every new golden case documents where its expectations come from
    new_cases = {
        "/".join(path.split("/")[:3])
        for status, path in changes
        if status == "A" and _is_golden(path) and path.count("/") >= 3
    }
    for case in sorted(new_cases):
        raw = _show(head, f"{case}/expected.json")
        if raw is None:
            errs.append(f"P4: {case} has no expected.json")
            continue
        meta = json.loads(raw)
        if not (isinstance(meta.get("derivation"), list) and meta["derivation"]):
            errs.append(f"P4: {case}/expected.json needs a non-empty 'derivation' list")
        if not (isinstance(meta.get("source"), str) and SOURCE_RE.match(meta["source"])):
            errs.append(f"P4: {case}/expected.json needs 'source': 'synthetic' or 'book: <cite>'")

    # P5 the head tree must satisfy its own lock
    errs.extend(f"P5: {e}" for e in lock_violations(head_lock, lambda p: _show(head, p)))

    # P6 the reference and production never import each other
    for path in _git("ls-tree", "-r", "--name-only", head).splitlines():
        if not path.endswith(".py"):
            continue
        text = _show(head, path) or ""
        if path.startswith("src/") and re.search(r"^\s*(from|import)\s+reference\b", text, re.M):
            errs.append(f"P6: {path} imports the reference")
        if path.startswith("reference/") and re.search(
            r"^\s*(from|import)\s+huffman_eda\b", text, re.M
        ):
            errs.append(f"P6: {path} imports huffman_eda")

    # P7 no test-weakening markers in added lines
    diff = _git(
        "diff", "--unified=0", "--no-renames", base, head, "--", "src", "tests", "reference"
    )
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:]
        elif line.startswith("+") and WEAKENERS.search(line) and not _is_golden(current):
            # golden harnesses are locked spec files that skip until their module exists
            errs.append(f"P7: weakening marker added in {current}: {line[1:].strip()}")

    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--base", required=True)
    c.add_argument("--head", required=True)
    c.add_argument("--author", required=True)
    sub.add_parser("verify")
    lk = sub.add_parser("lock")
    lk.add_argument("--section", action="append", default=[])
    lk.add_argument("--file", action="append", default=[])
    a = ap.parse_args()

    if a.cmd == "check":
        errs = check(a.base, a.head, a.author)
    elif a.cmd == "verify":
        lock = json.loads(Path(LOCK).read_text())
        errs = lock_violations(lock, lambda p: Path(p).read_text() if Path(p).exists() else None)
    else:
        lock = json.loads(Path(LOCK).read_text()) if Path(LOCK).exists() else {}
        lock.setdefault("sections", {})
        lock.setdefault("files", {})
        secs = sections(Path(SEMANTICS).read_text())
        for num in a.section:
            if num in lock["sections"]:
                sys.exit(f"§{num} is already locked; changing it needs owner-approved")
            lock["sections"][num] = _sha(secs[num])
        for path in a.file:
            if path in lock["files"]:
                sys.exit(f"{path} is already locked; changing it needs owner-approved")
            lock["files"][path] = _sha(Path(path).read_text())
        Path(LOCK).write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        errs = []

    for e in errs:
        print(f"::error::{e}" if os.environ.get("GITHUB_ACTIONS") else e)
    if not errs and a.cmd != "lock":
        print("spec policy: OK")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
