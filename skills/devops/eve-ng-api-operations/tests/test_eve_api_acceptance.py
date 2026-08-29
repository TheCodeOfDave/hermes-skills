from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from http.client import IncompleteRead
import os
from pathlib import Path
import tempfile
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "eve_api_acceptance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("eve_api_acceptance", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load acceptance module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def private_temp_directory(module):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        if os.name == "nt":
            module._set_windows_private_acl(path, directory=True)
        yield path


class FakeEveClient:
    def __init__(self, module, *, corrupt_marker: bool = False):
        self.module = module
        self.corrupt_marker = corrupt_marker
        self.calls = []
        self.folder_exists = False
        self.lab = None

    def request(self, method, route, body=None):
        self.calls.append((method, route, body))
        if method == "GET" and route.startswith("/api/folders/"):
            if self.folder_exists:
                return self.module.ApiResponse(200, {"status": "success", "code": 200, "data": {}})
            return self.module.ApiResponse(404, {"status": "fail", "code": 404})
        if method == "GET" and route.startswith("/api/labs/"):
            if self.lab is None:
                return self.module.ApiResponse(404, {"code": "404"})
            data = dict(self.lab)
            if self.corrupt_marker:
                data["description"] = "different marker"
            return self.module.ApiResponse(200, {"status": "success", "code": "200", "data": data})
        if method == "POST" and route == "/api/folders":
            self.folder_exists = True
            return self.module.ApiResponse(200, {"status": "success", "code": 200})
        if method == "POST" and route == "/api/labs":
            self.lab = dict(body)
            return self.module.ApiResponse(200, {"status": "success", "code": 200})
        if method == "PUT" and route.startswith("/api/labs/"):
            self.lab.update(body)
            return self.module.ApiResponse(200, {"status": "success", "code": "200"})
        if method == "DELETE" and route.startswith("/api/labs/"):
            self.lab = None
            return self.module.ApiResponse(200, {"status": "success", "code": 200})
        if method == "DELETE" and route.startswith("/api/folders/"):
            self.folder_exists = False
            return self.module.ApiResponse(200, {"status": "success", "code": 200})
        raise AssertionError((method, route, body))


class ResponseVerificationTests(unittest.TestCase):
    def test_tls_is_strict_by_default_and_insecure_only_when_requested(self):
        module = load_module()
        strict = module.EveApiClient("https://example.invalid")
        insecure = module.EveApiClient("https://example.invalid", insecure=True)
        strict_handlers = [
            handler for handler in strict.opener.handlers
            if handler.__class__.__name__ == "HTTPSHandler"
        ]
        insecure_handlers = [
            handler for handler in insecure.opener.handlers
            if handler.__class__.__name__ == "HTTPSHandler"
        ]
        self.assertEqual(len(strict_handlers), 1)
        strict_context = getattr(strict_handlers[0], "_context", None)
        if strict_context is not None:
            self.assertNotEqual(strict_context.verify_mode, module.ssl.CERT_NONE)
        self.assertEqual(len(insecure_handlers), 1)
        self.assertEqual(
            getattr(insecure_handlers[0], "_context").verify_mode,
            module.ssl.CERT_NONE,
        )

    def test_incomplete_http_response_is_classified_as_transport_failure(self):
        module = load_module()

        class BrokenOpener:
            def open(self, request, timeout):
                raise IncompleteRead(b"partial", 10)

        client = module.EveApiClient("https://example.invalid")
        client.opener = BrokenOpener()
        with self.assertRaises(module.TransportError):
            client.request("GET", "/api/status")

    def test_normalizes_numeric_and_string_jsend_codes(self):
        module = load_module()

        self.assertEqual(module.normalize_jsend_code(200), "200")
        self.assertEqual(module.normalize_jsend_code("200"), "200")
        self.assertIsNone(module.normalize_jsend_code(None))
        with self.assertRaises(module.VerificationError):
            module.normalize_jsend_code(True)

    def test_success_requires_transport_http_jsend_and_postcondition(self):
        module = load_module()

        result = module.verify_response(
            operation="synthetic_check",
            transport_ok=True,
            http_status=200,
            payload={"status": "success", "code": "200", "data": {}},
            expected_http={200},
            expected_status="success",
            postcondition=True,
        )

        self.assertEqual(
            result,
            {
                "operation": "synthetic_check",
                "transport": "success",
                "transport_code": 0,
                "http": 200,
                "status": "success",
                "code": "200",
                "verified": True,
            },
        )
        self.assertNotIn("data", result)

    def test_identity_home_accepts_root_folder(self):
        module = load_module()
        response = module.ApiResponse(
            200,
            {"status": "success", "code": 200, "data": {"folder": "/"}},
        )
        self.assertEqual(module._identity_home(response), "/")

    def test_exact_404_proves_absence_without_requiring_jsend_status(self):
        module = load_module()

        no_status = module.verify_absence("lab_absent", 404, {"code": 404})
        fail_status = module.verify_absence(
            "folder_absent", 404, {"code": "404", "status": "fail"}
        )

        self.assertTrue(no_status["verified"])
        self.assertTrue(fail_status["verified"])
        self.assertIsNone(no_status["status"])
        self.assertEqual(fail_status["status"], "fail")
        with self.assertRaises(module.VerificationError):
            module.verify_absence("not_absent", 200, {"status": "success", "code": 200})

    def test_success_rejects_a_missing_jsend_code(self):
        module = load_module()

        with self.assertRaises(module.VerificationError):
            module.verify_response(
                operation="missing_code",
                transport_ok=True,
                http_status=200,
                payload={"status": "success"},
                expected_http={200},
                expected_status="success",
                postcondition=True,
            )


class RecoveryDirectoryTests(unittest.TestCase):
    def test_existing_empty_directory_is_preserved(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "existing"
            target.mkdir()
            with self.assertRaises(module.VerificationError):
                module.prepare_recovery_directory(target)
            self.assertTrue(target.is_dir())


class DisposableWorkflowTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows ACL behavior")
    def test_windows_insecure_parent_fails_before_remote_calls(self):
        module = load_module()
        client = FakeEveClient(module)
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            module._set_windows_private_acl(parent, directory=True)
            module._windows_command(
                [
                    "icacls.exe",
                    str(parent),
                    "/grant",
                    "*S-1-5-32-545:(RX)",
                ]
            )
            try:
                with self.assertRaises(module.VerificationError):
                    module.run_disposable_acceptance(
                        client,
                        parent_path="/sample-home",
                        run_token="fixedtoken",
                        approve_create_modify=True,
                        approve_delete=True,
                        recovery_file=parent / "recovery.json",
                    )
                self.assertEqual(client.calls, [])
                self.assertFalse((parent / "recovery.json").exists())
            finally:
                module._set_windows_private_acl(parent, directory=True)

    def test_without_delete_approval_retains_owned_objects_and_recovery(self):
        module = load_module()
        client = FakeEveClient(module)
        with private_temp_directory(module) as directory:
            recovery = Path(directory) / "recovery.json"
            receipts = module.run_disposable_acceptance(
                client,
                parent_path="/sample-home",
                run_token="fixedtoken",
                approve_create_modify=True,
                approve_delete=False,
                recovery_file=recovery,
            )
            self.assertTrue(recovery.exists())
            if os.name == "nt":
                self.assertTrue(module._windows_acl_is_private(recovery))
        self.assertNotIn("DELETE", [method for method, _, _ in client.calls])
        self.assertTrue(client.folder_exists)
        self.assertIsNotNone(client.lab)
        self.assertEqual(receipts[-1]["operation"], "lab_modification_readback")

    def test_refuses_preexisting_recovery_file_without_remote_calls(self):
        module = load_module()
        client = FakeEveClient(module)
        with private_temp_directory(module) as directory:
            recovery = Path(directory) / "recovery.json"
            recovery.write_text("preserve-me", encoding="utf-8")
            with self.assertRaises(module.VerificationError):
                module.run_disposable_acceptance(
                    client,
                    parent_path="/sample-home",
                    run_token="fixedtoken",
                    approve_create_modify=True,
                    approve_delete=True,
                    recovery_file=recovery,
                )
            self.assertEqual(recovery.read_text(encoding="utf-8"), "preserve-me")
            self.assertEqual(client.calls, [])

    def test_refuses_mutation_without_explicit_gate(self):
        module = load_module()
        client = FakeEveClient(module)

        with self.assertRaises(module.AuthorizationError):
            module.run_disposable_acceptance(
                client,
                parent_path="/sample-home",
                run_token="fixedtoken",
                approve_create_modify=False,
                approve_delete=False,
                recovery_file=None,
            )

        self.assertEqual(client.calls, [])

    def test_root_parent_uses_canonical_single_slash_paths(self):
        module = load_module()
        client = FakeEveClient(module)
        with private_temp_directory(module) as directory:
            module.run_disposable_acceptance(
                client,
                parent_path="/",
                run_token="fixedtoken",
                approve_create_modify=True,
                approve_delete=True,
                recovery_file=Path(directory) / "recovery.json",
            )
        folder_create = next(
            body for method, route, body in client.calls
            if method == "POST" and route == "/api/folders"
        )
        lab_create = next(
            body for method, route, body in client.calls
            if method == "POST" and route == "/api/labs"
        )
        self.assertEqual(folder_create["path"], "/")
        self.assertEqual(lab_create["path"], "/api-check-fixedtoken")
        self.assertTrue(all("//" not in route for _, route, _ in client.calls))

    def test_interior_duplicate_parent_separators_are_canonicalized(self):
        module = load_module()
        client = FakeEveClient(module)
        with private_temp_directory(module) as directory:
            module.run_disposable_acceptance(
                client,
                parent_path="/team//nested/",
                run_token="fixedtoken",
                approve_create_modify=True,
                approve_delete=True,
                recovery_file=Path(directory) / "recovery.json",
            )
        lab_create = next(
            body for method, route, body in client.calls
            if method == "POST" and route == "/api/labs"
        )
        self.assertEqual(
            lab_create["path"], "/team/nested/api-check-fixedtoken"
        )

    def test_create_modify_delete_is_exact_and_ownership_gated(self):
        module = load_module()
        client = FakeEveClient(module)
        with private_temp_directory(module) as directory:
            recovery = Path(directory) / "recovery.json"
            receipts = module.run_disposable_acceptance(
                client,
                parent_path="/sample-home",
                run_token="fixedtoken",
                approve_create_modify=True,
                approve_delete=True,
                recovery_file=recovery,
            )

            self.assertFalse(recovery.exists())

        methods = [method for method, _, _ in client.calls]
        self.assertEqual(
            methods,
            ["GET", "GET", "POST", "GET", "POST", "GET", "PUT", "GET", "DELETE", "GET", "DELETE", "GET"],
        )
        self.assertEqual(receipts[-1]["operation"], "folder_absent_after_cleanup")
        self.assertTrue(all(receipt["verified"] for receipt in receipts))
        self.assertFalse(client.folder_exists)
        self.assertIsNone(client.lab)

    def test_marker_mismatch_blocks_all_deletes_and_retains_recovery_record(self):
        module = load_module()
        client = FakeEveClient(module, corrupt_marker=True)
        with private_temp_directory(module) as directory:
            recovery = Path(directory) / "recovery.json"
            with self.assertRaises(module.OwnershipError):
                module.run_disposable_acceptance(
                    client,
                    parent_path="/sample-home",
                    run_token="fixedtoken",
                    approve_create_modify=True,
                    approve_delete=True,
                    recovery_file=recovery,
                )

            self.assertTrue(recovery.exists())

        self.assertNotIn("DELETE", [method for method, _, _ in client.calls])
        self.assertTrue(client.folder_exists)
        self.assertIsNotNone(client.lab)


if __name__ == "__main__":
    unittest.main()
