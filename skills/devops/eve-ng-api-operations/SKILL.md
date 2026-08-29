---
name: eve-ng-api-operations
description: Use when operating or troubleshooting EVE-NG through its HTTP API. Applies discovery-first calls, session-safe authentication, explicit side-effect gates, and exact readback verification.
version: 1.0.1
author: Hermes Skills Contributors
license: MIT
metadata:
  hermes:
    tags: [eve-ng, api, network-labs, automation]
    related_skills: []
---

# EVE-NG API Operations

## Overview

Operate EVE-NG Community or Professional through the appliance's `/api/...` endpoints. Use a discovery-first sequence: authenticate, confirm identity, inspect system and lab state, then make the smallest authorized change and read the exact target back.

The official API page warns that some request documentation lags the product. Treat live `GET` responses and the Web UI's network calls as the parameter authority for the installed version.

Official reference: <https://www.eve-ng.net/index.php/how-to-eve-ng-api/>

## When to Use

Use this skill for:

- authentication and session troubleshooting;
- inventorying folders, labs, templates, images, networks, nodes, interfaces, and topology;
- starting, stopping, exporting, or wiping nodes;
- creating or editing labs, folders, networks, nodes, or users;
- diagnosing JSend responses such as `unauthorized`, `forbidden`, `fail`, or `error`.

Use SSH or the Web UI instead when the required operation has no verified API route, the live appliance disagrees with the documented request shape, or an interactive console is the actual task.

## Safety Boundary

Classify the requested operation before sending it:

| Class | Examples | Required behavior |
|---|---|---|
| Read-only | status, auth identity, templates, folders, labs, nodes, topology | Execute after resolving the exact appliance and target. |
| Operational side effect | start, stop, export, create, edit, move | Confirm the target and requested effect are explicit; read back the affected resource. |
| Destructive | wipe nodes, delete labs/folders/users, overwrite durable state | Require explicit approval naming the target and action; capture useful pre-change state; verify the result. |
| Security-sensitive | users, roles, permissions, authentication, TLS policy | Explain the boundary and obtain explicit approval before changing it. |

A node wipe removes user state such as startup configuration and VLAN data. Export first when preservation is required, but do not imply that an export is a complete appliance backup.

## Prerequisites

Resolve these values without printing secret contents:

- `EVE_BASE_URL`, including scheme and optional port;
- edition: Community or Professional;
- `EVE_USERNAME` and `EVE_PASSWORD`, supplied through a secret manager or protected process environment;
- a private cookie-jar path;
- the exact lab path and node IDs for targeted operations.

Recommended shell setup:

```bash
select_python() {
  if [ -n "${PYTHON:-}" ]; then
    if "$PYTHON" -c 'raise SystemExit(0)' >/dev/null 2>&1; then
      export PYTHON
      return 0
    fi
    printf '%s\n' 'Configured PYTHON cannot execute.' >&2
    return 1
  fi

  for candidate in python3 python; do
    if "$candidate" -c 'raise SystemExit(0)' >/dev/null 2>&1; then
      PYTHON="$candidate"
      export PYTHON
      return 0
    fi
  done

  printf '%s\n' 'No executable Python interpreter was found.' >&2
  return 1
}

select_python || exit 1
```

An explicit `PYTHON` value is authoritative and must execute successfully; it is not silently replaced. Without an override, the probe tries `python3` and then `python`. This execution test avoids command aliases that resolve but cannot run.

Create the remaining private shell state only after interpreter selection succeeds:

```bash
umask 077
EVE_BASE_URL='<scheme>://<eve-ng-host>'
EVE_COOKIE="$(mktemp)"
```

Use `https://` for Professional. If the appliance uses a private CA, trust that CA where practical. Use `curl --insecure` only when the user accepts the certificate-validation tradeoff for the named appliance; never make insecure TLS the silent default.

## Session-Safe Authentication

EVE-NG allows one active location per user. A second login can invalidate the first session. Prefer a dedicated automation account where supported, and avoid repeatedly logging in during one workflow.

Assume credentials are already injected into `EVE_USERNAME` and `EVE_PASSWORD`. Build the login body without placing the password in shell history or curl's argument list:

```bash
"$PYTHON" -c 'import json,os; print(json.dumps({"username":os.environ["EVE_USERNAME"],"password":os.environ["EVE_PASSWORD"]}))' \
  | curl --silent --show-error \
      --cookie "$EVE_COOKIE" --cookie-jar "$EVE_COOKIE" \
      --header 'Content-Type: application/json' \
      --request POST --data-binary @- \
      "$EVE_BASE_URL/api/auth/login"
```

For Professional installations that require the documented HTML5 selector, include `"html5":"0"` in the generated JSON. Add `--insecure` only under the explicit TLS exception above.

A successful response normally contains:

```json
{"code":200,"status":"success"}
```

Immediately confirm the session identity:

```bash
curl --silent --show-error \
  --cookie "$EVE_COOKIE" --cookie-jar "$EVE_COOKIE" \
  --header 'Content-Type: application/json' \
  "$EVE_BASE_URL/api/auth"
```

Completion criterion: the response is successful and identifies the intended automation user without exposing the cookie or credential values.

## Discovery-First Workflow

### 1. Check appliance status

```bash
curl --silent --show-error \
  --cookie "$EVE_COOKIE" --cookie-jar "$EVE_COOKIE" \
  --header 'Content-Type: application/json' \
  "$EVE_BASE_URL/api/status"
```

Completion criterion: HTTP and JSON status indicate success, and the response is from the intended appliance.

### 2. Discover supported object types

```bash
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/list/templates/"
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/list/networks"
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/list/roles"
```

Inspect a chosen template before creating a node:

```bash
TEMPLATE='<template>'
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/list/templates/$TEMPLATE"
```

Completion criterion: every type, image, and required option in a planned write comes from the live response rather than an assumed default.

### 3. Resolve and encode the target path

EVE-NG lab routes use URL paths such as `/api/labs/<path>.unl`. Encode every path segment. Do not encode the whole endpoint string in one pass because that also escapes `/` separators.

Portable segment encoding:

```bash
EVE_LAB_PATH='<folder>/<lab>.unl'
LAB_ROUTE="$("$PYTHON" -c 'import sys,urllib.parse; print("/".join(urllib.parse.quote(x,safe="") for x in sys.argv[1].split("/")))' "$EVE_LAB_PATH")"
```

Completion criterion: the encoded route points to one exact lab, confirmed by a successful lab metadata `GET`.

### 4. Inspect the lab before acting

```bash
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/labs/$LAB_ROUTE"
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/labs/$LAB_ROUTE/networks"
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/labs/$LAB_ROUTE/nodes"
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/labs/$LAB_ROUTE/topology"
```

Completion criterion: the lab name/path and every targeted node ID match the user's request.

### 5. Apply the narrowest authorized operation

Start or stop one node rather than all nodes when a node ID was specified:

```bash
NODE_ID='<node-id>'
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/labs/$LAB_ROUTE/nodes/$NODE_ID/start"
```

Export one node before an approved wipe when its startup state must be preserved:

```bash
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/labs/$LAB_ROUTE/nodes/$NODE_ID/export"
```

Do not send a wipe or delete request merely because it appears in an example. The safety boundary must already be satisfied.

### 6. Verify the exact target

After any write or operational action:

1. require the API response to indicate success;
2. `GET` the affected lab, node, network, folder, or user;
3. compare the observed state with the requested state;
4. report partial or ambiguous results as incomplete rather than successful.

For node actions, read the node and lab node collection when the installed version exposes state there:

```bash
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/labs/$LAB_ROUTE/nodes/$NODE_ID"
curl --silent --show-error --cookie "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/labs/$LAB_ROUTE/nodes"
```

Completion criterion: readback identifies the same object and proves the intended postcondition.

### 7. Logout and remove session residue

```bash
curl --silent --show-error \
  --cookie "$EVE_COOKIE" --cookie-jar "$EVE_COOKIE" \
  "$EVE_BASE_URL/api/auth/logout"
rm -f -- "$EVE_COOKIE"
```

Deleting this temporary cookie jar is routine credential cleanup, not deletion of user data. If the process fails before logout, remove the local cookie jar and report that server-side session state may remain until timeout.

## JSend Interpretation

EVE-NG responses use fields such as `code`, `message`, `status`, and sometimes `data`.

| Status | Typical meaning | Response |
|---|---|---|
| `success` | 20x operation completed | Verify the specific postcondition. |
| `unauthorized` + 400 | Session timed out | Re-authenticate once, then retry the read. |
| `unauthorized` + 401 | Login required | Check cookie-jar continuity and identity. |
| `forbidden` + 403 | Insufficient role/privilege | Stop; do not work around permissions. |
| `fail` | Common 40x request/target problem | Correct path, method, or payload from live evidence; some missing-object responses omit `status`. |
| `error` | 50x server failure | Preserve response and inspect appliance health/logs. |

Normalize `code` before comparing it because installed endpoints can return either a number such as `200` or a digit string such as `"200"`. Reject booleans and unrelated strings, then compare the normalized string with the HTTP status.

Do not accept HTTP 200 alone. Require transport success, the expected HTTP status, the expected JSend status when that status is part of the endpoint contract, and the operation-specific postcondition.

For cleanup, an exact HTTP `404` can prove absence whether JSend `status` is `fail` or omitted, but only when all of these are true: the exact target was absent before creation, creation and marker-bearing readback proved ownership, deletion succeeded, and the readback used the same unambiguous segment-encoded path.

## Reusable Acceptance Runner

Run the repository helper from this skill directory. It uses an in-memory cookie jar, validates transport/HTTP/JSend/postcondition layers, records transport code `0` only after the Python HTTP transport completes, normalizes numeric and string JSend codes, and emits payload-free JSON receipts. It never prints the base URL, credentials, cookies, home folder, generated target names, or API payloads.

Protected environment variables:

- `EVE_BASE_URL`
- `EVE_USERNAME`
- `EVE_PASSWORD`
- optional `EVE_HTML5`, default `0`

Read-only smoke:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" scripts/eve_api_acceptance.py \
  --mode read-only
```

This authenticates once, confirms session identity, checks appliance status, inventories templates, network types, roles, and the authenticated home folder, then logs out. A second login can invalidate an existing Web UI session for the same account, so confirm that session impact before authenticated testing.

### Disposable create/edit acceptance

Use this branch only after explicit approval to create and modify one generated empty lab. Choose the cleanup flag only after separate explicit approval to delete that temporary lab and its temporary parent folder.

```bash
RECOVERY_ROOT="${TEMP:-${TMPDIR:-}}"
if [ -z "$RECOVERY_ROOT" ]; then
  printf '%s\n' 'TEMP or TMPDIR is required for recovery data' >&2
  exit 1
fi
RECOVERY_DIR="$RECOVERY_ROOT/eve-recovery-$("$PYTHON" -c 'import secrets; print(secrets.token_hex(8))')"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" scripts/eve_api_acceptance.py \
  --prepare-recovery-directory "$RECOVERY_DIR"
RECOVERY_FILE="$RECOVERY_DIR/targets.json"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" scripts/eve_api_acceptance.py \
  --mode disposable-lab \
  --approve-create-modify \
  --approve-delete-temporary-lab-and-folder \
  --recovery-file "$RECOVERY_FILE"
if [ ! -e "$RECOVERY_FILE" ]; then
  rmdir "$RECOVERY_DIR"
fi
```

The preparation mode creates a new directory and emits only a sanitized receipt. It fails if the path already exists. On POSIX it enforces mode `0700`; on Windows it removes ACL inheritance, removes every non-allowlisted grant, grants only the current user, SYSTEM, and Administrators, and verifies the resulting owner and allow ACEs by SID. The mutation runner re-verifies the parent before creating the recovery file, then applies and verifies the same Windows boundary on the file before writing target names. Missing PowerShell, `icacls`, untranslatable identities, or any unexpected allow ACE fail closed before the first API mutation; authentication calls may precede the mutation-runner check when preparation is skipped.

The runner performs this exact sequence:

1. Generate collision-resistant folder, lab, and ownership-marker values.
2. Exclusively create and durably flush the recovery file before any API mutation. The path must not already exist. On POSIX, the runner enforces an owner-only parent and fsyncs both file and parent directory. On Windows, the preparation mode and mutation runner enforce and verify exact native ACLs on the parent and file; unavailable ACL tooling fails closed. Values never go to standard output.
3. Prove the exact folder and lab paths return `404` before creation.
4. Create a dedicated folder and empty lab.
5. Read back name, marker, and version before claiming ownership.
6. Modify only harmless lab metadata and verify the changed marker, author, and version while the name stays stable.
7. If deletion was explicitly approved, delete the lab, prove exact `404` absence, then delete the folder and prove exact `404` absence.
8. Remove the recovery file only after complete cleanup; always attempt logout.

If ownership or cleanup becomes ambiguous, the runner sends no further delete request, retains the recovery file for manual review, and emits only a sanitized failure classification. Do not delete by name pattern. If deletion was not approved, omit `--approve-delete-temporary-lab-and-folder`; the generated objects and recovery file are intentionally retained.

Default TLS verification remains enabled. Pass `--insecure` only under the explicit, appliance-scoped exception described in Prerequisites.

### Deterministic repository validation

Run before live testing and after every skill edit:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" scripts/validate_skill.py
```

The validator checks frontmatter and version, the linked endpoint catalog, 42 unique method/route entries, every Bash fence through raw-byte `bash -n`, Python syntax, generated caches, environment-neutral text patterns, controlled interpreter fallback behavior, and synthetic unit/integration fixtures. This deterministic gate supplements rather than replaces the repository-wide privacy scanner and independent review.

## API Drift Procedure

When a documented payload fails or the installed version exposes different fields:

1. Run the closest read-only `GET` for the object and record its field names.
2. Reproduce the intended action manually in the Web UI only if the user authorized that action.
3. Inspect the browser network request: method, URL, content type, and payload shape.
4. Generalize only the required fields; remove cookies, credentials, hostnames, lab names, IDs, and other environment data from saved examples.
5. Retry against a disposable or non-production lab when available.
6. Read back the exact target and document the version-specific difference.

Completion criterion: the adapted request is grounded in the live installed version and contains no captured private values.

## Common Pitfalls

1. **Session collision.** Repeated login attempts invalidate another session for the same user. Reuse one cookie jar and authenticate once per workflow.
2. **TLS shortcuts.** Copying `-k` into every command hides certificate failures. Prefer trusted certificates; make any exception explicit and scoped.
3. **Unencoded paths.** Spaces and special characters break routes. Encode segments and verify lab metadata before acting.
4. **Assumed templates.** Template names, images, and options vary. Discover them from the appliance before node creation.
5. **Broad node actions.** Collection routes can affect every node. Use a node-specific route when the request names one node.
6. **Weak success checks.** HTTP success or a JSend `success` string does not prove state. Read the resource back.
7. **Credential leakage.** Passwords in command arguments, pasted cookies, and verbose curl traces can enter logs. Inject secrets through protected environment variables and keep tracing off.
8. **Premature destructive calls.** Wipe and delete routes are not diagnostics. Confirm exact authorization and preserve required state first.
9. **Assumed JSend envelopes.** A missing object may return `status: fail` or omit `status`. Verify exact HTTP status and ownership context rather than inventing a universal envelope.
10. **Pattern-based test cleanup.** A generated-looking name is not proof of ownership. Require preflight absence plus marker-bearing readback, and retain ambiguous objects for manual review.

## Verification Checklist

- [ ] Appliance, edition, and base URL resolved.
- [ ] Credentials came from a protected source and were not printed.
- [ ] Cookie jar permissions are private.
- [ ] Authenticated identity matches the intended user.
- [ ] Live templates, images, networks, roles, and object IDs were discovered as needed.
- [ ] Lab paths were segment-encoded and metadata-checked.
- [ ] Side-effect class and approval boundary were satisfied.
- [ ] The narrowest applicable endpoint was used.
- [ ] Transport, HTTP, normalized JSend code/status, and exact postcondition passed.
- [ ] Destructive operations preserved required pre-change evidence.
- [ ] Disposable cleanup was ownership-gated and verified lab absence before folder deletion.
- [ ] Logout was attempted and local cookie residue removed.
- [ ] Saved artifacts contain no credentials, cookies, private endpoints, or environment fingerprints.
- [ ] `scripts/validate_skill.py` passed without generating caches.

For the endpoint catalog, load `references/api-endpoints.md` only when selecting a route.
