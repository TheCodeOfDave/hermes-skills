# Configuration Transactions

## Scope

Load this reference before any NAPALM configuration mutation. It covers replace/merge candidates, diff review, discard, commit-confirm, rollback, post-change validation, and uncertain-state handling.

## Hard boundary

Configuration calls require explicit authorization for:

- target device/environment;
- candidate content or file;
- merge versus replacement strategy;
- commit and rollback plan.

A request to inspect or ingest NAPALM does not authorize a router change.

## Transaction model

```text
capability preflight
→ read baseline
→ load candidate
→ compare
→ approve or discard
→ commit with recovery
→ validate live state
→ confirm or roll back
→ close and receipt
```

## Capability preflight

Record per driver/device:

- replace support;
- merge support;
- compare fidelity;
- atomicity for the selected strategy;
- rollback behavior: native, emulated, unavailable;
- commit-confirm support and minimum device release;
- locking options and ownership;
- transfer/file-system requirements;
- management-path recovery.

Never infer this from vendor support alone.

## Baseline

Before staging, collect only impact-relevant evidence:

- `get_facts()`
- sanitized `get_config()` where needed;
- affected interfaces, IPs, BGP/LLDP peers, routes, services;
- `is_alive()`;
- validation policy inputs.

Hash candidate/baseline artifacts without retaining secrets.

## Replace candidate

```python
device.load_replace_candidate(filename="candidate.conf")
```

Or:

```python
device.load_replace_candidate(config="<complete configuration>")
```

Replacement semantics differ by platform. Verify whether the driver/device supports atomic replacement and rollback.

Failure: `ReplaceConfigException` → discard/clear candidate if possible, preserve sanitized error, stop.

## Merge candidate

```python
device.load_merge_candidate(config="<bounded configuration>")
```

Or use `filename=`. Merge can be non-atomic even where replacement is atomic. Platform-generated compare output may be simplistic.

For text-driven IOS merge files, prefer persistent configuration statements over interactive CLI macros. In particular, expand `interface range` into individual interface stanzas unless the exact driver/device canary proves that the transferred merge file executes the macro and readback matches every intended interface.

Failure: `MergeConfigException` → discard candidate, preserve error, stop.

## Compare gate

```python
diff = device.compare_config()
```

Require:

- non-empty diff when change is expected;
- only intended lines/objects;
- no credential/default/unrelated churn;
- additions/deletions match strategy;
- driver-specific compare limitations acknowledged;
- target and diff reviewed together.

Empty diff can mean no change, a failed stage, or poor compare support. Resolve before commit.

Reject with:

```python
device.discard_config()
```

Then verify no pending candidate/confirmed commit state remains.

## Commit without timer

```python
device.commit_config(message="bounded change")
```

Use only when the driver/device cannot provide commit-confirm or the workflow explicitly requires a permanent commit. This increases risk and requires a proven rollback/out-of-band path.

`CommitError` makes state uncertain until re-read.

A normal return from `commit_config()` is not semantic success. A reproduced IOS path returned normally after the device emitted `Command rejected:` for an incompatible trunk-mode command; the driver's detector covered a narrower error phrase. After every commit, perform exact **semantic readback** of each intended command and operational outcome. If readback is absent or partial, mark the transaction uncertain, stop expansion, preserve the sanitized device diagnostic, and recover through the tested rollback/out-of-band path.

## Commit-confirm

Where supported and tested:

```python
device.commit_config(message="bounded change", revert_in=300)
assert device.has_pending_commit() is True
```

Validate within the timer. Confirm only after all critical checks pass:

```python
device.confirm_commit()
assert device.has_pending_commit() is False
```

A second `commit_config()` while a confirmed commit is pending should raise rather than stack another change.

`CommitConfirmException` or an unexpected pending-state result requires immediate state verification.

## Rollback

For failed validation or lost certainty:

```python
device.rollback()
```

Then prove restoration with the baseline getters/compliance policy. Rollback return without state verification is not success.

Rollback can be native, emulated, strategy-dependent, or unavailable. Test the exact driver/device family before production authority.

## Live-state validation

After commit, validate operational outcomes:

- management reachability;
- affected interface state/addressing;
- expected neighbors/routes;
- service/health checks;
- `compliance_report()`;
- no critical method skipped.

Configuration text alone is insufficient.

## Uncertain-state protocol

Treat state as uncertain after:

- connection closed during stage/commit/confirm;
- commit timeout/error;
- lock/session conflict;
- pending-commit status disagrees with expectation;
- validation cannot run;
- rollback error;
- management path lost.
- commit returned normally but semantic readback does not match the reviewed diff.

Response:

1. stop further mutations;
2. preserve transaction ID/timestamps/errors;
3. reconnect read-only if safe;
4. inspect running/pending state;
5. use out-of-band recovery when required;
6. escalate rather than guessing.

## Typed failures

- `LockError`, `UnlockError`, `SessionLockedException`
- `ReplaceConfigException`, `MergeConfigException`
- `CommitError`, `CommitConfirmException`
- `ConnectionClosedException`
- `CommandTimeoutException`, `CommandErrorException`

Map each to a specific stop/retry/recovery decision.

## Mock-first branches

Prove with the mock driver:

- accepted and rejected diff;
- merge/replace exception;
- commit-confirm pending then confirmed;
- validation failure causing rollback;
- connection closed during validation;
- rollback failure escalation.

Then use one real lab canary.

## Change receipt

```text
Target/environment:
NAPALM/driver/device version:
Transport/security options:
Strategy:
Baseline source/hash:
Candidate source/hash:
Diff and reviewer:
Atomicity/rollback semantics:
Commit-confirm timer:
Post-change validation:
Confirmation/rollback result:
Connection/session closed:
Residual uncertainty:
```

## Source anchors

- `napalm/base/base.py`
- `napalm/base/exceptions.py`
- `docs/tutorials/changing_the_config.rst`
- `docs/support/index.rst`
- driver-specific support caveats
- configuration tests and fixture diffs under `test/`
