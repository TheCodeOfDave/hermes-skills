# Unit Testing Nornir Code

Use unit tests to prove orchestration behavior before inventory credentials, transports, or devices enter the test. Build a neutral in-memory inventory, run the real task through Nornir, and assert the complete result tree and state transitions.

The examples in `tests/test_unit_test_harness.py` are executable with the verified Nornir 3.6.0, nornir-napalm 0.6.0, and NAPALM 5.1.0 baseline. The reusable helpers live in `scripts/unit_test_harness.py`.

## What belongs in a unit test

Unit-test these boundaries without network access:

- inventory inheritance and exact target filtering;
- custom task return values and exceptions;
- `AggregatedResult`, per-host `MultiResult`, and leaf `Result` objects;
- nested subtasks;
- changed and failed state;
- failed-host quarantine and deliberate recovery;
- serial and threaded runner equivalence;
- calls into a mocked NAPALM connection;
- connection cleanup.

Reserve a live canary for transport negotiation, authentication, platform-driver support, device semantics, and operational readback. A mocked task proves Python orchestration, not device compatibility.

## Run the executable examples

From the skill directory, using the pinned environment:

```bash
PYTHONDONTWRITEBYTECODE=1 python tests/test_unit_test_harness.py
```

Run all Nornir skill tests explicitly:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p "test_*.py" -v
```

Completion criterion: all tests pass, no test opens a socket, and expected exception cases do not leak uncontrolled traceback output.

## Build a neutral in-memory fixture

`build_test_nornir()` accepts host specifications without reading YAML or obtaining secrets. It defaults to `SerialRunner` and dry-run state so the smallest deterministic path is the default.

```python
from unit_test_harness import build_test_nornir

HOSTS = {
    "node-a": {"platform": "demo", "data": {"role": "edge"}},
    "node-b": {"platform": "demo", "data": {"role": "core"}},
}

nr = build_test_nornir(HOSTS)
```

Do not put production inventory, addresses, usernames, passwords, host keys, or captured configurations in unit fixtures. Use neutral labels and minimal attributes that drive the behavior under test.

## Test one task through Nornir

Test the real task function through `nr.run()` rather than calling it with a hand-built `Task`. Nornir then supplies the host, wraps exceptions, creates result containers, and updates failed-host state exactly as production orchestration does.

```python
from nornir.core.task import Result, Task
from unit_test_harness import assert_clean_run, build_test_nornir


def observe(task: Task) -> Result:
    return Result(
        host=task.host,
        changed=False,
        result=task.host.data["role"],
    )


nr = build_test_nornir(
    {"node-a": {"platform": "demo", "data": {"role": "edge"}}}
)
aggregate = nr.run(task=observe)
assert_clean_run(aggregate, expected_hosts={"node-a"})
assert aggregate["node-a"][0].result == "edge"
```

Assert semantic fields, not only truthiness. A non-empty aggregate can still contain failures, changes, skipped hosts, or nested errors.

## Fail closed on targeting

Filter before running and compare requested and resolved sets. The helper rejects empty selection and missing labels.

```python
from unit_test_harness import build_test_nornir, select_exact_hosts

nr = build_test_nornir(
    {
        "node-a": {"platform": "demo"},
        "node-b": {"platform": "demo"},
    }
)
selected = select_exact_hosts(nr, {"node-b"})
assert set(selected.inventory.hosts) == {"node-b"}
```

Add separate tests for an empty requested set and an absent label. A zero-host run may return without an exception; that is not successful target coverage.

## Inspect every result layer

The shape is:

```text
AggregatedResult
  host label -> MultiResult
    parent Result
    child Result or nested MultiResult
```

`assert_clean_run()` recursively walks every leaf result. For task-specific assertions, index the known parent and child names explicitly.

```python
from nornir.core.task import Result, Task
from unit_test_harness import assert_clean_run, build_test_nornir


def child(task: Task) -> Result:
    return Result(host=task.host, changed=False, result="observed")


def parent(task: Task) -> Result:
    task.run(task=child, name="inspect child")
    return Result(host=task.host, changed=False, result="complete")


nr = build_test_nornir({"node-a": {"platform": "demo"}})
aggregate = nr.run(task=parent)
assert_clean_run(aggregate, expected_hosts={"node-a"})
assert aggregate["node-a"][0].name == "parent"
assert aggregate["node-a"][1].name == "inspect child"
```

Test nested subtasks because a parent result can coexist with a failed or changed child. Human-oriented `print_result()` output is not a machine assertion.

## Test failure, quarantine, and recovery

When `raise_on_error` is false, a failed host enters shared `nr.data.failed_hosts`. Later runs skip that host by default. Test the whole transition; otherwise a workflow can look healthy while silently omitting a device.

```python
from nornir.core.task import Result, Task
from unit_test_harness import build_test_nornir


def maybe_fail(task: Task) -> Result:
    if task.host.data["role"] == "core":
        raise RuntimeError("synthetic task failure")
    return Result(host=task.host, result="ok")


nr = build_test_nornir(
    {
        "node-a": {"data": {"role": "edge"}},
        "node-b": {"data": {"role": "core"}},
    }
)
first = nr.run(task=maybe_fail)
assert first.failed
assert set(first.failed_hosts) == {"node-b"}
assert set(nr.run(task=maybe_fail)) == {"node-a"}
nr.data.reset_failed_hosts()
assert set(nr.run(task=maybe_fail)) == {"node-a", "node-b"}
```

Capture expected error logs in the test framework. Call `reset_failed_hosts()` only after asserting the failure and only when the test intentionally starts a new retry phase.

Also test `on_failed=True, on_good=False` when production code has a failed-host recovery branch.

## Compare `SerialRunner` and `ThreadedRunner`

Use `SerialRunner` for deterministic task semantics. Add a parity test with a bounded `ThreadedRunner` if production will use threads.

```python
from nornir.core.task import Result, Task
from unit_test_harness import assert_clean_run, build_test_nornir


def role(task: Task) -> Result:
    return Result(host=task.host, result=task.host.data["role"])


hosts = {
    "node-a": {"data": {"role": "edge"}},
    "node-b": {"data": {"role": "core"}},
}
observed = {}
for runner in ("serial", "threaded"):
    nr = build_test_nornir(hosts, runner=runner, num_workers=2)
    aggregate = nr.run(task=role)
    assert_clean_run(aggregate, expected_hosts=set(hosts))
    observed[runner] = {
        name: multi[0].result for name, multi in aggregate.items()
    }
assert observed["serial"] == observed["threaded"]
```

Compare host-keyed values rather than iteration order. Thread completion order is not a semantic contract.

## Mock a NAPALM task without hardware

Patch the host connection boundary and run the real `napalm_get` task. This checks getter selection, argument handling, and result normalization while keeping device I/O out of the unit test.

```python
from unittest.mock import MagicMock, patch

from nornir.core.inventory import Host
from nornir_napalm.plugins.tasks import napalm_get
from unit_test_harness import assert_clean_run, build_test_nornir

nr = build_test_nornir({"node-a": {"platform": "demo"}})
device = MagicMock()
device.get_facts.return_value = {
    "hostname": "node-a",
    "vendor": "Example",
}

with patch.object(
    Host,
    "get_connection",
    autospec=True,
    return_value=device,
) as get_connection:
    aggregate = nr.run(task=napalm_get, getters=["facts"])

assert_clean_run(aggregate, expected_hosts={"node-a"})
assert aggregate["node-a"][0].result["facts"]["vendor"] == "Example"
get_connection.assert_called_once()
device.get_facts.assert_called_once_with()
```

This is a mocked NAPALM connection, not a mocked Nornir result. Keeping the real Nornir and task layers avoids tests that merely restate a fabricated return object.

For NAPALM driver behavior, use NAPALM's `mock` platform and recorded method fixtures as a separate driver-level test. Keep those fixtures synthetic and review them as repository content. The official nornir-napalm tests use that pattern for getters and configuration transactions.

## Verify cleanup

Use Nornir as a context manager in production and test that cleanup includes hosts already marked failed. `Nornir.__exit__()` calls `close_connections(on_good=True, on_failed=True)`.

```python
from unittest.mock import patch

from nornir.core.inventory import Host
from unit_test_harness import build_test_nornir

nr = build_test_nornir(
    {
        "node-a": {"platform": "demo"},
        "node-b": {"platform": "demo"},
    }
)
with patch.object(Host, "close_connections", autospec=True) as close:
    with nr:
        pass
assert close.call_count == 2
```

If production code opens a separate console, jump channel, temporary file, or vendor session inside a task, inject that dependency and assert its `close()` call in the task's own `finally` branch. Nornir can close only registered host connections; it cannot clean up resources hidden from its connection registry.

## Test changed, failed, and exception branches

At minimum, cover:

1. successful unchanged result;
2. successful expected change when the task is authorized to change state;
3. explicit `failed=True` result;
4. raised exception wrapped by Nornir;
5. one-host failure with other hosts successful;
6. failed host skipped on the next default run;
7. reset or `on_failed` recovery;
8. changed or failed nested child;
9. exact-target mismatch;
10. cleanup after both success and failure.

For read-only code, `assert_clean_run()` rejects any `changed=True` leaf. For authorized change tests, pass `allow_changed=True`, then assert the exact hosts and task names that were expected to change. Do not globally ignore the changed flag.

## Test isolation rules

- Create a fresh Nornir object per test unless shared-state behavior is the subject.
- If a fixture is shared, reset `dry_run` and `failed_hosts` before every test.
- Never let unit tests read the operator's environment, SSH configuration, credential store, or live inventory.
- Patch at the connection boundary, not at `nr.run()` or the final result object.
- Do not assert thread completion order.
- Suppress bytecode when validating distributable skill trees.
- Keep unit, mock-driver, offline canary, and live acceptance receipts separate.

## Verification checklist

- [ ] Fixture uses only neutral in-memory inventory.
- [ ] Exact requested and resolved host sets are asserted.
- [ ] The real task runs through `nr.run()`.
- [ ] Aggregate, host, and nested results are inspected.
- [ ] Success, changed, failed, exception, and partial-result paths are covered.
- [ ] Failed-host skip and explicit recovery behavior are covered.
- [ ] Serial behavior is tested before threaded parity.
- [ ] External connections are mocked at their boundary.
- [ ] Cleanup includes good and failed hosts.
- [ ] No unit test requires a device, route, credential, or private fixture.
- [ ] A separate live canary verifies transport and platform semantics before production use.

## Official sources

- Nornir 3.6.0, Tasks: <https://nornir.readthedocs.io/en/latest/tutorial/tasks.html>
- Nornir 3.6.0, Processing results: <https://nornir.readthedocs.io/en/latest/tutorial/task_results.html>
- Nornir 3.6.0, Failed Tasks: <https://nornir.readthedocs.io/en/latest/tutorial/failed_tasks.html>
- Nornir source tests for task, subtask, failure, skip, and reset behavior: <https://github.com/nornir-automation/nornir/blob/main/tests/core/test_tasks.py>
- nornir-napalm test fixture and reset pattern: <https://github.com/nornir-automation/nornir_napalm/blob/main/tests/conftest.py>
- nornir-napalm mock getter tests: <https://github.com/nornir-automation/nornir_napalm/blob/main/tests/unit/test_napalm_get.py>
