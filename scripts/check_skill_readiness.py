#!/usr/bin/env python3
"""Check whether an Agent Skill directory is ready for open-source publishing.

Agent-agnostic and dependency-free (Python 3.8+ stdlib only). Never writes,
never contacts the network, never stages or pushes. Emits mechanical findings;
semantic quality still needs human review.

Scope of checks (see references/standard.md for the full rationale):
  A. Structure & triggering  — SKILL.md, frontmatter name/description
  B. Portability             — hardcoded home paths, backslashes, nested refs
  C. Robustness              — time-sensitive info, undeclared home assumptions
  D. Privacy / open-source   — secrets, internal-ID heuristics, LICENSE presence

Exit code is 0 when there are no ERROR-level findings, 1 otherwise. Warnings
never fail the run on their own.

Usage:
  check_skill_readiness.py <skill-dir> [--json] [--strict]

  --json    machine-readable report
  --strict  treat warnings as errors (exit 1 if any warning)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---- frontmatter -----------------------------------------------------------

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_NAME_WORDS = ("anthropic", "claude")
# "when to use" signal words the description should contain (EN + ZH)
TRIGGER_WORDS = re.compile(
    r"use when|use for|use this|when the user|when you|for tasks|"
    r"适用于|当用户|当需要|当你|当 |使用本|时使用|用于|触发|场景|需要时",
    re.I,
)

# ---- portability -----------------------------------------------------------

# Hardcoded per-user absolute paths, e.g. /Users/<name>, /home/<name>, C:\Users  # skill-release-check: ignore
HOME_ABS_RE = re.compile(r"(?:/Users/|/home/)[A-Za-z0-9._-]+|[A-Za-z]:\\\\?Users\\", re.I)
# Obvious placeholders that are NOT a real machine path (docs, templates).
HOME_PLACEHOLDER_RE = re.compile(
    r"(?:/Users/|/home/)(?:x|name|<[^>]*>|\.\.\.|user|username|you|me)\b|/Users/\.\.\.",
    re.I,
)
# A run inside a backtick code span (used to skip prose examples like `/Users/x`).
INLINE_CODE_RE = re.compile(r"`[^`]*`")
# Windows-style filesystem paths. Match genuine path shapes only, to avoid
# firing on regex-escape sequences that appear in source code:
#   - drive-rooted paths, multi-segment paths, or a segment with a file extension  # skill-release-check: ignore
BACKSLASH_PATH_RE = re.compile(
    r"[A-Za-z]:\\[A-Za-z0-9_.-]|"
    r"[A-Za-z0-9_.-]{2,}\\[A-Za-z0-9_.-]{2,}\\[A-Za-z0-9_.-]{2,}|"
    r"[A-Za-z0-9_-]{2,}\\[A-Za-z0-9_-]{2,}\.[A-Za-z0-9]{1,4}\b"
)

# ---- robustness ------------------------------------------------------------

TIME_SENSITIVE_RE = re.compile(
    r"\b(?:before|after|until|prior to)\s+(?:\w+\s+)?20\d\d\b|"
    r"20\d\d\s*年\s*\d{1,2}\s*月(?:之前|之后|前|后)",
    re.I,
)

# ---- privacy / secrets (generic heuristics, no name lists) ----------------

SECRET_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghs|ghr|github_pat)_[A-Za-z0-9_\-]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{16,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("generic-bearer", re.compile(r"\b[Bb]earer\s+[A-Za-z0-9._\-]{20,}\b")),
]

# Internal-identifier heuristics: opaque tenant/user/object IDs that should
# never ship in a public skill. These are FORMAT heuristics, not name lists.
INTERNAL_ID_PATTERNS = [
    ("lark-open-id", re.compile(r"\bou_[0-9a-f]{20,}\b")),
    ("lark-chat-id", re.compile(r"\boc_[0-9a-f]{20,}\b")),
    ("lark-app-id", re.compile(r"\bcli_[0-9a-z]{12,}\b")),
    ("lark-union-id", re.compile(r"\bon_[0-9a-f]{20,}\b")),
    ("bitable-token", re.compile(r"\b(?:bascn|basob)[0-9A-Za-z]{12,}\b")),
    ("corp-email", re.compile(r"\b[A-Za-z0-9._%+-]+@(?:bytedance|feishu|larksuite)\.com\b", re.I)),
]

# Files/dirs we never scan for secrets or count.
SKIP_PARTS = {".git", "node_modules", ".preview", "dist", "build", "__pycache__", ".venv"}
TEXT_MAX_BYTES = 2_000_000


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_frontmatter(text: str):
    """Return (frontmatter_dict_like, body) doing a minimal YAML-ish parse.

    Handles top-level scalar keys (name, description, license, version) plus
    YAML block scalars (`key: |` / `key: >`) whose value spans following
    indented lines. Not a full YAML parser — just enough to stay dependency
    free while reading the fields we check.
    """
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    block = text[3:end].strip("\n")
    body = text[end + 4 :]
    fm: dict[str, str] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in ("|", ">", "|-", ">-", "|+", ">+"):
            # block scalar: gather following more-indented lines
            collected = []
            i += 1
            while i < len(lines) and (lines[i].strip() == "" or lines[i].startswith((" ", "\t"))):
                collected.append(lines[i].strip())
                i += 1
            fm[key] = " ".join(x for x in collected if x)
            continue
        fm[key] = val.strip('"').strip("'")
        i += 1
    return fm, body


def iter_files(root: Path, tracked_only: bool = False):
    if tracked_only:
        import subprocess

        proc = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=False
        )
        if proc.returncode == 0 and proc.stdout:
            for name in proc.stdout.split("\0"):
                if not name:
                    continue
                p = root / name
                if p.is_file() and not any(part in SKIP_PARTS for part in p.parts):
                    yield p
            return
        # fall through to full walk if not a git repo
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def real_home_paths(content: str, is_markdown: bool) -> list[str]:
    """Return real hardcoded home-path hits, ignoring doc placeholders.

    Skips lines carrying `skill-release-check: ignore`, matches that are obvious
    placeholders (/Users/x, /Users/<name>, ...), and — in markdown — matches
    that only appear inside inline code spans (prose examples).
    """
    hits = []
    for line in content.splitlines():
        if "skill-release-check: ignore" in line:
            continue
        scan = INLINE_CODE_RE.sub("", line) if is_markdown else line
        for m in HOME_ABS_RE.finditer(scan):
            token = m.group(0)
            if HOME_PLACEHOLDER_RE.match(token):
                continue
            hits.append(token)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="scan only git-tracked files (what will actually be published)",
    )
    args = parser.parse_args()

    root = Path(args.skill).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, object] = {}

    # ---- A. Structure & triggering -------------------------------------
    skill_md = root / "SKILL.md"
    fm = None
    body = ""
    if not skill_md.is_file():
        errors.append("A: no SKILL.md at skill root")
    else:
        fm, body = parse_frontmatter(read_text(skill_md))
        if fm is None:
            errors.append("A: SKILL.md has no YAML frontmatter block")
            fm = {}
        name = fm.get("name", "")
        desc = fm.get("description", "")
        checks["name"] = name
        checks["description_len"] = len(desc)

        if not name:
            errors.append("A: frontmatter missing required field: name")
        else:
            if not NAME_RE.match(name):
                errors.append(f"A: name '{name}' must be lowercase letters/digits/hyphens, no leading/trailing/consecutive hyphens")
            if len(name) > 64:
                errors.append("A: name exceeds 64 characters")
            if any(w in name.lower() for w in RESERVED_NAME_WORDS):
                errors.append(f"A: name contains reserved word ({'/'.join(RESERVED_NAME_WORDS)})")
            if name != root.name:
                warnings.append(f"A: name '{name}' does not match directory '{root.name}' (agentskills spec expects match)")
        if not desc:
            errors.append("A: frontmatter missing required field: description")
        else:
            if len(desc) > 1024:
                errors.append("A: description exceeds 1024 characters")
            if not TRIGGER_WORDS.search(desc):
                warnings.append("A: description has no clear 'when to use'/trigger phrasing")
            if re.search(r"\b(?:I |you )(?:can|will|help)\b", desc):
                warnings.append("A: description should be third person (avoid 'I/you can help ...')")

        # SKILL.md length budget
        line_count = read_text(skill_md).count("\n") + 1
        checks["skill_md_lines"] = line_count
        if line_count > 500:
            warnings.append(f"B: SKILL.md is {line_count} lines (>500); consider moving detail to references/")

    # README must NOT live inside the skill folder itself. For a single-skill
    # repo, the repo root IS the skill folder, so a root README is expected and
    # fine — we only flag a README nested in a deeper skill subfolder.
    for nested in root.rglob("SKILL.md"):
        d = nested.parent
        if d != root and (d / "README.md").is_file():
            warnings.append(f"A: README.md found inside skill folder '{rel(root, d)}' (anti-pattern)")

    # ---- reference depth (one level from SKILL.md) ---------------------
    if body:
        link_re = re.compile(r"\]\(([^)\s]+\.md)\)")
        for target in link_re.findall(body):
            t = target.split("#", 1)[0]
            if t.startswith(("http://", "https://", "/")):
                continue
            depth = t.replace("\\", "/").strip("./").count("/")
            if depth >= 2:
                warnings.append(f"B: reference '{t}' is nested >1 level deep from SKILL.md")

    # ---- scan all files: portability / robustness / privacy -------------
    secret_hits: list[dict] = []
    internal_hits: list[dict] = []
    home_path_hits: list[str] = []
    backslash_hits: list[str] = []
    time_hits: list[str] = []

    scan_ext = {".md", ".py", ".sh", ".yaml", ".yml", ".json", ".js", ".ts", ".txt", ".mjs", ".cjs"}
    for path in iter_files(root, tracked_only=args.tracked_only):
        try:
            if path.stat().st_size > TEXT_MAX_BYTES:
                continue
        except OSError:
            continue
        if path.suffix.lower() not in scan_ext:
            continue
        content = read_text(path)
        rp = rel(root, path)

        for label, pat in SECRET_PATTERNS:
            if pat.search(content):
                secret_hits.append({"type": label, "file": rp})
        for label, pat in INTERNAL_ID_PATTERNS:
            if pat.search(content):
                internal_hits.append({"type": label, "file": rp})
        if real_home_paths(content, path.suffix.lower() == ".md"):
            home_path_hits.append(rp)
        # backslash paths: only meaningful in scripts, skip prose-heavy md
        if path.suffix.lower() in {".py", ".sh", ".js", ".ts", ".mjs", ".cjs"}:
            for line in content.splitlines():
                if "skill-release-check: ignore" in line:
                    continue
                if BACKSLASH_PATH_RE.search(line):
                    backslash_hits.append(rp)
                    break
        if path.suffix.lower() == ".md":
            for line in content.splitlines():
                if "skill-release-check: ignore" in line:
                    continue
                if TIME_SENSITIVE_RE.search(INLINE_CODE_RE.sub("", line)):
                    time_hits.append(rp)
                    break

    checks["secret_hits"] = secret_hits
    checks["internal_id_hits"] = internal_hits
    checks["home_path_files"] = sorted(set(home_path_hits))
    if secret_hits:
        errors.append("D: possible credential(s) found; inspect before publishing: " + ", ".join(f"{h['type']}@{h['file']}" for h in secret_hits))
    if internal_hits:
        errors.append("D: possible internal identifier(s) found (tenant/user/app IDs, corp email): " + ", ".join(f"{h['type']}@{h['file']}" for h in internal_hits))
    if home_path_hits:
        errors.append("B: hardcoded per-user home path(s) in: " + ", ".join(sorted(set(home_path_hits))) + " — use env vars or relative paths")
    if backslash_hits:
        warnings.append("B: Windows-style backslash path(s) in: " + ", ".join(sorted(set(backslash_hits))))
    if time_hits:
        warnings.append("C: time-sensitive wording (e.g. 'before 2025') in: " + ", ".join(sorted(set(time_hits))) + " — prefer an 'old patterns' section")

    # ---- D. LICENSE presence -------------------------------------------
    license_files = [p.name for p in root.iterdir() if p.is_file() and p.name.upper().startswith(("LICENSE", "LICENCE", "COPYING"))]
    checks["license_files"] = license_files
    if not license_files:
        errors.append("D: no LICENSE file at skill root — a public open-source skill needs an explicit license")

    ok = not errors
    result = {"skill": str(root), "ok": ok, "errors": errors, "warnings": warnings, "checks": checks}

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"skill:  {root}")
        print(f"status: {'PASS' if ok else 'FAIL'}")
        for k, v in checks.items():
            print(f"  {k}: {v}")
        for m in errors:
            print(f"ERROR:   {m}", file=sys.stderr)
        for m in warnings:
            print(f"WARNING: {m}", file=sys.stderr)

    if not ok:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
