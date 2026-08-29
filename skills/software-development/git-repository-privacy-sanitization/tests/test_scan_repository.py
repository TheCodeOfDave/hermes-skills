from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scan_repository.py"


def load_scanner():
    spec = importlib.util.spec_from_file_location("privacy_scanner", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load privacy scanner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class UrlPlaceholderRegressionTests(unittest.TestCase):
    def test_bracketed_placeholder_url_is_reported_without_aborting_scan(self):
        module = load_scanner()
        findings = []

        module.scan_text(
            "Reference: https://[placeholder]/api/resource",
            surface="fixture",
            location="fixture.md",
            identifiers=[],
            findings=findings,
        )

        self.assertTrue(any(item["category"] == "external_reference" for item in findings))

    def test_dotnet_static_call_is_not_classified_as_ipv6(self):
        module = load_scanner()
        findings = []

        module.scan_text(
            "PowerShell: [Example.Type]::Create()",
            surface="fixture",
            location="fixture.ps1",
            identifiers=[],
            findings=findings,
        )

        self.assertNotIn("ip_address", [item["category"] for item in findings])

    def test_bracketed_unspecified_ipv6_is_still_reported(self):
        module = load_scanner()
        findings = []

        module.scan_text(
            "Endpoint: https://[::]/",
            surface="fixture",
            location="fixture.md",
            identifiers=[],
            findings=findings,
        )

        self.assertIn("ip_address", [item["category"] for item in findings])


if __name__ == "__main__":
    unittest.main()
