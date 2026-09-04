from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
VALIDATOR = SKILL_DIR / "scripts" / "validate_skill.py"


class DeterministicValidatorTests(unittest.TestCase):
    def run_validator(self, skill_dir: Path):
        return subprocess.run([sys.executable, str(VALIDATOR), "--skill-dir", str(skill_dir)], text=True, capture_output=True, timeout=60)

    def copy_candidate(self, directory: str) -> Path:
        candidate = Path(directory) / "napalm-network-automation"
        shutil.copytree(SKILL_DIR, candidate)
        return candidate

    def test_repository_candidate_passes(self):
        result = self.run_validator(SKILL_DIR)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validation=PASS", result.stdout)
        self.assertIn("neutrality=PASS", result.stdout)
        self.assertIn("mock_canary=PASS", result.stdout)

    def test_literal_address_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            literal = ".".join(str(part) for part in (203, 0, 113, 8))
            with (candidate / "SKILL.md").open("a", encoding="utf-8") as handle:
                handle.write(f"\nSynthetic fixture: {literal}\n")
            result = self.run_validator(candidate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ipv4_literal_absent:SKILL.md", result.stderr)

    def test_inline_cli_password_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            unsafe = "--" + "password" + " literal-value"
            with (candidate / "SKILL.md").open("a", encoding="utf-8") as handle:
                handle.write(f"\nSynthetic fixture: {unsafe}\n")
            result = self.run_validator(candidate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe_recipe:", result.stderr)

    def test_ios_merge_false_success_contract_is_documented(self):
        transaction = (SKILL_DIR / "references" / "configuration-transactions.md").read_text(encoding="utf-8")
        caveats = (SKILL_DIR / "references" / "support-caveats-and-security.md").read_text(encoding="utf-8")
        self.assertIn("Command rejected:", transaction)
        self.assertIn("semantic readback", transaction)
        self.assertIn("interface range", transaction)
        self.assertIn("switchport trunk encapsulation dot1q", caveats)
        self.assertIn("duplicate SVI MAC", caveats)


if __name__ == "__main__":
    unittest.main()
