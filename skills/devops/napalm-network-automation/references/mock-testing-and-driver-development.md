# Mock Testing and Driver Development

## Scope

Load this reference when testing NAPALM automation without hardware, modeling sequential responses/errors, using the shared getter suite, testing against a real device, or evaluating a community driver.

## Mock driver

Resolve it through the normal API:

```python
import napalm

driver = napalm.get_network_driver("mock")
device = driver(
    hostname="foo",
    username="user",
    password="pass",
    optional_args={"path": path_to_results},
)
device.open()
```

`path` defaults to the current directory. The hostname and credentials are inert test values for the mock driver; never reuse real secrets in fixtures.

## Per-method call-sequenced fixtures

The NAPALM 5.2.0 mock implementation loads getter, ping, and traceroute fixtures by method name and that method's own invocation count.

- First `get_interfaces()` result: `get_interfaces.1`.
- A second `get_interfaces()` call uses `get_interfaces.2`.
- The first `get_interfaces_ip()` call independently uses `get_interfaces_ip.1`.
- `open()` does not increment those per-method counters in current source.

Fixture content is JSON matching the normalized method result.

The published mock-driver tutorial describes one global post-`open()` call stack and therefore shows a different second method using suffix `.2`. Current 5.2.0 source uses a dictionary keyed by method name. Pin the NAPALM version and test the installed implementation rather than copying that stale cross-method example.

Missing fixture behavior is intentional: the mock driver raises `NotImplementedError` and names the file that can be supplied.

## CLI fixtures

For:

```python
device.cli(["show interface Ethernet 1/1", "show interface Ethernet 1/2"])
```

The fixture name includes:

- `cli`;
- call sequence;
- sanitized command text;
- command index.

Examples:

```text
cli.1.show_interface_Ethernet_1_1.0
cli.1.show_interface_Ethernet_1_2.1
```

Special characters in commands are replaced by underscores.

## Exception fixtures

A fixture can raise an exception:

```json
{
  "exception": "napalm.base.exceptions.ConnectionClosedException",
  "args": ["Connection closed."],
  "kwargs": {}
}
```

Use this to test retries, uncertainty, rollback, and escalation paths.

## Sequential-state tests

Model changing state across calls:

```text
get_interfaces.1  → baseline
get_interfaces.2  → changed state
get_interfaces.3  → restored state
```

Useful scenarios:

- connection closes after stage;
- compliance fails after commit;
- retry succeeds after one transient failure;
- commit-confirm pending then clears;
- rollback restores baseline;
- getter becomes unsupported/empty.

## Shared driver test framework

NAPALM's shared tests enforce similar behavior across drivers.

Features:

- same getter tests for all vendors;
- multiple test cases per getter;
- expected output compared to actual normalized output;
- unsupported methods skipped;
- mocked data by default;
- optional switch to a real device.

Generic getter tests live under `napalm/base/test/getters.py` in the studied source.

## Case layout

Driver test cases follow:

```text
test/unit/mocked_data/<test_function>/<case_name>/
```

Each case contains backend responses and `expected_result.json`.

Use case names that encode the behavior, not ticket numbers alone:

- `normal`
- `no_peers`
- `multiple_vrfs`
- `connection_closed`
- `unsupported_version`
- `malformed_counter`

## Real-device test switch

Documented environment variables:

- `NAPALM_TEST_MOCK=1` — mocked data (default)
- `NAPALM_TEST_MOCK=0` — connect to a device
- `NAPALM_HOSTNAME`
- `NAPALM_USERNAME`
- `NAPALM_PASSWORD`
- `NAPALM_OPTIONAL_ARGS`

Credentials belong in ephemeral injected environment state, never committed files/logs.

## Test ladder

```text
unit/helper test
→ mock driver success/failure branches
→ shared getter suite
→ one authorized lab device
→ one device per driver/version family
→ bounded inventory batch
```

Each gate must produce a receipt before expansion.

## What mock evidence proves

- orchestration calls the expected method sequence;
- normalized-result consumers handle known shapes;
- typed exceptions route correctly;
- rollback/hold/confirm branches execute;
- compliance reports are interpreted correctly;
- receipts omit credentials.

## What mock evidence does not prove

- transport authentication works;
- device OS output matches fixtures;
- parser handles an unseen release;
- locking/atomicity/rollback behaves correctly;
- timing and concurrency limits;
- platform service prerequisites;
- real configuration safety.

## Community-driver responsibilities

A community driver maintainer owns:

- API compatibility with core;
- documentation and caveats;
- bug and issue triage;
- review/release process;
- mocked and real-device tests;
- backend dependency compatibility.

Evaluate maintenance activity and tests before adoption.

## Driver implementation shape

A driver must:

1. subclass `NetworkDriver`;
2. implement lifecycle methods;
3. implement supported getters with documented normalized shapes;
4. raise `NotImplementedError` for unsupported methods;
5. implement configuration semantics/caveats accurately;
6. map backend failures to NAPALM exceptions;
7. provide fixtures and shared tests;
8. document required services and `optional_args`.

## Regression-test rule

Every parser/normalization bug should add:

- exact captured backend response;
- expected normalized result;
- minimal named case;
- test on the affected driver;
- shared contract test when the issue is cross-driver.

Preserve raw device output only after sanitization.

## Test receipt

```text
NAPALM/driver/backend version:
Test type: mock | lab | real
Case names:
Methods covered:
Success branches:
Failure branches:
Skipped methods:
Pass/fail counts:
Coverage limitation:
Credentials injected/removed:
Promotion decision:
```

## Source anchors

- `docs/tutorials/mock_driver.rst`
- `docs/development/testing_framework.rst`
- `napalm/base/mock.py`
- `napalm/base/test/`
- `test/`
