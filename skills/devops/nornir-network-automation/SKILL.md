---
name: nornir-network-automation
description: Use when orchestrating network automation with Nornir. Applies exact inventory scoping, runtime-only credentials, bounded concurrency, explicit result inspection, and read-only-first validation.
version: 1.1.0
author: Hermes Skills Contributors
license: MIT
metadata:
  hermes:
    tags: [nornir, network-automation, inventory, napalm, safety]
    related_skills: []
---

# Nornir Network Automation

## Overview

Use Nornir as an orchestration framework for inventory, filtering, task execution, concurrency, connection lifecycle, and structured results. Nornir does not provide network drivers by itself. Select a task plugin such as NAPALM, Netmiko, or Scrapli according to the required device operation and transport.

The default path is a narrow read-only canary: resolve an explicit inventory, inject credentials at runtime, filter exact targets, run one normalized getter, inspect every host and subtask result, close connections, and save sanitized evidence. Configuration work is a separate authorization branch.

Official references:

- <https://nornir.readthedocs.io/en/latest/>
- <https://github.com/nornir-automation/nornir>
- <https://nornir.readthedocs.io/en/latest/plugins/index.html>

## When to Use

Use this skill for:

- building or reviewing Nornir inventory and filtering;
- running read-only collection across multiple network devices;
- integrating Nornir with NAPALM, Netmiko, Scrapli, or another connection plugin;
- writing network-free unit tests for Nornir tasks and result handling;
- choosing serial versus bounded threaded execution;
- inspecting `AggregatedResult`, `MultiResult`, and `Result` failures;
- diagnosing skipped hosts, connection lifecycle, or plugin compatibility;
- turning a proven one-device operation into a controlled fleet workflow.

Use a device-library-specific procedure without Nornir when only one device and one operation are involved. Use a workflow engine around Nornir when durable scheduling, approvals, retries, or cross-system state transitions are the primary problem.

## Safety Contract

1. **Exact scope.** Convert requested targets into an explicit label set, filter the inventory, and assert the resolved set before opening a connection.
2. **Runtime-only credentials.** Obtain secrets through a protected environment or secret-execution mechanism. Keep passwords, tokens, private keys, and session material out of inventory, source, command arguments, evidence, and logs.
3. **Strict transport verification.** Preserve SSH host-key and TLS verification. A private-lab exception must be explicit, appliance-scoped, and absent from reusable defaults.
4. **Read-only first.** Prove inventory, transport, driver, getter, result handling, and cleanup before any configuration task.
5. **Bounded concurrency.** Start serially or with a small worker count. Increase only after representative devices pass and the control plane can sustain the load.
6. **No implicit success.** Inspect the aggregate, every host `MultiResult`, and every subtask. A top-level return value alone is not acceptance evidence.
7. **Explicit side effects.** Configuration methods require an authorized target and content, a reviewed diff, a rollback path, and post-change readback.
8. **Sanitized receipts.** Persist labels, plugin/package versions, methods, counts, changed/failed states, and timestamps. Redact device identities and omit credentials and private topology.

## Execution Model

```text
Inventory
  → exact filter
  → runner schedules tasks
  → task plugin opens connection
  → Result per subtask
  → MultiResult per host
  → AggregatedResult for the run
  → explicit failure inspection
  → connection cleanup
  → sanitized evidence
```

Nornir separates orchestration from device behavior:

- **Core:** inventory, filters, runners, processors, tasks, and results.
- **Inventory plugin:** loads hosts, groups, defaults, and connection options.
- **Task plugin:** implements the operation.
- **Connection plugin:** owns transport setup and teardown.
- **Runner:** controls scheduling, not semantic safety.
- **Processor:** observes task lifecycle for logging, telemetry, or policy.

A threaded runner can make a bad task fail faster across more devices. Concurrency is not a safety boundary.

## Procedure

### 1. Define the run contract

Record:

- purpose and allowed operation class;
- exact target labels and expected count;
- inventory source;
- task and connection plugins;
- supported platforms and device versions;
- runner and worker limit;
- timeout and failure policy;
- expected evidence fields;
- connection cleanup and rollback behavior.

Completion criterion: target count, allowed methods, and success conditions are explicit before initialization.

### 2. Create an isolated environment

Pin a tested combination of Nornir and each external plugin. Do not assume independent latest versions are compatible.

```bash
python -m venv .venv
.venv/bin/python -m pip install "nornir==3.6.0" "nornir-napalm==0.6.0" "napalm==5.1.0"
```

On Windows, invoke `.venv/Scripts/python.exe` instead. The versions above are a verified baseline, not a claim that they are the newest releases.

Completion criterion: the interpreter imports Nornir and every selected plugin and prints the expected installed versions.

### 2a. Unit-test task behavior offline

Before using inventory credentials or opening a transport, run custom tasks against neutral in-memory inventory. Test exact filtering, every result layer, nested subtasks, failed-host state, runner parity, mocked connection boundaries, and cleanup.

Load `references/unit-testing-nornir.md` for the reusable harness, executable examples, and the boundary between unit, mock-driver, offline-canary, and live tests.

Completion criterion: the executable unit examples pass without network access, private fixtures, credentials, or uncontrolled tracebacks.

### 3. Load inventory without secrets

Prefer `SimpleInventory` for a small file-backed deployment and a purpose-built inventory plugin for a source of truth. Use groups for shared platform and connection options; use defaults only for genuinely universal values.

Keep credential fields absent from reusable inventory. After `InitNornir`, inject runtime values only into the selected hosts. Load `references/inventory-filtering-and-secrets.md` for the inventory template and exact-filter pattern.

Completion criterion: inventory serialization contains no credential values, and the resolved host set equals the requested labels.

### 4. Select a runner deliberately

Use the serial runner while establishing behavior or when devices share a constrained console, jump path, API session, or lab resource. Use the threaded runner for independent I/O-bound operations after a representative canary passes.

For the built-in Nornir 3 runner, use the registered plugin identifier rather than the class name:

```yaml
runner:
  plugin: serial
```

Set an explicit worker count. Treat connection limits, authentication throttles, shared jump hosts, device CPU, and output sinks as capacity constraints.

Completion criterion: the chosen runner has a stated capacity reason and an explicit maximum concurrency.

### 5. Run one read-only canary

Use one representative target and one normalized getter. For NAPALM, `napalm_get(getters=["facts"])` is the preferred first task because it proves driver selection, authentication, transport, normalization, and result handling without requesting configuration.

Load `references/napalm-read-only-canary.md` for the complete reusable pattern.

Completion criterion: the canary returns `failed=false`, every subtask is inspected, and every read-only result reports `changed=false`.

### 6. Expand in bounded batches

Add one platform or failure domain at a time. Keep exact labels and assert both requested and resolved counts. Do not silently continue when a target is missing, duplicated, or unexpectedly filtered out.

Nornir marks failed hosts in `data.failed_hosts`; later tasks skip them by default. Inspect that state before every follow-on task. Use `reset_failed_hosts()` only after diagnosing and deliberately accepting the retry.

Completion criterion: every requested label appears exactly once in the result or has an explicit pre-execution rejection.

### 7. Inspect the full result tree

For every host:

1. inspect `MultiResult.failed`;
2. iterate all child `Result` objects;
3. capture task name, `failed`, `changed`, exception type, and sanitized result metadata;
4. reject any unexpected child task or configuration change;
5. reconcile totals programmatically.

`print_result` is for humans, not machine acceptance. Build evidence from result objects.

Completion criterion: declared target, success, failure, and changed totals equal the enumerated records.

### 8. Close connections and write evidence

Prefer `with InitNornir(...) as nr:` so registered connections close on exit. If the plugin or workflow cannot use the context manager, call `nr.close_connections()` in `finally`.

Evidence should contain:

- UTC timestamp;
- neutral target label;
- package and plugin versions;
- task/getter names;
- `failed` and `changed` state;
- sanitized platform facts needed for the decision;
- explicit skipped or unsupported capability state.

Completion criterion: connections are closed, temporary files are removed, and the evidence contains no credentials or environment-specific identifiers.

### 9. Gate configuration work separately

Do not infer configuration approval from a successful read-only run. For an authorized configuration task:

1. narrow to exact targets again;
2. render and preserve intended configuration separately from execution;
3. obtain a device-native or plugin-supported diff;
4. reject empty, broad, or unexplained diffs;
5. apply to one canary with a tested rollback path;
6. read operational state back;
7. expand only after the canary converges.

Completion criterion: each changed target has an authorized diff, verified postcondition, and tested recovery path.

## Failure Classification

Classify the first failing layer:

| Layer | Typical evidence | Response |
|---|---|---|
| Inventory | missing label, duplicate source record, inheritance surprise | Stop before connection; correct scope. |
| Filter | requested and resolved sets differ | Reject the run; never broaden implicitly. |
| Package/plugin | import or registration failure | Reconcile pinned compatibility. |
| Transport | route, host key, TLS, timeout | Preserve strict verification; fix trust or reachability. |
| Authentication | rejected protected credential | Stop; do not print or persist the value. |
| Driver/platform | unsupported OS, version, or getter | Record capability failure; choose a supported plugin. |
| Task | typed exception or malformed result | Inspect the host and child result. |
| Runner/capacity | correlated timeouts or resource exhaustion | Reduce concurrency or serialize failure domains. |
| Evidence | totals disagree or sensitive fields appear | Reject acceptance and regenerate sanitized output. |

A running VM, reachable TCP port, successful login, completed task, and semantically valid result are separate states. Verify the layer the claim actually depends on.

## Included Offline Check

Run the bundled no-network canary after installation or skill changes:

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/offline_canary.py
```

It creates an in-memory neutral inventory, filters two exact labels, executes a bounded threaded custom task, inspects aggregate and child results, asserts zero changes and failures, closes connections, and emits only counts. It proves Nornir orchestration behavior, not device transport or driver support.

Run deterministic skill validation:

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/validate_skill.py
```

Run the executable Nornir unit-testing examples:

```bash
PYTHONDONTWRITEBYTECODE=1 python tests/test_unit_test_harness.py
```

## Common Pitfalls

1. **Treating Nornir as a driver.** Install and validate the task/connection plugin separately.
2. **Filtering without asserting.** A typo can produce an empty successful-looking run. Compare requested and resolved sets.
3. **Credentials in YAML.** Inject after initialization from a protected runtime source.
4. **Silent trust weakening.** Fix host-key or CA trust rather than disabling verification in reusable configuration.
5. **Unbounded threads.** Start small and measure the constrained control plane.
6. **Top-level-only inspection.** A host can contain several child results; inspect all of them.
7. **Ignoring failed-host state.** Later tasks skip failed hosts unless deliberately reset.
8. **Shared output races.** Aggregate in memory or use a concurrency-safe processor/sink.
9. **Raw CLI as the default.** Prefer normalized getters; label CLI output as vendor-specific.
10. **Retrying writes blindly.** A timeout can hide a completed change. Read back before any retry.
11. **Calling mock success live validation.** Offline checks prove orchestration only.
12. **Mixing evidence and secrets.** Redact before serialization, not after publishing.
13. **Pre-opening serial jump channels.** Open a fresh channel inside each host task and close it before the next host; idle unauthenticated channels can age out as EOF failures.
14. **Prompt detection on asynchronous commands.** Route explicitly authorized debug/clear commands through a timing-aware backend path and always run the matching cleanup command.

## Verification Checklist

- [ ] Purpose, operation class, exact labels, and expected count recorded.
- [ ] Nornir and plugin versions pinned and import-tested.
- [ ] Custom tasks passed the network-free unit tests in `references/unit-testing-nornir.md`.
- [ ] Inventory contains no credentials.
- [ ] Requested and resolved host sets match exactly.
- [ ] Runner and worker count are explicit and capacity-justified.
- [ ] SSH host-key and TLS verification remain strict.
- [ ] One representative read-only canary passed first.
- [ ] Every host and child result was inspected.
- [ ] Failed-host state was reconciled before follow-on tasks.
- [ ] Declared totals equal enumerated records.
- [ ] Every accepted result has `failed=false` and expected `changed` state.
- [ ] Connections and temporary artifacts were cleaned up.
- [ ] Saved evidence is sanitized and reproducible without credentials.
- [ ] Configuration work, if any, had separate authorization, diff, canary, rollback, and readback.
- [ ] Unit examples, `scripts/offline_canary.py`, and `scripts/validate_skill.py` passed without network access.
