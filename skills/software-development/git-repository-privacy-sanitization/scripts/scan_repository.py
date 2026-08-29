from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

REPORT_VERSION = 1
RUN_REDACTION_KEY = os.urandom(32)

EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
IPV4_RE = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
IPV6_RE = re.compile(r"(?<![A-Fa-f0-9:])(?:[A-Fa-f0-9]{0,4}:){2,7}[A-Fa-f0-9]{0,4}(?![A-Fa-f0-9:])")
URL_RE = re.compile(r"(?i)\b(?:https?|ssh|git)://[^\s<>()`]+|\bgit@[A-Z0-9._-]+:[^\s<>()`]+")
WIN_HOME_RE = re.compile(r"(?i)(?:[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s]+)")
_POSIX_HOME_PREFIXES = tuple("/" + segment + "/" for segment in ("home", "Users"))
POSIX_HOME_RE = re.compile(r"(?:" + "|".join(re.escape(prefix) for prefix in _POSIX_HOME_PREFIXES) + r")[^/\s]+")
UNC_RE = re.compile(r"\\\\[A-Za-z0-9._-]+[\\/][^\s]+")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
SECRET_SHAPE_RE = re.compile(
    r"(?i)(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,})"
)
LITERAL_SENSITIVE_RE = re.compile(
    r"(?i)\b(username|user|hostname|host|password|token|secret|api[_-]?key)\b"
    r"[\"'` ]*[:=]\s*[\"']([^\"'\n]+)[\"']"
)


@dataclass(frozen=True)
class Identifier:
    label: str
    value: str


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(message or f"git {' '.join(args)} failed")
    return proc.stdout


def load_identifiers_from_stdin(enabled: bool) -> list[Identifier]:
    if not enabled:
        return []
    payload = json.load(sys.stdin)
    raw = payload.get("identifiers", [])
    if not isinstance(raw, list):
        raise ValueError("identifiers must be a list")
    identifiers: list[Identifier] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each identifier must be an object")
        value = str(item.get("value") or "")
        if not value.strip():
            raise ValueError("identifier has an empty value")
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        # Caller-controlled labels are deliberately ignored. A label can itself
        # contain the private value, so reports use generated ordinals only.
        identifiers.append(Identifier(f"identifier_{len(identifiers) + 1}", value))
    return identifiers


def fingerprint(value: str) -> str:
    return hmac.new(
        RUN_REDACTION_KEY,
        value.casefold().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12]


def finding_id(
    surface: str,
    location: str,
    line: int | None,
    category: str,
    source: str,
    detail: str,
) -> str:
    material = "\x00".join((surface, location, str(line or 0), category, source, detail))
    return "F-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def redact_location(location: str, identifiers: list[Identifier]) -> str:
    redacted = location
    for identifier in sorted(identifiers, key=lambda item: len(item.value), reverse=True):
        redacted = re.sub(
            re.escape(identifier.value),
            f"<redacted:{identifier.label}>",
            redacted,
            flags=re.IGNORECASE,
        )
    for regex, replacement in (
        (EMAIL_RE, "<email>"),
        (WIN_HOME_RE, "<user-path>"),
        (POSIX_HOME_RE, "<user-path>"),
        (UNC_RE, "<network-path>"),
        (SECRET_SHAPE_RE, "<secret>"),
        (IPV4_RE, "<ip-address>"),
        (IPV6_RE, "<ip-address>"),
        (URL_RE, "<url>"),
    ):
        redacted = regex.sub(replacement, redacted)
    if len(redacted) > 240:
        suffix = hashlib.sha256(redacted.encode("utf-8")).hexdigest()[:12]
        redacted = redacted[:200] + f"<truncated:{suffix}>"
    return redacted


def add_finding(
    findings: list[dict],
    *,
    surface: str,
    location: str,
    line: int | None,
    category: str,
    source: str,
    evidence_fingerprint: str,
    detail: str,
) -> None:
    findings.append(
        {
            "id": finding_id(surface, location, line, category, source, detail),
            "surface": surface,
            "location": location,
            "line": line,
            "category": category,
            "source": source,
            "evidence_fingerprint": evidence_fingerprint,
            "detail": detail,
        }
    )


def scan_text(text: str, *, surface: str, location: str, identifiers: list[Identifier], findings: list[dict]) -> None:
    report_location = redact_location(location, identifiers)
    folded = text.casefold()
    for identifier in identifiers:
        needle = identifier.value.casefold()
        start = 0
        while True:
            start = folded.find(needle, start)
            if start < 0:
                break
            add_finding(
                findings,
                surface=surface,
                location=report_location,
                line=line_number(text, start),
                category="known_identifier",
                source=identifier.label,
                evidence_fingerprint=fingerprint(identifier.value),
                detail="exact user-context identifier",
            )
            start += max(1, len(needle))

    structural: tuple[tuple[re.Pattern[str], str, str], ...] = (
        (EMAIL_RE, "email", "email-shaped value"),
        (WIN_HOME_RE, "absolute_user_path", "Windows user-home path"),
        (POSIX_HOME_RE, "absolute_user_path", "POSIX user-home path"),
        (UNC_RE, "network_path", "UNC path"),
        (PRIVATE_KEY_RE, "secret_material", "private-key header"),
        (SECRET_SHAPE_RE, "secret_material", "credential-shaped value"),
    )
    for regex, category, detail in structural:
        for match in regex.finditer(text):
            raw = match.group(0)
            add_finding(
                findings,
                surface=surface,
                location=report_location,
                line=line_number(text, match.start()),
                category=category,
                source="structural_pattern",
                evidence_fingerprint=fingerprint(raw),
                detail=detail,
            )

    for regex, version in ((IPV4_RE, 4), (IPV6_RE, 6)):
        for match in regex.finditer(text):
            raw = match.group(0)
            try:
                parsed = ipaddress.ip_address(raw)
            except ValueError:
                continue
            if parsed.version != version:
                continue
            add_finding(
                findings,
                surface=surface,
                location=report_location,
                line=line_number(text, match.start()),
                category="ip_address",
                source="structural_pattern",
                evidence_fingerprint=fingerprint(raw),
                detail=f"IPv{version} address",
            )

    for match in URL_RE.finditer(text):
        raw = match.group(0).rstrip(".,;:'\"")
        if raw.startswith("git@"):
            host = raw.split("@", 1)[1].split(":", 1)[0]
        else:
            host = urlparse(raw).hostname or ""
        add_finding(
            findings,
            surface=surface,
            location=report_location,
            line=line_number(text, match.start()),
            category="external_reference",
            source="structural_pattern",
            evidence_fingerprint=fingerprint(raw),
            detail="URL or Git remote; classify as public, private, or placeholder",
        )

    for match in LITERAL_SENSITIVE_RE.finditer(text):
        raw = match.group(2).strip()
        if raw.startswith("<") or raw.startswith("${") or raw.startswith("{"):
            continue
        add_finding(
            findings,
            surface=surface,
            location=report_location,
            line=line_number(text, match.start()),
            category="literal_sensitive_assignment",
            source="structural_pattern",
            evidence_fingerprint=fingerprint(raw),
            detail=f"literal assigned to {match.group(1).casefold()} field",
        )


def decode_for_scan(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    sample = data[:512]
    if len(sample) >= 8:
        even_nuls = sample[0::2].count(0)
        odd_nuls = sample[1::2].count(0)
        pairs = len(sample) // 2
        if max(even_nuls, odd_nuls) >= max(4, pairs * 3 // 4) and min(even_nuls, odd_nuls) <= pairs // 8:
            return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def scan_bytes(
    data: bytes,
    *,
    surface: str,
    location: str,
    identifiers: list[Identifier],
    findings: list[dict],
) -> None:
    scan_text(decode_for_scan(data), surface=surface, location=location, identifiers=identifiers, findings=findings)


def worktree_files(repo: Path) -> list[Path]:
    return sorted(
        path
        for path in repo.rglob("*")
        if (path.is_file() or path.is_symlink()) and ".git" not in path.relative_to(repo).parts
    )


def reachable_commits(repo: Path) -> list[str]:
    output = git(repo, "rev-list", "--all").decode("ascii", errors="replace")
    return [line for line in output.splitlines() if line]


def reachable_object_ids(repo: Path, ref_object_ids: set[str]) -> set[str]:
    output = git(repo, "rev-list", "--objects", "--all")
    result = {line.split(b" ", 1)[0].decode("ascii") for line in output.splitlines() if line}
    result.update(ref_object_ids)
    return result


def tree_entries(repo: Path, commit: str) -> list[tuple[str, str]]:
    output = git(repo, "ls-tree", "-r", "-z", commit)
    entries: list[tuple[str, str]] = []
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        _mode, object_type, object_id = metadata.decode("ascii").split(" ", 2)
        if object_type == "blob":
            entries.append((object_id, raw_path.decode("utf-8", errors="surrogateescape")))
    return entries


def scan_repository(repo: Path, identifiers: list[Identifier], include_local_git: bool, max_bytes: int) -> dict:
    findings: list[dict] = []
    skipped: list[dict] = []

    files = worktree_files(repo)
    for path in files:
        relative = path.relative_to(repo).as_posix()
        scan_text(relative, surface="worktree_path", location=relative, identifiers=identifiers, findings=findings)
        if path.is_symlink():
            scan_text(
                os.readlink(path),
                surface="worktree_symlink_target",
                location=relative,
                identifiers=identifiers,
                findings=findings,
            )
            continue
        size = path.stat().st_size
        if size > max_bytes:
            skipped.append(
                {
                    "surface": "worktree",
                    "location": redact_location(relative, identifiers),
                    "reason": "byte_limit",
                    "size": size,
                }
            )
            continue
        scan_bytes(path.read_bytes(), surface="worktree", location=relative, identifiers=identifiers, findings=findings)

    commits = reachable_commits(repo)
    refs_output = git(repo, "for-each-ref", "--format=%(refname)%09%(objectname)%09%(objecttype)")
    ref_object_ids: set[str] = set()
    for row in refs_output.decode("utf-8", errors="replace").splitlines():
        ref_name, object_id, object_type = row.split("\t", 2)
        ref_object_ids.add(object_id)
        scan_text(
            ref_name,
            surface="reachable_ref_name",
            location=ref_name,
            identifiers=identifiers,
            findings=findings,
        )
        if object_type == "tag":
            scan_bytes(
                git(repo, "cat-file", "tag", object_id),
                surface="reachable_tag_metadata",
                location=ref_name,
                identifiers=identifiers,
                findings=findings,
            )
    seen_blobs: set[str] = set()
    for commit in commits:
        metadata = git(repo, "show", "-s", "--format=%an%n%ae%n%cn%n%ce%n%B", commit)
        scan_bytes(
            metadata,
            surface="reachable_commit_metadata",
            location=commit[:12],
            identifiers=identifiers,
            findings=findings,
        )
        for object_id, relative in tree_entries(repo, commit):
            scan_text(
                relative,
                surface="reachable_tree_path",
                location=f"{commit[:12]}:{relative}",
                identifiers=identifiers,
                findings=findings,
            )
            if object_id in seen_blobs:
                continue
            seen_blobs.add(object_id)
            size = int(git(repo, "cat-file", "-s", object_id).decode("ascii").strip())
            if size > max_bytes:
                skipped.append(
                    {
                        "surface": "reachable_blob",
                        "location": redact_location(f"{commit[:12]}:{relative}", identifiers),
                        "reason": "byte_limit",
                        "size": size,
                    }
                )
                continue
            scan_bytes(
                git(repo, "cat-file", "blob", object_id),
                surface="reachable_blob",
                location=f"{commit[:12]}:{relative}",
                identifiers=identifiers,
                findings=findings,
            )

    local_object_count = 0
    unreachable_object_count = 0
    if include_local_git:
        local_config = git(repo, "config", "--local", "--list", "--show-origin")
        scan_bytes(
            local_config,
            surface="local_git_config",
            location="<local-git-config>",
            identifiers=identifiers,
            findings=findings,
        )
        reachable_ids = reachable_object_ids(repo, ref_object_ids)
        rows = git(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype) %(objectsize)")
        for row in rows.decode("ascii", errors="replace").splitlines():
            object_id, object_type, object_size_text = row.split(" ", 2)
            local_object_count += 1
            if object_id in reachable_ids:
                continue
            unreachable_object_count += 1
            size = int(object_size_text)
            if object_type == "blob" and size > max_bytes:
                skipped.append(
                    {
                        "surface": "unreachable_git_blob",
                        "location": object_id[:12],
                        "reason": "byte_limit",
                        "size": size,
                    }
                )
                continue
            if object_type in {"blob", "commit", "tag"}:
                scan_bytes(
                    git(repo, "cat-file", object_type, object_id),
                    surface=f"unreachable_git_{object_type}",
                    location=object_id[:12],
                    identifiers=identifiers,
                    findings=findings,
                )
            elif object_type == "tree":
                scan_bytes(
                    git(repo, "ls-tree", "-rz", object_id),
                    surface="unreachable_git_tree",
                    location=object_id[:12],
                    identifiers=identifiers,
                    findings=findings,
                )

    deduplicated = {item["id"]: item for item in findings}
    ordered = sorted(
        deduplicated.values(),
        key=lambda item: (item["surface"], item["location"], item["line"] or 0, item["category"], item["id"]),
    )
    category_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    for item in ordered:
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1
        surface_counts[item["surface"]] = surface_counts.get(item["surface"], 0) + 1

    return {
        "report_version": REPORT_VERSION,
        "repository": "<redacted-repository>",
        "scope": {
            "worktree_files": len(files),
            "reachable_commits": len(commits),
            "reachable_unique_blobs": len(seen_blobs),
            "all_local_objects": local_object_count if include_local_git else None,
            "unreachable_local_objects": unreachable_object_count if include_local_git else None,
            "identifier_labels": len(identifiers),
            "max_file_bytes": max_bytes,
            "include_local_git": include_local_git,
        },
        "category_counts": dict(sorted(category_counts.items())),
        "surface_counts": dict(sorted(surface_counts.items())),
        "findings": ordered,
        "skipped": skipped,
        "rules": {
            "values_redacted": True,
            "mutation_performed": False,
            "approval_required_before_remediation": True,
        },
    }


def ensure_output_outside_repo(repo: Path, output: Path) -> None:
    resolved = output.resolve()
    try:
        resolved.relative_to(repo)
    except ValueError:
        return
    raise ValueError("output report must be outside the repository")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Git repository privacy scanner")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--identifiers-stdin", action="store_true")
    parser.add_argument("--include-local-git", action="store_true")
    parser.add_argument("--max-file-bytes", type=int, default=20 * 1024 * 1024)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    if not (repo / ".git").exists():
        raise SystemExit("repository must be a Git working tree with a .git entry")
    if args.max_file_bytes < 1:
        raise SystemExit("--max-file-bytes must be positive")
    try:
        ensure_output_outside_repo(repo, output)
        identifiers = load_identifiers_from_stdin(args.identifiers_stdin)
        report = scan_repository(repo, identifiers, args.include_local_git, args.max_file_bytes)
    except (GitError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"scan_error={type(exc).__name__}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "report_written": True,
                "findings": len(report["findings"]),
                "skipped": len(report["skipped"]),
                "mutation_performed": False,
                "approval_required_before_remediation": True,
            }
        )
    )
    return 1 if report["findings"] or report["skipped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
