#!/usr/bin/env python
"""Deterministically validate the reusable Nornir skill."""

from __future__ import annotations

import argparse
import ast
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


def read_text(path: Path) -> str:
    require(path.is_file(), f"file_exists:{path.name}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationFailure(f"utf8:{path.name}") from exc


def validate_frontmatter(skill_text: str) -> None:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", skill_text, re.DOTALL)
    require(match is not None, "frontmatter_shape")
    frontmatter = match.group(1)
    fields = {}
    for line in frontmatter.splitlines():
        if line and not line.startswith((" ", "\t")) and ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    require(fields.get("name") == "nornir-network-automation", "frontmatter_name")
    require(fields.get("version") == "1.1.0", "frontmatter_version")
    description = fields.get("description", "")
    require(description.startswith("Use when orchestrating network automation"), "description_trigger")
    require(len(description) <= 1024, "description_length")


def validate_references(skill_dir: Path, skill_text: str) -> int:
    names = [
        "references/inventory-filtering-and-secrets.md",
        "references/napalm-read-only-canary.md",
        "references/unit-testing-nornir.md",
    ]
    for name in names:
        require(name in skill_text, f"reference_linked:{name}")
        require((skill_dir / name).is_file(), f"reference_exists:{name}")
    return len(names)


def python_blocks(text: str) -> list[str]:
    return re.findall(r"```python\r?\n(.*?)\r?\n```", text, re.DOTALL)


def validate_python(skill_dir: Path) -> tuple[int, int]:
    files = sorted(skill_dir.rglob("*.py"))
    require(bool(files), "python_files_present")
    for path in files:
        try:
            ast.parse(read_text(path), filename=str(path))
        except SyntaxError as exc:
            raise ValidationFailure(f"python_ast:{path.name}") from exc
    blocks = []
    for path in sorted(skill_dir.rglob("*.md")):
        blocks.extend(python_blocks(read_text(path)))
    require(bool(blocks), "python_fences_present")
    for index, block in enumerate(blocks, start=1):
        try:
            ast.parse(block, filename=f"python-fence-{index}")
        except SyntaxError as exc:
            raise ValidationFailure(f"python_fence_ast:{index}") from exc
    return len(files), len(blocks)


def validate_contract(skill_dir: Path) -> None:
    contract_paths = [
        skill_dir / "SKILL.md",
        *sorted((skill_dir / "references").glob("*.md")),
        skill_dir / "scripts" / "offline_canary.py",
    ]
    all_text = "\n".join(read_text(path) for path in contract_paths)
    required = (
        "exact target",
        "Runtime-only credentials",
        "Strict transport verification",
        "Read-only first",
        "Bounded concurrency",
        "AggregatedResult",
        "close_connections",
        'getters=["facts"]',
        "failed=false",
        "changed=false",
        "in-memory inventory",
        "reset_failed_hosts()",
        "mocked NAPALM connection",
    )
    for phrase in required:
        require(phrase in all_text, f"contract_phrase:{phrase}")
    forbidden = (
        "ssh_strict: false",
        "host_key_auto_add: true",
        "ssl_verify: false",
        "StrictHostKeyChecking=no",
    )
    for phrase in forbidden:
        require(phrase not in all_text, f"unsafe_default:{phrase}")


def validate_neutrality(skill_dir: Path) -> None:
    patterns = {
        "private_ipv4_absent": rb"(?<![0-9])(?:10\.|192\.168\.|172\.(?:1[6-9]|2[0-9]|3[01])\.)[0-9]{1,3}(?:\.[0-9]{1,3}){2}(?![0-9])",
        "email_absent": rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "windows_home_absent": rb"(?i)[A-Z]:[\\/]Users[\\/][^<\\/\s]+",
        "posix_home_absent": rb"/(?:home|Users)/[^<\/\s]+",
        "credential_literal_absent": rb"(?i)(?:password|token|secret)\s*[:=]\s*['\"][^<\n'\"]{8,}",
        "private_key_absent": rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
    }
    for path in skill_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".py", ".yaml", ".yml"}:
            continue
        data = path.read_bytes()
        for check, pattern in patterns.items():
            require(re.search(pattern, data) is None, f"{check}:{path.name}")


def validate_generated_artifacts(skill_dir: Path) -> None:
    forbidden_names = {"__pycache__", ".pytest_cache", ".mypy_cache"}
    for path in skill_dir.rglob("*"):
        require(path.name not in forbidden_names, "generated_cache_absent")
        require(path.suffix.lower() not in {".pyc", ".pyo"}, "generated_bytecode_absent")


def run_offline_canary(skill_dir: Path) -> None:
    script = skill_dir / "scripts" / "offline_canary.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationFailure("offline_canary_timeout") from exc
    require(result.returncode == 0, "offline_canary")
    require(
        result.stdout.strip()
        == "offline_canary=PASS targets=2 failed=0 changed=0 workers=2",
        "offline_canary_receipt",
    )


def run_unit_tests(skill_dir: Path) -> None:
    test_file = skill_dir / "tests" / "test_unit_test_harness.py"
    try:
        result = subprocess.run(
            [sys.executable, "-B", str(test_file)],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationFailure("unit_tests_timeout") from exc
    require(result.returncode == 0, "unit_tests")
    require(
        "Ran 9 tests" in result.stderr and "OK" in result.stderr,
        "unit_tests_receipt",
    )


def validate(skill_dir: Path) -> dict[str, int | str]:
    skill_text = read_text(skill_dir / "SKILL.md")
    validate_frontmatter(skill_text)
    reference_count = validate_references(skill_dir, skill_text)
    python_count, fence_count = validate_python(skill_dir)
    validate_contract(skill_dir)
    validate_neutrality(skill_dir)
    validate_generated_artifacts(skill_dir)
    run_unit_tests(skill_dir)
    run_offline_canary(skill_dir)
    return {
        "validation": "PASS",
        "references": reference_count,
        "python_files": python_count,
        "python_fences": fence_count,
        "neutrality": "PASS",
        "unit_tests": "PASS",
        "offline_canary": "PASS",
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
