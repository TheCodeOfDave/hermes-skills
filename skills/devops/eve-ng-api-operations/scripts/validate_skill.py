#!/usr/bin/env python
"""Deterministically validate the reusable EVE-NG API skill."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import os
from pathlib import Path
import re
import subprocess
import sys



class ValidationFailure(RuntimeError):
    def __init__(self, check: str):
        super().__init__(check)
        self.check = check


def require(condition: bool, check: str) -> None:
    if not condition:
        raise ValidationFailure(check)


def read_skill(skill_dir: Path) -> tuple[Path, bytes, str]:
    path = skill_dir / "SKILL.md"
    require(path.is_file(), "skill_file_exists")
    raw = path.read_bytes()
    require(
        raw.startswith((b"---\n", b"---\r\n")),
        "frontmatter_starts_at_byte_zero",
    )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationFailure("skill_utf8") from exc
    return path, raw, text


def validate_frontmatter(text: str) -> None:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    require(match is not None, "frontmatter_shape")
    frontmatter = match.group(1)
    fields = {}
    for line in frontmatter.splitlines():
        if line and not line.startswith((" ", "\t")) and ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    require(fields.get("name") == "eve-ng-api-operations", "frontmatter_name")
    require(fields.get("version") == "1.0.1", "frontmatter_version")
    description = fields.get("description", "")
    require(bool(description) and len(description) <= 1024, "frontmatter_description")


def bash_blocks(raw: bytes) -> list[bytes]:
    return re.findall(rb"```bash\r?\n(.*?)\r?\n```", raw, re.DOTALL)


def validate_bash(raw: bytes) -> int:
    blocks = bash_blocks(raw)
    require(bool(blocks), "bash_fences_present")
    for block in blocks:
        try:
            result = subprocess.run(["bash", "-n"], input=block, capture_output=True)
        except OSError as exc:
            raise ValidationFailure("bash_available") from exc
        require(result.returncode == 0, "bash_fence_raw_bytes")
    return len(blocks)


def endpoint_entries(endpoint_text: str) -> list[tuple[str, str]]:
    return re.findall(
        r"^\| `([A-Z]+)` \| `([^`]+)` \|", endpoint_text, re.MULTILINE
    )


def validate_endpoints(skill_dir: Path, skill_text: str) -> int:
    reference = skill_dir / "references" / "api-endpoints.md"
    require("references/api-endpoints.md" in skill_text, "endpoint_reference_linked")
    require(reference.is_file(), "endpoint_reference_exists")
    text = reference.read_text(encoding="utf-8")
    entries = endpoint_entries(text)
    normalized = [(method, route.rstrip("/") or "/") for method, route in entries]
    duplicates = [entry for entry, count in Counter(normalized).items() if count > 1]
    require(not duplicates, "endpoint_method_route_unique")
    require(len(entries) == 42, "endpoint_entry_count")
    return len(entries)


def validate_python(skill_dir: Path) -> int:
    files = sorted(skill_dir.rglob("*.py"))
    require(bool(files), "python_files_present")
    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        except (SyntaxError, UnicodeDecodeError) as exc:
            raise ValidationFailure("python_ast") from exc
    return len(files)


def validate_generated_artifacts(skill_dir: Path) -> None:
    forbidden_names = {"__pycache__", ".pytest_cache", ".mypy_cache"}
    for path in skill_dir.rglob("*"):
        require(path.name not in forbidden_names, "generated_cache_absent")
        require(path.suffix.lower() not in {".pyc", ".pyo"}, "generated_bytecode_absent")


def validate_neutrality(skill_dir: Path) -> None:
    patterns = {
        "private_ipv4_absent": rb"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])",
        "email_absent": rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "windows_home_path_absent": rb"(?i)[A-Z]:[\\/]Users[\\/][^<\\/\s]+",
        "posix_home_path_absent": rb"/(?:home|Users)/[^<\/\s]+",
        "credential_literal_absent": rb"(?i)(?<![A-Za-z0-9_])(?:password|token|secret)\s*[:=]\s*['\"][^<\n'\"]{8,}",
    }
    for path in skill_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".py"}:
            continue
        data = path.read_bytes()
        for check, pattern in patterns.items():
            require(re.search(pattern, data) is None, check)


def extract_python_selector(skill_text: str) -> bytes:
    blocks = re.findall(r"```bash\r?\n(.*?)\r?\n```", skill_text, re.DOTALL)
    matches = [block for block in blocks if "select_python()" in block]
    require(len(matches) == 1, "interpreter_selector_block")
    return matches[0].encode("utf-8")


def run_selector(
    selector: bytes, command_stubs: bytes, explicit: str | None = None
):
    assignment = (
        b"unset PYTHON\n"
        if explicit is None
        else f"PYTHON={explicit!r}\n".encode("utf-8")
    )
    script = command_stubs + assignment + selector + b"\nprintf '%s' \"$PYTHON\"\n"
    try:
        return subprocess.run(["bash"], input=script, env=os.environ.copy(), capture_output=True)
    except OSError as exc:
        raise ValidationFailure("bash_available") from exc


def validate_interpreter_fallback(skill_text: str) -> None:
    selector = extract_python_selector(skill_text)
    fallback = run_selector(
        selector,
        b"python3() { return 49; }\npython() { return 0; }\n",
    )
    require(fallback.returncode == 0, "interpreter_fallback_executes")
    require(fallback.stdout.decode("utf-8") == "python", "interpreter_fallback_selects_python")

    explicit = run_selector(
        selector,
        b"custom_python() { return 0; }\npython3() { return 49; }\npython() { return 49; }\n",
        "custom_python",
    )
    require(explicit.returncode == 0, "interpreter_explicit_executes")
    require(
        explicit.stdout.decode("utf-8") == "custom_python",
        "interpreter_explicit_preserved",
    )

    invalid_explicit = run_selector(
        selector,
        b"custom_python() { return 49; }\npython3() { return 0; }\npython() { return 0; }\n",
        "custom_python",
    )
    require(
        invalid_explicit.returncode != 0,
        "interpreter_invalid_explicit_fails_without_fallback",
    )

    unavailable = run_selector(
        selector,
        b"python3() { return 49; }\npython() { return 49; }\n",
    )
    require(unavailable.returncode != 0, "interpreter_unavailable_fails")


def run_unit_tests(skill_dir: Path) -> None:
    test_dir = skill_dir / "tests"
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(test_dir),
                "-p",
                "test_eve_api_*.py",
            ],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationFailure("unit_test_timeout") from exc
    require(result.returncode == 0, "unit_tests")


def validate(skill_dir: Path) -> dict[str, int | str]:
    _, raw, text = read_skill(skill_dir)
    validate_frontmatter(text)
    endpoint_count = validate_endpoints(skill_dir, text)
    bash_count = validate_bash(raw)
    python_count = validate_python(skill_dir)
    validate_generated_artifacts(skill_dir)
    validate_neutrality(skill_dir)
    validate_interpreter_fallback(text)
    run_unit_tests(skill_dir)
    return {
        "validation": "PASS",
        "endpoint_entries": endpoint_count,
        "bash_fences": bash_count,
        "python_files": python_count,
        "interpreter_fallback": "PASS",
        "unit_tests": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = validate(args.skill_dir.resolve())
    except ValidationFailure as exc:
        print(f"validation=FAIL check={exc.check}", file=sys.stderr)
        return 1
    print(" ".join(f"{key}={value}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
