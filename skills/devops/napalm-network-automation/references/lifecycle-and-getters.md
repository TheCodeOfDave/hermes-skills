# Lifecycle and Getters

## Scope

Load this reference when opening/closing devices, running a read-only canary, selecting normalized getters, handling unsupported methods, or deciding whether to use raw CLI output.

## Preferred lifecycle

Use the context manager for bounded work:

```python
from napalm import get_network_driver

driver = get_network_driver("eos")
with driver(hostname, username, password, optional_args=optional_args) as device:
    facts = device.get_facts()
```

The context manager opens and closes the connection. Explicit `open()` and `close()` remain appropriate for longer-lived or asynchronous orchestration, but cleanup must be guaranteed.

## Lifecycle methods

- `open()` — establish the backend connection.
- `close()` — release the session/resources.
- `is_alive()` — return normalized connection health.
- `pre_connection_tests()`, `connection_tests()`, and `post_connection_tests()` are diagnostic hooks used by NAPALM's show-tech CLI path. They are not ordinary application lifecycle steps, and the base implementations raise `NotImplementedError`.

A successful TCP/SSH/API connection is not proof every required method works.

## Read-only canary

Run on one authorized lab device before wider access:

```python
from napalm import get_network_driver

driver = get_network_driver(driver_name)
with driver(hostname, username, password, optional_args=optional_args) as device:
    result = {
        "facts": device.get_facts(),
        "interfaces": device.get_interfaces(),
        "lldp": device.get_lldp_neighbors(),
        "alive": device.is_alive(),
    }
```

Acceptance:

- expected driver opened;
- target identity in `get_facts()` matches intent;
- normalized shapes are present;
- unsupported methods are explicit;
- `is_alive()` reports healthy before close;
- no secret/config dump is retained;
- session closes.

## Getter families

### Identity and configuration

- `get_facts()`
- `get_config()`
- `get_users()`
- `get_snmp_information()`

### Interfaces and topology

- `get_interfaces()`
- `get_interfaces_counters()`
- `get_interfaces_ip()`
- `get_lldp_neighbors()`
- `get_lldp_neighbors_detail()`
- `get_optics()`
- `get_vlans()`

### Routing and neighbors

- `get_bgp_config()`
- `get_bgp_neighbors()`
- `get_bgp_neighbors_detail()`
- `get_arp_table()`
- `get_ipv6_neighbors_table()`
- `get_mac_address_table()`
- `get_route_to()`
- `get_network_instances()`

### Services and health

- `get_environment()`
- `get_ntp_peers()`
- `get_ntp_servers()`
- `get_ntp_stats()`
- `get_probes_config()`
- `get_probes_results()`
- `get_firewall_policies()`

Support varies by driver. Read the live matrix before choosing a getter.

## Normalized result rules

- Downstream code should consume NAPALM's documented dictionaries/models, not vendor parser internals.
- Preserve target, driver, package version, device version, timestamp, getter, and arguments with the result.
- Treat missing keys, empty values, and `NotImplementedError` differently.
- Do not infer unsupported methods from one empty response; inspect driver behavior and tests.
- Keep configuration output sanitized when using `get_config()`.
- Do not silently coerce driver-specific deviations into expected truth.

## Capability handling

`NotImplementedError` is an expected contract outcome.

Use this decision:

```text
supported + tested → call
unsupported → skip with explicit reason
unknown → run lab canary
broken → stop and preserve evidence
```

A skipped critical observation makes a validation incomplete.

## Raw CLI escape hatch

```python
output = device.cli(["show version"], encoding="text")
```

`cli()` returns a command-keyed dictionary. Use it only when:

- no normalized getter exposes the required state;
- exact vendor output is the artifact;
- command and parsing are driver/device-version scoped;
- authorization covers the command;
- output retention is sanitized.

Once `cli()` is used, portability must be re-proven.

## Diagnostics

- `ping()` — normalized success/error result where supported.
- `traceroute()` — normalized hop/probe result where supported.
- Both accept method-specific parameters; check the base signature and driver implementation.
- IOS-XR NETCONF/XML-agent support differs from other drivers.

## Error handling

Connection classes:

- `ConnectAuthError` — credentials/authorization; do not retry unchanged.
- `ConnectTimeoutError` — reachability/service/timeout; bounded retry only after evidence.
- `ConnectionClosedException` — connection became unusable; mark results/transaction uncertain.
- `UnsupportedVersion` — device/backend mismatch.

Command classes:

- `CommandTimeoutException`
- `CommandErrorException`

Do not catch broad `Exception` and report an empty dictionary as success.

## Result receipt

```text
Target:
Driver/package/device version:
Transport/optional arguments:
Getter and arguments:
Returned schema/record count:
Unsupported/skipped methods:
Raw CLI used:
Sanitization performed:
Connection health:
Session closed:
Result: PASS | PARTIAL | FAIL
```

## Read-only scaling rule

Before concurrency across inventory:

1. one mock target;
2. one real lab target;
3. one target per driver/device family;
4. bounded batch;
5. wider inventory.

Record latency, failure rate, backend limits, and connection cleanup at each gate.

## Source anchors

- `napalm/base/base.py`
- `napalm/base/models.py`
- `napalm/base/exceptions.py`
- `docs/base.rst`
- `docs/tutorials/context_manager.rst`
- `docs/support/index.rst`
- driver getter tests under `test/`
