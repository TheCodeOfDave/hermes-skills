from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from urllib.parse import unquote, urlsplit
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "eve_api_acceptance.py"


class SyntheticEveHandler(BaseHTTPRequestHandler):
    folder_exists = False
    lab = None

    def log_message(self, format, *args):
        return

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send(self, http_status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(http_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.wfile.flush()

    def _route(self):
        return unquote(urlsplit(self.path).path)

    def do_POST(self):
        route = self._route()
        body = self._body()
        if route == "/api/auth/login":
            if not body.get("username") or not body.get("password"):
                self._send(401, {"status": "unauthorized", "code": 401})
                return
            self._send(200, {"status": "success", "code": 200})
            return
        if route == "/api/folders":
            type(self).folder_exists = True
            self._send(200, {"status": "success", "code": 200})
            return
        if route == "/api/labs":
            type(self).lab = dict(body)
            self._send(200, {"status": "success", "code": "200"})
            return
        self._send(404, {"code": 404})

    def do_PUT(self):
        route = self._route()
        body = self._body()
        if route.startswith("/api/labs/") and type(self).lab is not None:
            type(self).lab.update(body)
            self._send(200, {"status": "success", "code": 200})
            return
        self._send(404, {"code": 404})

    def do_DELETE(self):
        route = self._route()
        if route.startswith("/api/labs/") and type(self).lab is not None:
            type(self).lab = None
            self._send(200, {"status": "success", "code": 200})
            return
        if route.startswith("/api/folders/") and type(self).folder_exists:
            type(self).folder_exists = False
            self._send(200, {"status": "success", "code": 200})
            return
        self._send(404, {"code": 404})

    def do_GET(self):
        route = self._route()
        if route == "/api/auth":
            self._send(
                200,
                {
                    "status": "success",
                    "code": 200,
                    "data": {"folder": "/sample-home"},
                },
            )
            return
        if route == "/api/status":
            self._send(200, {"status": "success", "code": 200, "data": {}})
            return
        if route in {"/api/list/templates/", "/api/list/networks", "/api/list/roles"}:
            self._send(200, {"status": "success", "code": "200", "data": {}})
            return
        if route == "/api/auth/logout":
            self._send(200, {"status": "success", "code": 200})
            return
        if route.startswith("/api/labs/"):
            if type(self).lab is None:
                self._send(404, {"code": 404})
            else:
                self._send(
                    200,
                    {"status": "success", "code": "200", "data": dict(type(self).lab)},
                )
            return
        if route.startswith("/api/folders/"):
            if type(self).folder_exists or route == "/api/folders/sample-home":
                self._send(200, {"status": "success", "code": 200, "data": {}})
            else:
                self._send(404, {"status": "fail", "code": 404})
            return
        self._send(404, {"code": 404})


class CommandLineAcceptanceTests(unittest.TestCase):
    def setUp(self):
        SyntheticEveHandler.folder_exists = False
        SyntheticEveHandler.lab = None
        self.server = ThreadingHTTPServer(("localhost", 0), SyntheticEveHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


    def _load_module(self):
        spec = importlib.util.spec_from_file_location("eve_api_acceptance_cli", SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load acceptance script")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _run_in_process(self, *arguments):
        module = self._load_module()
        original = os.environ.copy()
        os.environ.update(
            {
                "EVE_BASE_URL": f"http://{self.server.server_address[0]}:{self.server.server_port}",
                "EVE_USERNAME": "sample-user",
                "EVE_PASSWORD": "sample-value",
            }
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                returncode = module.main(list(arguments))
        finally:
            os.environ.clear()
            os.environ.update(original)
        return subprocess.CompletedProcess(
            arguments, returncode, stdout.getvalue(), stderr.getvalue()
        )

    def test_read_only_cli_verifies_layers_without_leaking_inputs(self):
        result = self._run_in_process("--mode", "read-only")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"operation":"appliance_status"', result.stdout)
        self.assertIn('"operation":"logout"', result.stdout)
        self.assertNotIn("sample-user", result.stdout + result.stderr)
        self.assertNotIn("sample-value", result.stdout + result.stderr)
        self.assertNotIn("localhost", result.stdout + result.stderr)

    def test_disposable_cli_completes_cleanup_and_sanitizes_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            recovery_directory = Path(directory) / "protected-recovery"
            prepared = self._run_in_process(
                "--prepare-recovery-directory",
                str(recovery_directory),
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertIn('"operation":"recovery_directory_prepared"', prepared.stdout)
            self.assertNotIn(str(recovery_directory), prepared.stdout + prepared.stderr)
            module = self._load_module()
            if os.name == "nt":
                self.assertTrue(module._windows_acl_is_private(recovery_directory))
            recovery = recovery_directory / "recovery.json"
            result = self._run_in_process(
                "--mode",
                "disposable-lab",
                "--approve-create-modify",
                "--approve-delete-temporary-lab-and-folder",
                "--recovery-file",
                str(recovery),
                "--run-token",
                "fixedtoken",
            )
            self.assertFalse(recovery.exists())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"operation":"lab_modification_readback"', result.stdout)
        self.assertIn('"operation":"folder_absent_after_cleanup"', result.stdout)
        self.assertFalse(SyntheticEveHandler.folder_exists)
        self.assertIsNone(SyntheticEveHandler.lab)
        combined = result.stdout + result.stderr
        for forbidden in ("sample-user", "sample-value", "localhost", "sample-home", "api-check-"):
            self.assertNotIn(forbidden, combined)

    def test_disposable_cli_refuses_before_login_without_create_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._run_in_process(
                "--mode",
                "disposable-lab",
                "--recovery-file",
                str(Path(directory) / "recovery.json"),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"error":"authorization"', result.stderr)
        self.assertIsNone(SyntheticEveHandler.lab)
        self.assertFalse(SyntheticEveHandler.folder_exists)


if __name__ == "__main__":
    unittest.main()
