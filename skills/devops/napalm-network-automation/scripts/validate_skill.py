#!/usr/bin/env python
"""Deterministically validate the shareable NAPALM skill."""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap


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


def validate_frontmatter(text: str) -> None:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    require(match is not None, "frontmatter_shape")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line and not line.startswith((" ", "\t")) and ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    require(fields.get("name") == "napalm-network-automation", "frontmatter_name")
    require(fields.get("version") == "1.0.0", "frontmatter_version")
    description = fields.get("description", "")
    require(description.startswith("Use when operating or testing network devices"), "description_trigger")
    require(len(description) <= 1024, "description_length")


def python_blocks(text: str) -> list[str]:
    return [
        textwrap.dedent(block)
        for block in re.findall(r"```python\r?\n(.*?)\r?\n\s*```", text, re.DOTALL)
    ]


def validate_python(skill_dir: Path) -> tuple[int, int]:
    files = sorted(skill_dir.rglob("*.py"))
    require(bool(files), "python_files_present")
    for path in files:
        try:
            ast.parse(read_text(path), filename=str(path))
        except SyntaxError as exc:
            raise ValidationFailure(f"python_ast:{path.name}") from exc
    blocks: list[str] = []
    for path in sorted(skill_dir.rglob("*.md")):
        blocks.extend(python_blocks(read_text(path)))
    require(bool(blocks), "python_fences_present")
    for index, block in enumerate(blocks, start=1):
        try:
            ast.parse(block, filename=f"python-fence-{index}")
        except SyntaxError as exc:
            raise ValidationFailure(f"python_fence_ast:{index}") from exc
    return len(files), len(blocks)


def validate_references(skill_dir: Path, skill_text: str) -> int:
    names = sorted(path.name for path in (skill_dir / "references").glob("*.md"))
    require(len(names) == 9, "reference_count")
    for name in names:
        relative = f"references/{name}"
        require(relative in skill_text, f"reference_linked:{name}")
    return len(names)


def validate_contract(skill_dir: Path) -> None:
    paths = [skill_dir / "SKILL.md", *sorted((skill_dir / "references").glob("*.md")), skill_dir / "scripts" / "mock_canary.py"]
    text = "\n".join(read_text(path) for path in paths)
    phrases = (
        "Python `>=3.10`",
        "runtime secret mechanism",
        "context manager",
        "NotImplementedError",
        "compare_config",
        "discard_config",
        "commit_config(revert_in=",
        "has_pending_commit",
        "confirm_commit",
        "rollback",
        "compliance_report",
        "skipped",
        "AssertionError",
        "ValueError",
        "per method",
        "mock_canary=PASS",
        "explicit authorization",
    )
    for phrase in phrases:
        require(phrase in text, f"contract_phrase:{phrase}")
    unsafe_recipes = (
        r"['\"]ssh_strict['\"]\s*:\s*False",
        r"['\"]ssl_verify['\"]\s*:\s*False",
        r"StrictHostKeyChecking=no",
        r"--password\s+[^<\s]",
    )
    for pattern in unsafe_recipes:
        require(re.search(pattern, text) is None, f"unsafe_recipe:{pattern}")


def validate_neutrality(skill_dir: Path) -> None:
    patterns = {
        "ipv4_literal_absent": rb"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])",
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
    forbidden = {"__pycache__", ".pytest_cache", ".mypy_cache"}
    for path in skill_dir.rglob("*"):
        require(path.name not in forbidden, "generated_cache_absent")
        require(path.suffix.lower() not in {".pyc", ".pyo"}, "generated_bytecode_absent")


def run_canary(skill_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(skill_dir / "scripts" / "mock_canary.py")],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    require(result.returncode == 0, "mock_canary")
    require(result.stdout.strip() == "mock_canary=PASS facts_calls=2 interface_calls=1 unsupported=1 closed=true", "mock_canary_receipt")


def validate(skill_dir: Path) -> dict[str, int | str]:
    skill_text = read_text(skill_dir / "SKILL.md")
    validate_frontmatter(skill_text)
    references = validate_references(skill_dir, skill_text)
    python_files, python_fences = validate_python(skill_dir)
    validate_contract(skill_dir)
    validate_neutrality(skill_dir)
    validate_generated_artifacts(skill_dir)
    run_canary(skill_dir)
    return {"validation": "PASS", "references": references, "python_files": python_files, "python_fences": python_fences, "neutrality": "PASS", "mock_canary": "PASS"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = validate(args.skill_dir.resolve())
    except (ValidationFailure, subprocess.TimeoutExpired) as exc:
        check = exc.check if isinstance(exc, ValidationFailure) else "mock_canary_timeout"
        print(f"validation=FAIL check={check}", file=sys.stderr)
        return 1
    print(" ".join(f"{key}={value}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
