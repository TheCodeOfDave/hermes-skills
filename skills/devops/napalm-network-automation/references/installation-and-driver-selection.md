# Installation and Driver Selection

## Scope

Load this reference when installing NAPALM, selecting a core/community driver, choosing a transport, or reviewing driver-specific connection arguments.

## Effective version floor

For NAPALM 5.2.0:

- PyPI metadata: Python `>=3.10`.
- Tag/develop `pyproject.toml`: `requires-python = ">=3.10"`.
- Linux CI: Python 3.10 through 3.14.
- Ruff target: `py310`.
- The runtime import guard still mentions 3.9; it conflicts with current package metadata and is not the installation floor.

Operational rule: install and test 5.2.0 on Python 3.10 or newer.

## Install

Invoke through the `terminal` tool inside an isolated Python environment:

```bash
pip install napalm
```

Verify:

```bash
python -c "import napalm; print(napalm.__version__); print(napalm.SUPPORTED_DRIVERS)"
```

The full package installs dependencies for all core drivers.

## Core drivers

| Name | Platform path | Typical backend |
|---|---|---|
| `eos` | Arista EOS | pyeapi; HTTP/HTTPS/SSH options |
| `ios` | Cisco IOS | Netmiko; SSH/Telnet options |
| `iosxr` | Cisco IOS-XR XML Agent | pyIOSXR |
| `iosxr_netconf` | Cisco IOS-XR NETCONF | ncclient |
| `junos` | Juniper Junos | Junos PyEZ |
| `nxos` | Cisco NX-OS NX-API | HTTP/HTTPS |
| `nxos_ssh` | Cisco NX-OS SSH | Netmiko |
| `mock` | File-backed test driver | local fixture files |

The internal `SUPPORTED_DRIVERS` list also contains `base`; it is not a device target.

## Driver resolution

```python
from napalm import get_network_driver

driver = get_network_driver("eos")
```

Plain driver lookup order:

1. `custom_napalm.<name>` — site-local driver;
2. `napalm.<name>` — core driver;
3. `napalm_<name>` — community driver.

Rules from `get_network_driver(name, prepend=True)`:

- names are lowercased;
- hyphens are removed, so `IOS-XR` resolves as `iosxr`;
- `mock` returns `MockDriver`;
- explicit dotted paths may be `napalm.<driver>` or `custom_napalm.<driver>`;
- additional dots and arbitrary module paths are rejected;
- `prepend=False` is only for already-qualified names containing `napalm`;
- the resolved module must contain a `NetworkDriver` subclass.

Failures raise `ModuleImportError` rather than returning a fallback object.

## Constructor

The base constructor shape is:

```text
NetworkDriver(
    hostname: str,
    username: str,
    password: str,
    timeout: int = 60,
    optional_args: dict | None = None,
)
```

Keep credentials outside source and logs. Pass secrets through a runtime secret mechanism, retain them only for the bounded connection window, and remove temporary environment or file references afterward.

## Driver preflight

Before connection, record:

- exact device OS and version;
- driver and backend library;
- connection service enabled on the device;
- port and transport;
- required getter/configuration methods;
- configuration replace/merge support;
- atomicity, compare, rollback, and commit-confirm support;
- driver caveat page;
- host-key or TLS verification setting;
- timeout and locking behavior.

A driver name is not a capability grant.

## Optional arguments

Common documented options include:

- `port` — all core device drivers;
- `transport` — EOS, IOS, NX-OS;
- `allow_agent`, `use_keys`, `key_file`, `ssh_config_file`;
- `ssh_strict`, `alt_host_keys`, `alt_key_file`;
- `secret` or `enable_password` for privilege escalation;
- `force_no_enable`;
- `global_delay_factor`;
- `config_lock`, `lock_disable`, `config_private`;
- `ssl_verify` for NX-OS;
- `config_encoding` for IOS-XR NETCONF;
- `keepalive` for IOS-XR/Junos;
- `huge_tree` for large Junos XML responses;
- driver-specific candidate/rollback filenames and transfer settings.

Use only options listed for the chosen driver. Unknown keys may be ignored, rejected, or passed to a backend unexpectedly.

## Transport matrix

Documented alternatives:

| Driver | Default | Alternatives |
|---|---|---|
| EOS | `https` | `http`, `https`, `ssh` |
| NX-OS | `https` | `http`, `https` |
| IOS | `ssh` | `telnet`, `ssh` |

Other drivers use their own backend-specific transport model.

## Security-sensitive defaults

- Selected SSH drivers document `ssh_strict=False`, which may accept unknown host keys.
- NX-OS `ssl_verify` defaults to `None`, effectively disabled verification.
- `allow_agent` and `use_keys` broaden credential discovery when enabled.
- Telnet is unencrypted.
- Inline passwords in the NAPALM CLI become shell-history/process-list risk.

For production, configure verification explicitly and use least-privilege accounts.

## Community drivers

Community drivers are plugins maintained outside core. Their maintainer owns:

- API compatibility;
- documentation;
- bug/issue triage;
- tests and releases;
- long-term platform support.

Require current maintenance, package provenance, method tests, and a lab canary before adoption.

## Selection receipt

```text
NAPALM version:
Python version:
Driver/module:
Device OS/version:
Backend/transport/port:
Required capabilities:
Optional arguments:
Host-key/TLS policy:
Caveats reviewed:
Lab canary result:
```

## Source anchors

- `pyproject.toml`
- `README.md`
- `napalm/__init__.py`
- `napalm/base/__init__.py`
- `napalm/_SUPPORTED_DRIVERS.py`
- `docs/installation/`
- `docs/support/index.rst`
