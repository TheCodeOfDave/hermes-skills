#!/usr/bin/env python
"""Sanitized EVE-NG API acceptance checks.

Output contains only operation labels and verification state. Response payloads,
URLs, credentials, cookies, and target names are not logged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import ssl
import stat
import subprocess
import sys
from typing import Any, Iterable, Mapping, NamedTuple
from urllib.error import HTTPError, URLError
from http.client import HTTPException
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener
import http.cookiejar
from urllib.parse import quote
import argparse


class VerificationError(RuntimeError):
    """A transport, protocol, envelope, or postcondition check failed."""


class AuthorizationError(RuntimeError):
    """A required explicit side-effect gate was not supplied."""


class OwnershipError(RuntimeError):
    """The temporary objects cannot be proven to belong to this run."""


class TransportError(RuntimeError):
    """A request failed before a valid HTTP response was received."""


class ApiResponse(NamedTuple):
    http_status: int
    payload: Mapping[str, Any]


def normalize_jsend_code(value: Any) -> str | None:
    """Normalize numeric/string JSend codes without accepting booleans."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise VerificationError("invalid JSend code type")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.isdigit():
        return value
    raise VerificationError("invalid JSend code value")


def verify_response(
    *,
    operation: str,
    transport_ok: bool,
    http_status: int,
    payload: Mapping[str, Any],
    expected_http: Iterable[int],
    expected_status: str | None,
    postcondition: bool,
) -> dict[str, Any]:
    """Verify all response layers and return a payload-free receipt."""
    if not transport_ok:
        raise VerificationError(f"{operation}: transport failed")
    if http_status not in set(expected_http):
        raise VerificationError(f"{operation}: unexpected HTTP status")
    status = payload.get("status")
    if expected_status is not None and status != expected_status:
        raise VerificationError(f"{operation}: unexpected JSend status")
    code = normalize_jsend_code(payload.get("code"))
    if code is None:
        raise VerificationError(f"{operation}: missing JSend code")
    if code != str(http_status):
        raise VerificationError(f"{operation}: HTTP/JSend code mismatch")
    if not postcondition:
        raise VerificationError(f"{operation}: postcondition failed")
    return {
        "operation": operation,
        "transport": "success",
        "transport_code": 0,
        "http": http_status,
        "status": status,
        "code": code,
        "verified": True,
    }


def verify_absence(
    operation: str, http_status: int, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Accept an exact 404 whether JSend status is missing or ``fail``."""
    if http_status != 404:
        raise VerificationError(f"{operation}: exact target is not absent")
    status = payload.get("status")
    if status not in (None, "fail"):
        raise VerificationError(f"{operation}: unexpected JSend absence status")
    code = normalize_jsend_code(payload.get("code"))
    if code is not None and code != "404":
        raise VerificationError(f"{operation}: HTTP/JSend code mismatch")
    return {
        "operation": operation,
        "transport": "success",
        "transport_code": 0,
        "http": 404,
        "status": status,
        "code": code,
        "verified": True,
    }


def encode_object_path(path: str) -> str:
    """Encode an EVE object path one segment at a time."""
    return "/".join(quote(segment, safe="") for segment in path.strip("/").split("/"))


def _success(
    operation: str, response: ApiResponse, *, postcondition: bool = True
) -> dict[str, Any]:
    return verify_response(
        operation=operation,
        transport_ok=True,
        http_status=response.http_status,
        payload=response.payload,
        expected_http={200},
        expected_status="success",
        postcondition=postcondition,
    )


def _data(response: ApiResponse) -> Mapping[str, Any]:
    value = response.payload.get("data")
    return value if isinstance(value, Mapping) else {}


_WINDOWS_CURRENT_SID_SCRIPT = (
    "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value"
)
_WINDOWS_ALLOW_SIDS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$acl = Get-Acl -LiteralPath $env:HERMES_ACL_TARGET
$sids = @()
foreach ($rule in $acl.Access) {
    if ($rule.AccessControlType -eq 'Allow') {
        try {
            $sids += $rule.IdentityReference.Translate(
                [System.Security.Principal.SecurityIdentifier]
            ).Value
        } catch {}
    }
}
$sids | Sort-Object -Unique | ConvertTo-Json -Compress
"""
_WINDOWS_PRIVATE_ACL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$required = @($current, 'S-1-5-18', 'S-1-5-32-544')
$acl = Get-Acl -LiteralPath $env:HERMES_ACL_TARGET
if ($acl.Owner -match '^S-1-(\d+-)+\d+$') {
    $owner = $acl.Owner
} else {
    try {
        $owner = ([System.Security.Principal.NTAccount]::new($acl.Owner)).Translate(
            [System.Security.Principal.SecurityIdentifier]
        ).Value
    } catch {
        $owner = ''
    }
}
$allowSids = @()
$bad = 0
foreach ($rule in $acl.Access) {
    if ($rule.AccessControlType -eq 'Allow') {
        try {
            $sid = $rule.IdentityReference.Translate(
                [System.Security.Principal.SecurityIdentifier]
            ).Value
        } catch {
            $sid = ''
        }
        $allowSids += $sid
        if ((-not $sid) -or ($required -notcontains $sid)) { $bad++ }
    }
}
$missing = @($required | Where-Object { $allowSids -notcontains $_ }).Count
[pscustomobject]@{
    private = (($required -contains $owner) -and ($bad -eq 0) -and ($missing -eq 0))
} | ConvertTo-Json -Compress
"""


def _windows_command(
    command: list[str], *, target: Path | None = None
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if target is not None:
        environment["HERMES_ACL_TARGET"] = str(target)
    try:
        result = subprocess.run(
            command,
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VerificationError("Windows ACL tooling failed") from exc
    if result.returncode != 0:
        raise VerificationError("Windows ACL tooling failed")
    return result


def _windows_current_sid() -> str:
    result = _windows_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _WINDOWS_CURRENT_SID_SCRIPT,
        ]
    )
    sid = result.stdout.strip()
    if not sid.startswith("S-") or not all(
        part.isdigit() for part in sid.removeprefix("S-").split("-")
    ):
        raise VerificationError("Windows identity SID was invalid")
    return sid


def _windows_allow_sids(path: Path) -> list[str]:
    result = _windows_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _WINDOWS_ALLOW_SIDS_SCRIPT,
        ],
        target=path,
    )
    try:
        parsed = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise VerificationError("Windows ACL output was invalid") from exc
    values = [parsed] if isinstance(parsed, str) else parsed
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise VerificationError("Windows ACL output was invalid")
    return values


def _windows_acl_is_private(path: Path) -> bool:
    result = _windows_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _WINDOWS_PRIVATE_ACL_SCRIPT,
        ],
        target=path,
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError("Windows ACL output was invalid") from exc
    return parsed.get("private") is True if isinstance(parsed, Mapping) else False


def _set_windows_private_acl(path: Path, *, directory: bool) -> None:
    current_sid = _windows_current_sid()
    allowed = {current_sid, "S-1-5-18", "S-1-5-32-544"}
    _windows_command(["icacls.exe", str(path), "/inheritance:r"])
    for sid in _windows_allow_sids(path):
        if sid not in allowed:
            _windows_command(["icacls.exe", str(path), "/remove:g", f"*{sid}"])
    suffix = ":(OI)(CI)F" if directory else ":F"
    _windows_command(
        [
            "icacls.exe",
            str(path),
            "/grant:r",
            f"*{current_sid}{suffix}",
            f"*S-1-5-18{suffix}",
            f"*S-1-5-32-544{suffix}",
        ]
    )
    if not _windows_acl_is_private(path):
        raise VerificationError("Windows ACL verification failed")


def prepare_recovery_directory(path: Path) -> None:
    created = False
    try:
        path.mkdir(mode=0o700)
        created = True
        if os.name == "nt":
            _set_windows_private_acl(path, directory=True)
        else:
            os.chmod(path, 0o700)
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise VerificationError("recovery directory must be owner-only")
    except (OSError, VerificationError) as exc:
        if created:
            try:
                path.rmdir()
            except OSError:
                pass
        if isinstance(exc, VerificationError):
            raise
        raise VerificationError("recovery directory could not be prepared") from exc


def _write_recovery_record(
    recovery_file: Path,
    *,
    folder_path: str,
    lab_path: str,
    marker: str,
) -> None:
    parent = recovery_file.parent
    if not parent.is_dir():
        raise VerificationError("recovery parent directory does not exist")
    if os.name == "nt":
        if not _windows_acl_is_private(parent):
            raise VerificationError("recovery parent Windows ACL is not private")
    elif os.name == "posix":
        try:
            parent_mode = stat.S_IMODE(parent.stat().st_mode)
        except OSError as exc:
            raise VerificationError("recovery parent could not be inspected") from exc
        if parent_mode & 0o077:
            raise VerificationError("recovery parent must be owner-only")

    payload = json.dumps(
        {"folder_path": folder_path, "lab_path": lab_path, "marker": marker},
        separators=(",", ":"),
    )
    try:
        descriptor: int | None = os.open(
            recovery_file,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        raise VerificationError("recovery file must not already exist") from exc
    except OSError as exc:
        raise VerificationError("recovery file could not be created") from exc

    try:
        if os.name == "nt":
            os.close(descriptor)
            descriptor = None
            _set_windows_private_acl(recovery_file, directory=False)
            if not _windows_acl_is_private(recovery_file):
                raise VerificationError("recovery file Windows ACL is not private")
            descriptor = os.open(recovery_file, os.O_WRONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "posix":
            directory_descriptor = os.open(
                parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    except (OSError, VerificationError) as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        recovery_file.unlink(missing_ok=True)
        if isinstance(exc, VerificationError):
            raise
        raise VerificationError("recovery file could not be persisted") from exc


def run_disposable_acceptance(
    client: Any,
    *,
    parent_path: str,
    run_token: str,
    approve_create_modify: bool,
    approve_delete: bool,
    recovery_file: Path | None,
) -> list[dict[str, Any]]:
    """Create, edit, verify, and optionally delete one disposable lab.

    Cleanup occurs only after exact preflight absence, successful creation,
    and marker-bearing readback. If ownership becomes ambiguous, the recovery
    record is retained and no delete call is sent.
    """
    if not approve_create_modify:
        raise AuthorizationError("create/modify approval is required")
    if recovery_file is None:
        raise AuthorizationError("a protected recovery file is required")
    if not run_token or not run_token.isalnum():
        raise VerificationError("run token must be non-empty and alphanumeric")

    relative_parent = "/".join(
        segment for segment in parent_path.split("/") if segment
    )
    parent_path = f"/{relative_parent}" if relative_parent else "/"
    folder_name = f"api-check-{run_token}"
    lab_name = f"api-check-{run_token}"
    folder_path = f"{parent_path.rstrip('/')}/{folder_name}"
    lab_path = f"{folder_path}/{lab_name}.unl"
    marker = f"eve-api-acceptance:{run_token}"
    encoded_folder = encode_object_path(folder_path)
    encoded_lab = encode_object_path(lab_path)
    receipts: list[dict[str, Any]] = []

    _write_recovery_record(
        recovery_file,
        folder_path=folder_path,
        lab_path=lab_path,
        marker=marker,
    )

    folder_preflight = client.request("GET", f"/api/folders/{encoded_folder}")
    receipts.append(
        verify_absence(
            "folder_absent_before_create",
            folder_preflight.http_status,
            folder_preflight.payload,
        )
    )
    lab_preflight = client.request("GET", f"/api/labs/{encoded_lab}")
    receipts.append(
        verify_absence(
            "lab_absent_before_create", lab_preflight.http_status, lab_preflight.payload
        )
    )

    folder_create = client.request(
        "POST", "/api/folders", {"path": parent_path, "name": folder_name}
    )
    receipts.append(_success("folder_created", folder_create))
    folder_readback = client.request("GET", f"/api/folders/{encoded_folder}")
    receipts.append(_success("folder_creation_readback", folder_readback))

    lab_create_body = {
        "path": folder_path,
        "name": lab_name,
        "version": "1",
        "author": "Hermes API acceptance",
        "description": marker,
        "body": "Disposable API acceptance lab",
    }
    lab_create = client.request("POST", "/api/labs", lab_create_body)
    receipts.append(_success("lab_created", lab_create))
    lab_readback = client.request("GET", f"/api/labs/{encoded_lab}")
    created_data = _data(lab_readback)
    created_owned = (
        created_data.get("name") == lab_name
        and created_data.get("description") == marker
        and str(created_data.get("version")) == "1"
    )
    if not created_owned:
        raise OwnershipError("created lab marker readback failed")
    receipts.append(_success("lab_creation_readback", lab_readback))

    modified_marker = f"{marker}:modified"
    lab_modify_body = {
        "author": "Hermes API acceptance modified",
        "description": modified_marker,
        "version": "2",
    }
    lab_modify = client.request("PUT", f"/api/labs/{encoded_lab}", lab_modify_body)
    receipts.append(_success("lab_modified", lab_modify))
    modified_readback = client.request("GET", f"/api/labs/{encoded_lab}")
    modified_data = _data(modified_readback)
    modified_owned = (
        modified_data.get("name") == lab_name
        and modified_data.get("description") == modified_marker
        and modified_data.get("author") == "Hermes API acceptance modified"
        and str(modified_data.get("version")) == "2"
    )
    if not modified_owned:
        raise OwnershipError("modified lab marker readback failed")
    receipts.append(_success("lab_modification_readback", modified_readback))

    if not approve_delete:
        return receipts

    lab_delete = client.request("DELETE", f"/api/labs/{encoded_lab}")
    receipts.append(_success("temporary_lab_deleted", lab_delete))
    lab_absent = client.request("GET", f"/api/labs/{encoded_lab}")
    receipts.append(
        verify_absence(
            "lab_absent_after_cleanup", lab_absent.http_status, lab_absent.payload
        )
    )

    folder_delete = client.request("DELETE", f"/api/folders/{encoded_folder}")
    receipts.append(_success("temporary_folder_deleted", folder_delete))
    folder_absent = client.request("GET", f"/api/folders/{encoded_folder}")
    receipts.append(
        verify_absence(
            "folder_absent_after_cleanup",
            folder_absent.http_status,
            folder_absent.payload,
        )
    )
    recovery_file.unlink(missing_ok=True)
    return receipts


class EveApiClient:
    """Cookie-backed JSON client that never includes private values in errors."""

    def __init__(
        self,
        base_url: str,
        *,
        insecure: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        cookie_jar = http.cookiejar.CookieJar()
        handlers: list[Any] = [HTTPCookieProcessor(cookie_jar)]
        if insecure:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            handlers.append(HTTPSHandler(context=context))
        self.opener = build_opener(*handlers)

    def request(
        self, method: str, route: str, body: Mapping[str, Any] | None = None
    ) -> ApiResponse:
        encoded_body = None
        headers = {"Accept": "application/json"}
        if body is not None:
            encoded_body = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{route}",
            data=encoded_body,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = response.status
                raw = response.read()
        except HTTPError as exc:
            status = exc.code
            try:
                raw = exc.read()
            finally:
                exc.close()
        except (URLError, OSError, TimeoutError, HTTPException) as exc:
            raise TransportError("request transport failed") from exc
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VerificationError("response was not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise VerificationError("response JSON was not an object")
        return ApiResponse(status, payload)


def _identity_home(response: ApiResponse) -> str:
    data = _data(response)
    folder = data.get("folder")
    if not isinstance(folder, str) or not folder.strip():
        raise VerificationError("identity did not expose a usable home folder")
    normalized = folder.strip()
    if normalized == "/":
        return "/"
    return "/" + normalized.strip("/")


def run_read_only_acceptance(
    client: EveApiClient, *, home_folder: str
) -> list[dict[str, Any]]:
    """Run a bounded read-only smoke without retaining response payloads."""
    checks = [
        ("appliance_status", "/api/status"),
        ("template_inventory", "/api/list/templates/"),
        ("network_type_inventory", "/api/list/networks"),
        ("role_inventory", "/api/list/roles"),
        ("home_folder_inventory", f"/api/folders/{encode_object_path(home_folder)}"),
    ]
    receipts = []
    for operation, route in checks:
        receipts.append(_success(operation, client.request("GET", route)))
    return receipts


def _emit(receipt: Mapping[str, Any], *, stream: Any = None) -> None:
    if stream is None:
        stream = sys.stdout
    print(json.dumps(receipt, separators=(",", ":"), sort_keys=True), file=stream)


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitized EVE-NG API acceptance checks")
    parser.add_argument("--mode", choices=("read-only", "disposable-lab"), default="read-only")
    parser.add_argument("--approve-create-modify", action="store_true")
    parser.add_argument(
        "--approve-delete-temporary-lab-and-folder", dest="approve_delete", action="store_true"
    )
    parser.add_argument("--recovery-file", type=Path)
    parser.add_argument("--prepare-recovery-directory", type=Path)
    parser.add_argument("--run-token", help=argparse.SUPPRESS)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    if args.prepare_recovery_directory is not None:
        if (
            args.mode != "read-only"
            or args.approve_create_modify
            or args.approve_delete
            or args.recovery_file is not None
            or args.run_token is not None
        ):
            _emit({"error": "invalid_prepare_gate", "verified": False}, stream=sys.stderr)
            return 2
        try:
            prepare_recovery_directory(args.prepare_recovery_directory)
        except VerificationError:
            _emit({"error": "recovery_directory", "verified": False}, stream=sys.stderr)
            return 1
        _emit({"operation": "recovery_directory_prepared", "verified": True})
        return 0
    if args.mode == "disposable-lab":
        if not args.approve_create_modify:
            _emit({"error": "authorization", "verified": False}, stream=sys.stderr)
            return 2
        if args.recovery_file is None:
            _emit({"error": "recovery_file_required", "verified": False}, stream=sys.stderr)
            return 2
    if args.approve_delete and args.mode != "disposable-lab":
        _emit({"error": "invalid_delete_gate", "verified": False}, stream=sys.stderr)
        return 2

    required = ("EVE_BASE_URL", "EVE_USERNAME", "EVE_PASSWORD")
    if any(not os.environ.get(name) for name in required):
        _emit({"error": "missing_environment", "verified": False}, stream=sys.stderr)
        return 2

    client = EveApiClient(
        os.environ["EVE_BASE_URL"], insecure=args.insecure, timeout=args.timeout
    )
    logged_in = False
    recovery_file = args.recovery_file
    try:
        login = client.request(
            "POST",
            "/api/auth/login",
            {
                "username": os.environ["EVE_USERNAME"],
                "password": os.environ["EVE_PASSWORD"],
                "html5": os.environ.get("EVE_HTML5", "0"),
            },
        )
        _emit(_success("login", login))
        logged_in = True

        identity = client.request("GET", "/api/auth")
        home_folder = _identity_home(identity)
        _emit(_success("session_identity", identity))

        if args.mode == "read-only":
            receipts = run_read_only_acceptance(client, home_folder=home_folder)
        else:
            receipts = run_disposable_acceptance(
                client,
                parent_path=home_folder,
                run_token=args.run_token or secrets.token_hex(6),
                approve_create_modify=args.approve_create_modify,
                approve_delete=args.approve_delete,
                recovery_file=recovery_file,
            )
        for receipt in receipts:
            _emit(receipt)
    except AuthorizationError:
        _emit({"error": "authorization", "verified": False}, stream=sys.stderr)
        return 2
    except OwnershipError:
        _emit(
            {
                "error": "ownership",
                "manual_cleanup_required": bool(recovery_file and recovery_file.exists()),
                "verified": False,
            },
            stream=sys.stderr,
        )
        return 1
    except (TransportError, VerificationError):
        _emit(
            {
                "error": "verification",
                "manual_cleanup_required": bool(recovery_file and recovery_file.exists()),
                "verified": False,
            },
            stream=sys.stderr,
        )
        return 1
    except Exception:
        _emit(
            {
                "error": "internal",
                "manual_cleanup_required": bool(recovery_file and recovery_file.exists()),
                "verified": False,
            },
            stream=sys.stderr,
        )
        return 1
    finally:
        if logged_in:
            try:
                logout = client.request("GET", "/api/auth/logout")
                _emit(_success("logout", logout))
            except Exception:
                _emit({"error": "logout", "verified": False}, stream=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
