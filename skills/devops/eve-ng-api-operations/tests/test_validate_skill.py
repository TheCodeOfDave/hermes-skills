from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
VALIDATOR = SKILL_DIR / "scripts" / "validate_skill.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("eve_skill_validator", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DeterministicValidatorTests(unittest.TestCase):
    def test_frontmatter_and_selector_extraction_accept_crlf(self):
        module = load_validator()
        text = (SKILL_DIR / "SKILL.md").read_bytes().decode("utf-8")
        crlf = text.replace("\n", "\r\n")
        module.validate_frontmatter(crlf)
        selector = module.extract_python_selector(crlf)
        self.assertIn(b"select_python()", selector)

    def _run(self, skill_dir):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--skill-dir", str(skill_dir)],
            text=True,
            capture_output=True,
            timeout=240,
        )

    def test_repository_candidate_passes_all_deterministic_checks(self):
        result = self._run(SKILL_DIR)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validation=PASS", result.stdout)
        self.assertIn("endpoint_entries=42", result.stdout)
        self.assertIn("interpreter_fallback=PASS", result.stdout)
        self.assertIn("unit_tests=PASS", result.stdout)

    def test_duplicate_endpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "eve-ng-api-operations"
            shutil.copytree(SKILL_DIR, candidate)
            endpoint_file = candidate / "references" / "api-endpoints.md"
            with endpoint_file.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write("\n| `GET` | `/api/status` | Duplicate fixture. |\n")
            result = self._run(candidate)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("endpoint_method_route_unique", result.stderr)


if __name__ == "__main__":
    unittest.main()
