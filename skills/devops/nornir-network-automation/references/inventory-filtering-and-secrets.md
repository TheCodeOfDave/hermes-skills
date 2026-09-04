# Inventory, Filtering, and Runtime Secrets

Load this reference when building a file-backed inventory or injecting credentials.

## Neutral `SimpleInventory` template

`config.yaml`:

```yaml
inventory:
  plugin: SimpleInventory
  options:
    host_file: inventory/hosts.yaml
    group_file: inventory/groups.yaml
    defaults_file: inventory/defaults.yaml
runner:
  plugin: threaded
  options:
    num_workers: 4
logging:
  enabled: false
core:
  raise_on_error: false
```

`inventory/hosts.yaml`:

```yaml
edge-a:
  hostname: "<device-address>"
  platform: ios
  groups: [read-only]
edge-b:
  hostname: "<device-address>"
  platform: nxos_ssh
  groups: [read-only]
```

`inventory/groups.yaml`:

```yaml
read-only:
  connection_options:
    napalm:
      extras:
        optional_args:
          ssh_strict: true
          system_host_keys: true
```

`inventory/defaults.yaml`:

```yaml
---
```

The inventory intentionally contains no `username` or `password` fields. When a private alternate host-key file is required, resolve its path at runtime; do not publish captured key material or an environment-specific path.

## Exact filtering

```python
from nornir import InitNornir

requested = {"edge-a", "edge-b"}
nr = InitNornir(config_file="config.yaml")
selected = nr.filter(filter_func=lambda host: host.name in requested)
resolved = set(selected.inventory.hosts)
if resolved != requested:
    raise RuntimeError(
        f"target mismatch: requested={len(requested)} resolved={len(resolved)}"
    )
```

Compare sets, not only counts. Two wrong labels can satisfy a count assertion.

## Runtime credential injection

```python
import os

username = os.environ["NORNIR_USERNAME"]
password = os.environ["NORNIR_PASSWORD"]
try:
    for host in selected.inventory.hosts.values():
        host.username = username
        host.password = password
    result = selected.run(task=read_only_task)
finally:
    for host in selected.inventory.hosts.values():
        host.username = None
        host.password = None
    selected.close_connections()
```

Clearing host attributes removes retained inventory references; it does not securely erase immutable Python strings. Keep the process short-lived and prevent secrets from entering durable output.

Environment variables are an injection interface, not a durable secret store. Populate them through a secret manager or protected process wrapper; do not put literal values in shell history. Do not dump the process environment for debugging.

## Inheritance checks

Host attributes can come from the host, one or more groups, or defaults. Use Nornir's resolved accessors rather than assuming the value exists directly on the host object. For connection settings, inspect `host.get_connection_parameters("<connection-name>")` and verify the effective result before connecting.

Completion criterion: requested and resolved label sets match, effective connection options preserve strict verification, and no serialized inventory contains credential values.
