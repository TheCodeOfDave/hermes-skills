# Compliance Validation

## Scope

Load this reference when writing expected-state YAML, calling `compliance_report()`, interpreting nested reports, handling skipped methods, or using validation as a promotion gate.

## Purpose

NAPALM validation checks **live state**, not configuration text. The validator calls named getters/methods, compares normalized output to expected YAML, and returns a structured report.

Use it after deployment, before confirming a commit, during drift checks, or as a canary acceptance gate.

## API

```python
report = device.compliance_report(validation_file="expected-state.yml")
```

Or provide an in-memory validation source:

```python
report = device.compliance_report(validation_source=rules)
```

Missing validation files and YAML parse failures raise `ValidationException`; unsupported called methods are recorded as skipped after `NotImplementedError`. Current 5.2.0 code does not normalize every malformed in-memory rule: a non-list source can raise `AssertionError`, while invalid comparison expressions can raise `ValueError`. Validate rule shape before treating this API as a typed-error boundary.

## Rule shape

Top-level YAML is a list of method/getter rules:

```yaml
---
- get_facts:
    hostname: edge01

- get_interfaces_ip:
    Ethernet2/1:
      ipv4:
        "<interface-address>":
          prefix_length: 30
```

Expected data follows the method's normalized return shape.

## Partial matching

Default matching validates only specified keys/items. Extra live state is permitted unless strict mode is set at the relevant level.

Use partial mode for:

- required facts/properties;
- one interface/address among many;
- one peer/route/service;
- safety invariants that do not require exhaustive inventory.

## Strict matching

Set `_mode: strict` at the exact nested level that must contain no extras/missing entries:

```yaml
- get_bgp_neighbors:
    global:
      peers:
        _mode: strict
        "<peer-address>":
          is_up: true
```

Strict mode is local to its level. It does not make the whole report globally strict.

## Lists

Lists require a `list` key and can be strict:

```yaml
- get_facts:
    interface_list:
      _mode: strict
      list:
        - Ethernet1
        - Ethernet2
```

Use strict lists only when no additional entries are acceptable.

## Numeric comparisons

Supported rule forms include:

- less than: `'<15.0'`
- greater than: `'>10.0'`
- range: `'10.0<->20.0'`
- integer range: `'10<->20'`
- percentage tolerance: `'10%20'` means ±10% around 20

Quote comparison strings in YAML.

## Method arguments

Use `_kwargs`:

```yaml
- ping:
    _name: ping_google
    _kwargs:
      destination: "<probe-destination>"
      source: "<probe-source>"
    success:
      packet_loss: 0
    _mode: strict
```

Use arguments supported by the chosen driver/method.

## Repeated methods

Use `_name` to distinguish multiple invocations:

```yaml
- ping:
    _name: primary_path
    _kwargs:
      destination: "<primary-destination>"
    success:
      packet_loss: 0

- ping:
    _name: backup_path
    _kwargs:
      destination: "<backup-destination>"
    success:
      packet_loss: 0
```

Names appear in the report and should be stable/meaningful.

## Regex matching

The validator supports regular expressions for expected values. Use anchored expressions where accidental substring matches would be unsafe.

## Report shape

Top-level fields include:

- `complies` — overall boolean;
- `skipped` — methods not executed;
- one report section per getter/name.

Nested sections can include:

- `complies`;
- `present`;
- `missing`;
- `extra`;
- `nested`;
- `diff`;
- `actual_value`;
- `reason` and `skipped`.

The report is designed for machine parsing; render a separate human summary when needed.

## Skipped methods

Unsupported methods are reported in `skipped` and do not count toward the overall result.

Decision rule:

```text
noncritical skipped → report PARTIAL with reason
critical skipped → proof incomplete; fail promotion
```

Never accept outer `complies: true` without checking `skipped`.

## Validation design

For a change gate, include:

- target identity/OS version;
- management reachability;
- affected interfaces/IPs;
- affected BGP/LLDP peers;
- expected route/service state;
- health thresholds;
- one negative invariant when useful;
- strict mode only at safety-critical boundaries.

Keep the rule minimal enough to diagnose failures.

## Change workflow

```text
baseline report
→ stage/compare/commit with timer
→ post-change report
→ inspect skipped and nested failures
→ confirm if complete/pass
→ rollback if fail/incomplete
→ restoration report
```

A validation exception during a commit-confirm timer is a failure to prove safety, not a reason to confirm.

## Common mistakes

- validating configuration instead of operational state;
- placing `_mode: strict` at the wrong level;
- forgetting `list` for list results;
- leaving numeric comparison strings unquoted;
- using a method unsupported by the selected driver;
- ignoring `skipped`;
- validating every field, creating brittle policies;
- using regex without anchors;
- treating a mock report as device proof.

## Validation receipt

```text
Policy file/hash:
Target/driver/device version:
Methods and arguments:
Strict levels:
Thresholds/ranges:
Overall complies:
Skipped methods:
Critical failures:
Extra/missing state:
Decision: CONFIRM | ROLLBACK | HOLD
```

## Source anchors

- `docs/validate/index.rst`
- `napalm/base/validate.py`
- `napalm/base/base.py::compliance_report`
- `test/base/validate/`
