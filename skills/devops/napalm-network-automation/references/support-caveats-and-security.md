# Support Caveats and Security

## Scope

Load this reference before selecting capabilities, connecting to a real device, scaling concurrency, or granting configuration authority. It separates common API shape from driver/device reality.

## Capability dimensions

Evaluate support across all dimensions:

- driver exists;
- device family and minimum release;
- required service/transport enabled;
- method implemented;
- structured versus parsed text data;
- configuration replace/merge support;
- compare fidelity;
- atomicity;
- rollback semantics;
- commit-confirm;
- optional arguments and backend versions;
- mocked and real-device test evidence.

“Vendor supported” is too vague to operate on.

## Core driver variants

- EOS: `eos`
- Junos: `junos`
- IOS-XR NETCONF: `iosxr_netconf`
- IOS-XR XML Agent: `iosxr`
- NX-OS NX-API: `nxos`
- NX-OS SSH: `nxos_ssh`
- IOS: `ios`

Transport variants for one platform can have different method coverage and output fidelity.

## Structured-data boundary

Drivers using native structured APIs typically reduce parsing ambiguity. SSH/text drivers often depend on CLI formatting, TextFSM/TTP templates, and release-specific output.

Structured transport does not guarantee semantic consistency; text transport does not guarantee failure. Test the exact release/output.

## Configuration support lessons

The studied matrix indicates broad replace/merge support but different safety:

- commit-confirm is available only on selected drivers/platforms;
- some rollback behavior is emulated;
- merge operations may be non-atomic;
- compare output can be hand-crafted or simplistic;
- device minimum versions apply to selected features.

Read the current matrix and caveat page immediately before use because the live support page is generated/deployed separately from source.

## Platform prerequisites

Examples from documentation:

- EOS: eAPI/selected transport and privilege handling;
- IOS: SSH/Telnet, file transfers, enable mode, config replace behavior;
- IOS-XR: XML agent or NETCONF service depending on driver;
- Junos: NETCONF/Junos PyEZ, lock/config database options;
- NX-OS: NX-API for `nxos` or SSH for `nxos_ssh`.

Missing service prerequisites are environment failures, not parser bugs.

For virtual IOS switching labs, capability-check commands that vary by image. Some images require `switchport trunk encapsulation dot1q` before `switchport mode trunk`; otherwise the latter can be rejected while a higher-level commit call still returns normally. Verify the resulting interface stanza and trunk operational state.

Also verify virtual L3 interface identity, not only bridge priority. Cloned virtual switches can expose a duplicate SVI MAC even when their base/bridge MACs differ, which breaks ARP while spanning tree appears healthy. In an isolated owned lab, assign unique locally administered SVI MACs only after proving the collision and then verify end-to-end forwarding. Do not copy lab-specific MAC values into reusable examples.

## Security-sensitive optional arguments

### SSH identity

- `ssh_strict=False` is documented for selected SSH drivers and may accept unknown host keys.
- `alt_host_keys`/`alt_key_file` can supply a controlled host-key file.
- `ssh_config_file` can centralize host/identity policy.
- `allow_agent` and `use_keys` broaden key discovery when enabled.
- `key_file` should point to an injected protected file.

Production rule: reject unknown host keys or use a reviewed known-hosts policy.

### TLS

- NX-OS `ssl_verify` defaults to `None`, effectively false in the documented path.
- HTTP is available for some drivers but is unencrypted.
- Use HTTPS with explicit certificate verification where possible.
- Record certificate/CA policy in the connection receipt.

### Privilege

- `secret`/`enable_password` may grant privileged exec.
- `force_no_enable` can prevent automatic elevation.
- Use least-privilege accounts and separate read-only from configuration roles.

### Configuration locking

- `config_lock`, `lock_disable`, `config_private`, and Junos database options change concurrency semantics.
- Never disable locks merely to get past `LockError`.
- Resolve ownership and transaction state first.

## Credential handling

- Inject at runtime from an approved secret mechanism.
- Avoid CLI password flags; they may enter shell history/process listings.
- Never write secrets into fixtures, validator files, debug reports, or wiki notes.
- Sanitize `get_config()` and raw CLI output.
- Remove temporary environment/files after the run.

## Authorization tiers

1. package/import check;
2. mock driver;
3. real read-only lab canary;
4. real read-only production canary;
5. lab candidate/diff/discard;
6. lab commit-confirm/rollback;
7. production canary change with approval;
8. wider bounded rollout.

Each tier requires a separate receipt and explicit authority.

## Concurrency and rate limits

NAPALM itself provides device sessions, not an unlimited orchestration scheduler. Backend/device limits include:

- SSH/API session counts;
- NETCONF locks;
- config-session conflicts;
- command latency and timeouts;
- CPU impact from expensive getters;
- backend library thread safety.

Scale with bounded workers and per-device serialization for mutations. Use Nornir or another orchestrator only after preserving NAPALM's per-device transaction boundaries.

## Data retention risks

Potentially sensitive output:

- running/startup/candidate configurations;
- local users/SNMP data;
- interface/IP/route/topology inventory;
- raw CLI command output;
- debug traces and optional arguments.

Store only what the task needs, with access control and retention limits.

## Capability receipt

```text
Target family/version:
Driver/transport/backend:
Required methods:
Support-matrix result:
Structured or parsed text:
Replace/merge/atomicity:
Compare fidelity:
Rollback/commit-confirm:
Required services:
Host-key/TLS policy:
Privilege/lock policy:
Mock test:
Lab canary:
Authority tier:
```

## Stop conditions

- device/version missing from support evidence;
- required getter/config method unsupported or broken;
- host identity/certificate cannot be verified;
- lock/session owner unknown;
- no tested rollback/recovery path;
- critical validation method skipped;
- connection lost during mutation;
- candidate diff cannot be reviewed;
- output includes secrets that cannot be sanitized.

## Source anchors

- `docs/support/index.rst`
- `docs/support/eos.rst`
- `docs/support/ios.rst`
- `docs/support/iosxr_netconf.rst`
- `docs/support/nxos.rst`
- core driver constructors/optional argument handling
- generated support matrix
