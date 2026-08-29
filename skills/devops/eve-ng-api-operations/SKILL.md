---
name: eve-ng-api-operations
description: Use when operating or troubleshooting EVE-NG through its HTTP API. Applies discovery-first calls, session-safe authentication, explicit side-effect gates, and exact readback verification.
version: 1.0.0
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
umask 077
EVE_BASE_URL='<scheme>://<eve-ng-host>'
EVE_COOKIE="$(mktemp)"
PYTHON="${PYTHON:-python3}"
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
| `fail` | Other 40x request/target problem | Correct path, method, or payload from live evidence. |
| `error` | 50x server failure | Preserve response and inspect appliance health/logs. |

Do not accept HTTP 200 alone. Require the JSON status and operation-specific postcondition.

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

## Verification Checklist

- [ ] Appliance, edition, and base URL resolved.
- [ ] Credentials came from a protected source and were not printed.
- [ ] Cookie jar permissions are private.
- [ ] Authenticated identity matches the intended user.
- [ ] Live templates, images, networks, roles, and object IDs were discovered as needed.
- [ ] Lab paths were segment-encoded and metadata-checked.
- [ ] Side-effect class and approval boundary were satisfied.
- [ ] The narrowest applicable endpoint was used.
- [ ] JSend result and exact postcondition both passed.
- [ ] Destructive operations preserved required pre-change evidence.
- [ ] Logout was attempted and local cookie residue removed.
- [ ] Saved artifacts contain no credentials, cookies, private endpoints, or environment fingerprints.

For the endpoint catalog, load `references/api-endpoints.md` only when selecting a route.
