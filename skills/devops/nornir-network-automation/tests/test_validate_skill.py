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
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--skill-dir", str(skill_dir)],
            text=True,
            capture_output=True,
            timeout=60,
        )

    def copy_candidate(self, directory: str) -> Path:
        candidate = Path(directory) / "nornir-network-automation"
        shutil.copytree(SKILL_DIR, candidate)
        return candidate

    def test_repository_candidate_passes(self):
        result = self.run_validator(SKILL_DIR)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validation=PASS", result.stdout)
        self.assertIn("neutrality=PASS", result.stdout)
        self.assertIn("unit_tests=PASS", result.stdout)
        self.assertIn("offline_canary=PASS", result.stdout)

    def test_weakened_ssh_verification_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            reference = candidate / "references" / "inventory-filtering-and-secrets.md"
            text = reference.read_text(encoding="utf-8")
            reference.write_text(
                text.replace("ssh_strict: true", "ssh_strict: false", 1),
                encoding="utf-8",
            )
            result = self.run_validator(candidate)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe_default:ssh_strict: false", result.stderr)

    def test_private_address_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            private_address = ".".join(str(part) for part in (10, 23, 45, 67))
            skill = candidate / "SKILL.md"
            with skill.open("a", encoding="utf-8") as handle:
                handle.write(f"\nSynthetic fixture: {private_address}\n")
            result = self.run_validator(candidate)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("private_ipv4_absent:SKILL.md", result.stderr)

    def test_serial_jump_and_async_cli_contract_is_documented(self):
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        reference = (SKILL_DIR / "references" / "napalm-read-only-canary.md").read_text(encoding="utf-8")
        self.assertIn("plugin: serial", skill)
        self.assertIn("open the jump channel inside the per-host task", reference)
        self.assertIn("Do not pre-open channels", reference)
        self.assertIn("send_command_timing", reference)

    def test_unit_testing_contract_is_documented_and_executable(self):
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        guide_path = SKILL_DIR / "references" / "unit-testing-nornir.md"

        self.assertIn("references/unit-testing-nornir.md", skill)
        self.assertTrue(guide_path.is_file())
        guide = guide_path.read_text(encoding="utf-8")
        for phrase in (
            "in-memory inventory",
            "AggregatedResult",
            "MultiResult",
            "reset_failed_hosts()",
            "nested subtasks",
            "mocked NAPALM connection",
            "SerialRunner",
            "ThreadedRunner",
            "close_connections",
        ):
            self.assertIn(phrase, guide)

        result = self.run_validator(SKILL_DIR)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unit_tests=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
