# CLI, Integrations, and Troubleshooting

## Scope

Load this reference for the NAPALM command-line interface, debug mode, framework integration boundaries, or layered failure diagnosis.

## CLI shape

Invoke through the `terminal` tool:

```text
napalm [options] hostname {configure,call,validate} ...
```

Core options documented by the CLI:

- `--user`, `-u`
- `--password`, `-p`
- `--vendor`, `-v`
- `--optional_args`, `-o`
- `--debug`

Actions:

- `configure` — configuration operation;
- `call` — invoke a NAPALM method;
- `validate` — validate state/configuration through the CLI path.

Use `napalm --help` from the installed version for authoritative current syntax.

## Read-only CLI boundary

The upstream CLI accepts `--password`, but putting a credential in an argument can expose it through shell history and process inspection. Do not publish or run a reusable real-device recipe with a password literal. Prefer the Python API with runtime-injected credentials. If an operator must use the CLI, choose an approved secret-injection wrapper that keeps the value out of command text and logs, then verify the local process model before use.

## Call method

Examples from documentation include:

```text
napalm ... HOSTNAME call get_interfaces
napalm ... HOSTNAME call ping --method-kwargs "destination='<probe-destination>'"
napalm ... HOSTNAME call cli --method-kwargs "commands=['show version']"
```

Method arguments must match the installed base/driver signature.

## Configure dry run

Documented pattern:

```text
napalm ... HOSTNAME configure new_config.txt --strategy merge --dry-run
```

Dry run displays a diff. It does not prove atomicity, rollback, or operational convergence. Configuration execution still requires explicit authorization.

## Debug mode

`--debug` records:

- installed NAPALM packages/versions;
- driver resolution;
- constructor arguments with password masking in the documented tool;
- connection tests;
- method calls and results;
- tracebacks on failure.

Before sharing a debug report, inspect it for:

- hostnames/IPs;
- usernames;
- optional arguments;
- configuration/CLI output;
- topology/state data;
- unmasked backend messages.

Debug mode is evidence collection, not automatic sanitization.

## Integration boundaries

### Ansible

`napalm-ansible` provides modules leveraging NAPALM. Treat it as a separate project/version and preserve NAPALM driver capability gates.

### Salt

Salt includes NAPALM integration in its network automation modules. Salt owns orchestration/event behavior; NAPALM still owns per-device driver semantics.

### StackStorm

The StackStorm NAPALM pack integrates device operations into workflows. Preserve target authorization, diff/rollback, and validation gates.

### Nornir

Nornir is a separate inventory/task/runner framework. `nornir-napalm` connects tasks to NAPALM drivers. Nornir can scale across devices but does not erase per-driver capability, locking, or transaction constraints.

### YANG and logs

The NAPALM docs point to separate `napalm-yang` and `napalm-logs` projects. Their APIs were not part of the core corpus; load their own docs before use.

## Layered diagnosis

1. **Python/package** — supported Python, installed version, dependency import.
2. **Driver resolution** — name/module/plugin and `NetworkDriver` subclass.
3. **Credentials/authorization** — auth failure versus insufficient privilege.
4. **Transport/service** — SSH, NETCONF, eAPI, NX-API, port, TLS/host key.
5. **Backend library** — Netmiko, pyeapi, PyEZ, ncclient, pyIOSXR.
6. **Driver method** — implementation and device-version branch.
7. **Capability** — unsupported/NotImplemented/broken support matrix.
8. **Parser/normalization** — vendor output and expected model.
9. **Transaction** — lock, candidate, compare, commit, pending confirm, rollback.
10. **Orchestration** — concurrency, retry, inventory, sequencing, receipt.

Stop at the first boundary where expected and observed state diverge.

## Exception map

### Import/version

- `ModuleImportError`
- `UnsupportedVersion`

### Connection

- `ConnectionException`
- `ConnectAuthError`
- `ConnectTimeoutError`
- `ConnectionClosedException`

### Configuration/session

- `ReplaceConfigException`
- `MergeConfigException`
- `CommitError`
- `CommitConfirmException`
- `LockError`
- `UnlockError`
- `SessionLockedException`

### Command/template/validation

- `CommandTimeoutException`
- `CommandErrorException`
- `DriverTemplateNotImplemented`
- `TemplateNotImplemented`
- `TemplateRenderException`
- `ValidationException`

Map each to an explicit retry, stop, capability, recovery, or input-fix decision.

## Common symptom matrix

| Symptom | First checks |
|---|---|
| Driver not found | spelling, lookup order, installed community package |
| Authentication failed | credential source, privilege, backend auth method |
| Timeout | service/port/reachability, timeout, device load |
| Getter NotImplemented | live method matrix, driver variant, device release |
| Empty/wrong normalized data | raw backend response, parser template, fixture/regression |
| Merge/replace error | candidate syntax, platform semantics, transfer path |
| Lock error | current owner/session, config-lock options |
| Commit uncertainty | reconnect read-only, pending state, rollback/out-of-band path |
| Validation says pass with skips | inspect `skipped`; critical proof may be incomplete |
| Mock passes, device fails | backend/device behavior was never proven |

## Evidence bundle

```text
NAPALM/Python version:
Driver/module/backend version:
Target OS/version:
Transport/port/security options:
Exact method and sanitized arguments:
Typed exception/traceback:
Support/caveat evidence:
Mock reproduction:
Lab reproduction:
First failing layer:
Next controlled test:
```

## Troubleshooting anti-patterns

- upgrading everything before reproducing;
- switching drivers/transports and methods simultaneously;
- catching exceptions and returning `{}`;
- retrying authentication failures unchanged;
- bypassing locks;
- using raw CLI output as normalized truth;
- sharing debug output without inspection;
- blaming NAPALM when a required device service is disabled;
- blaming the device when a parser fixture is stale.

## Source anchors

- `docs/cli.rst`
- `README.md`
- `napalm/base/clitools/`
- `napalm/base/exceptions.py`
- integration documentation/linked projects
