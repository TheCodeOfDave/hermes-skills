# Official Source Audit

## Scope

This audit reconciles the shareable skill against NAPALM 5.2.0 first-party documentation, package metadata, and source. It records conflicts instead of silently choosing whichever page looks newer.

## Sources

- Documentation home: <https://napalm.readthedocs.io/en/latest/>
- Installation: <https://napalm.readthedocs.io/en/latest/installation/index.html>
- `NetworkDriver` API: <https://napalm.readthedocs.io/en/latest/base.html>
- Support matrices and optional arguments: <https://napalm.readthedocs.io/en/latest/support/index.html>
- Configuration tutorial: <https://napalm.readthedocs.io/en/latest/tutorials/changing_the_config.html>
- Context manager tutorial: <https://napalm.readthedocs.io/en/latest/tutorials/context_manager.html>
- Mock-driver tutorial: <https://napalm.readthedocs.io/en/latest/tutorials/mock_driver.html>
- Compliance validation: <https://napalm.readthedocs.io/en/latest/validate/index.html>
- CLI: <https://napalm.readthedocs.io/en/latest/cli.html>
- Testing framework: <https://napalm.readthedocs.io/en/latest/development/testing_framework.html>
- Official repository: <https://github.com/napalm-automation/napalm>
- PyPI project metadata: <https://pypi.org/project/napalm/>

Research snapshot: NAPALM `5.2.0`; official source commit `820a06b2069eb1d7b0cbe8943ee2dea6e2949d1a`; PyPI requires Python `>=3.10`.

## Required fixes found and implemented

1. **CLI credential exposure.** Upstream CLI examples pass a password argument. The skill now documents the interface without reproducing a real-work password command and routes credentialed use to runtime-injected Python.
2. **Mock fixture counter drift.** The tutorial describes one global call sequence after `open()`. Current `napalm/base/mock.py` keeps counters per method; `open()` does not increment them. The reference and executable canary now assert current behavior.
3. **Python floor conflict.** PyPI and `pyproject.toml` require Python 3.10, while the runtime import guard still says 3.9. The skill uses the packaging contract and identifies the guard as stale.
4. **Lifecycle overstatement.** `pre_connection_tests()`, `connection_tests()`, and `post_connection_tests()` are show-tech diagnostic hooks whose base implementations raise `NotImplementedError`, not normal application lifecycle calls.
5. **Environment-specific wording.** The reusable skill now refers to an approved secret mechanism rather than a particular operator's secret store.
6. **Read-only canary scope.** The public canary starts with `get_facts()` and `is_alive()` and adds only support-matrix-approved getters. It does not assume LLDP or interface getter support merely because a driver exists.
7. **Validation exception overstatement.** File I/O and YAML parsing failures are wrapped as `ValidationException`, but malformed in-memory sources and comparison expressions can surface `AssertionError` or `ValueError`. The references now distinguish those paths.

## Confirmed contracts

- `get_network_driver()` resolves core, custom, community, and mock drivers but validates names and raises `ModuleImportError` on invalid or absent drivers.
- The context manager calls `open()` on entry and `close()` on exit, including cleanup after an entry failure.
- Loading a merge or replacement candidate does not itself apply the configuration.
- `compare_config()` returns the candidate-versus-running diff.
- Drivers supporting commit-confirm use `commit_config(revert_in=seconds)`, `has_pending_commit()`, `confirm_commit()`, and `rollback()`; callers must verify exact driver/device support.
- `rollback()` during a pending confirmed commit should revert and clear pending state.
- `compliance_report()` reports `complies`, `skipped`, and method details. Unsupported critical methods make promotion evidence incomplete even when the outer boolean remains true.
- `NotImplementedError` is the common unsupported-method signal.

## Evidence boundary

The packaged mock canary proves deterministic API consumption, per-method fixture sequencing, typed unsupported-method behavior, and connection cleanup. Separately, the design pattern was exercised with read-only `get_facts()` on two network-OS families: two successful targets, zero failed tasks, and zero reported changes. Those private device facts and transport details are intentionally excluded from this repository.

Neither mock nor read-only evidence authorizes configuration. Merge, replacement, commit-confirm, rollback, lock, and recovery behavior require a separately authorized disposable lab for the exact driver, transport, and device release.