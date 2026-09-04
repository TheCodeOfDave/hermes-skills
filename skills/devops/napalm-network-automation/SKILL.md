---
name: napalm-network-automation
description: Use when operating or testing network devices through NAPALM.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Network, Automation, Python, Testing, Safety]
    related_skills: [network-appliance-diagnostics, eve-ng-api-operations]
---

# NAPALM Network Automation

Use NAPALM's multivendor `NetworkDriver` contract to inspect state, stage configuration, validate outcomes, and test automation without hardware. This skill does not make driver capabilities uniform or authorize a configuration change; it requires Python 3.10+, the `napalm` package, and driver/device-specific preflight evidence.

## When to Use

- "Use NAPALM to collect facts from this router."
- "Choose the right NAPALM driver and transport."
- "Stage and compare a network configuration safely."
- "Validate live network state against expected YAML."
- "Test NAPALM automation without a real device."
- "Diagnose a NAPALM connection, driver, or getter failure."
- "Build a multivendor network automation canary."

## Prerequisites

- Python `>=3.10` for NAPALM 5.2.0.
- Install in an isolated environment by invoking through the `terminal` tool:
  ```bash
  pip install napalm
  ```
- An explicitly authorized lab/device target and supported network OS release.
- Required device service enabled: SSH, NETCONF, eAPI, NX-API, or the driver's documented backend.
- Credentials injected at runtime from a secret system; never store them in code, CLI history, fixtures, or notes.
- Current support matrix and platform caveats reviewed before any method call.

## How to Run

1. Load this skill before using NAPALM.
2. Load the needed topic on demand with `skill_view`, for example:
   ```text
   skill_view(name="napalm-network-automation", file_path="references/configuration-transactions.md")
   ```
3. Invoke Python or the NAPALM CLI through the `terminal` tool.
4. Default to a read-only canary. Configuration methods require explicit target and content authorization.
5. Save scripts with `write_file`; inspect them with `read_file`; make targeted changes with `patch`.

## Quick Reference

- Install: `pip install napalm`
- Driver loader: `from napalm import get_network_driver`
- Core drivers: `eos`, `ios`, `iosxr`, `iosxr_netconf`, `junos`, `nxos`, `nxos_ssh`
- Test driver: `mock`
- Lifecycle: `open`, `close`, `is_alive`
- Read-only canary: `get_facts`, `get_interfaces`, `get_lldp_neighbors`
- Config stage: `load_replace_candidate`, `load_merge_candidate`
- Review: `compare_config`
- Apply: `commit_config`
- Protect: `confirm_commit`, `has_pending_commit`, `rollback`
- Reject: `discard_config`
- Validate: `compliance_report`
- Escape hatch: `cli`
- CLI actions: `configure`, `call`, `validate`

## Procedure

1. **Gate the capability.** Record target, device OS/version, driver, transport, required methods, atomicity, rollback, commit-confirm, and caveats. Read the live support matrix and exact installed driver because documentation and implementation can drift. Completion: every required operation is supported or explicitly rejected before connection.

2. **Verify the package.** Invoke through the `terminal` tool:
   ```bash
   python -c "import napalm; print(napalm.__version__); print(napalm.get_network_driver('mock'))"
   ```
   Completion: an installed version is printed and the mock driver resolves.

3. **Select the driver.** Use `get_network_driver("<driver>")`. Plain names resolve site-local `custom_napalm.<name>`, core `napalm.<name>`, then community `napalm_<name>`. Completion: the expected `NetworkDriver` subclass resolves without `ModuleImportError`.

4. **Open safely.** Prefer a context manager and pass driver-specific `optional_args` only after review. Inject credentials for the bounded call; do not serialize constructor arguments or debug output:
   ```python
   from napalm import get_network_driver

   driver = get_network_driver("eos")
   with driver(hostname, username, password, optional_args=optional_args) as device:
       facts = device.get_facts()
   ```
   Completion: `get_facts()` returns normalized data and the session closes.

5. **Run the read-only canary.** Start with `get_facts()` and `is_alive()`. Add only matrix-supported getters such as `get_interfaces()` or `get_lldp_neighbors()`. Treat `NotImplementedError` as a capability result, not a successful observation. Completion: normalized results carry a neutral target identifier, driver, version, and timestamp without credentials or raw private device facts.

6. **Use normalized getters first.** Call only matrix-supported getters. Use `cli()` only when the common contract cannot satisfy the requirement, and mark the workflow driver-specific. Completion: every observation has a defined schema or an explicit raw-output exception.

7. **Stage configuration only when authorized.** Load a merge or replacement candidate, require `compare_config()`, and use `discard_config()` for any rejected diff. Completion: no commit occurs without a bounded, non-empty, reviewed diff.

8. **Apply with recovery.** Prefer `commit_config(revert_in=<seconds>)` only where commit-confirm is supported and tested; validate live state before `confirm_commit()`. Otherwise use a stricter canary and proven rollback path. Completion: the change is confirmed after passing evidence or `rollback()` is verified.

9. **Validate state.** Use `compliance_report()` with expected-state YAML. Critical methods in `skipped` make the proof incomplete. Completion: operational state—not merely configuration text—matches the policy.

10. **Classify failures.** Separate package/version, driver import, authentication, transport, backend library, unsupported method, lock/session, candidate validation, commit, normalization, and compliance failures. Completion: the first failing layer and typed exception are recorded; output is never invented.

11. **Test before hardware.** Use `get_network_driver("mock")` with call-sequenced fixture files, then run one representative real lab canary. Completion: success and failure branches pass deterministically before wider authority.

12. **Write the receipt.** Record target, driver/package/device versions, transport/security options, methods, candidate hash/diff, rollback protection, validation result, and residual uncertainty. Completion: another operator can reproduce the result without credentials.

## Knowledge References

Load only the relevant file with `skill_view`:

- `references/installation-and-driver-selection.md` — Python floor, install, core/community lookup, transports, and optional arguments.
- `references/lifecycle-and-getters.md` — context manager, connection health, normalized getters, models, and raw CLI escape hatch.
- `references/configuration-transactions.md` — replace/merge candidates, diff, discard, commit-confirm, rollback, and receipts.
- `references/compliance-validation.md` — validator YAML, strict/partial matching, ranges, repeated methods, and skipped checks.
- `references/mock-testing-and-driver-development.md` — mock fixtures, shared tests, real-device switch, and community-driver responsibilities.
- `references/support-caveats-and-security.md` — capability matrices, platform differences, authentication/TLS/host-key boundaries, and canary rules.
- `references/cli-integrations-and-troubleshooting.md` — NAPALM CLI, debug mode, integrations, exceptions, and layered diagnosis.
- `references/api-method-map.md` — lifecycle, configuration, getter, diagnostic, validation, and exception quick maps.
- `references/official-source-audit.md` — first-party source ledger, documentation/source conflicts, required fixes, and proven canary boundary.

## Pitfalls

- “Supported vendor” does not mean every method, device release, transport, atomicity mode, or rollback path is supported.
- NAPALM 5.2.0 package metadata requires Python 3.10; a runtime guard that still says 3.9 is stale and is not the install contract.
- `ssh_strict=False` and effectively disabled NX-OS `ssl_verify` defaults require explicit production review.
- `cli()` returns vendor-native output and forfeits portability.
- Mock success proves orchestration logic, not device behavior.
- A diff proves candidate intent, not operational convergence.
- Commit-confirm is not universal; never simulate certainty where the driver lacks it.
- A critical validator method in `skipped` is not a pass.
- Configuration calls can cause outages. Stop on uncertain lock, connectivity, pending-commit, or rollback state.

## Verification

Invoke through the `terminal` tool:

```bash
python -c "import napalm; assert napalm.__version__ != 'Not installed'; print(napalm.__version__); print(napalm.get_network_driver('mock'))"
```

Run the packaged deterministic checks:

```bash
python scripts/mock_canary.py
python scripts/validate_skill.py
python -m unittest discover -s tests -p "test_*.py" -v
```
