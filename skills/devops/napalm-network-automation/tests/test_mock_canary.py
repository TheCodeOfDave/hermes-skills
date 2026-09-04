from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "mock_canary.py"


class MockCanaryTests(unittest.TestCase):
    def test_mock_canary_proves_current_sequence_and_cleanup(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "mock_canary=PASS facts_calls=2 interface_calls=1 unsupported=1 closed=true")


if __name__ == "__main__":
    unittest.main()
