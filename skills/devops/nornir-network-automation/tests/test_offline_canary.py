from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "offline_canary.py"


class OfflineCanaryTests(unittest.TestCase):
    def test_offline_canary_exercises_exact_bounded_read_only_run(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "offline_canary=PASS targets=2 failed=0 changed=0 workers=2",
        )


if __name__ == "__main__":
    unittest.main()
