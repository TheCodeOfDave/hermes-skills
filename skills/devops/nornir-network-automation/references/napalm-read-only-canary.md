# NAPALM Read-Only Canary

Load this reference when validating Nornir against real network devices through `nornir-napalm`.

## Preconditions

- The target labels and expected count are explicit.
- NAPALM supports the selected driver, transport, device release, and getter.
- Credentials arrive through a protected runtime channel.
- SSH host-key or TLS certificate verification is strict.
- The selected devices are authorized for read-only inspection.
- Connection reachability has been verified independently from device readiness.

## Canary runner

```python
from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from nornir import InitNornir
from nornir_napalm.plugins.tasks import napalm_get


def sanitized_facts(raw: dict) -> dict:
    return {
        "vendor": raw.get("vendor"),
        "model": raw.get("model"),
        "os_version": raw.get("os_version"),
        "uptime_seconds": raw.get("uptime"),
        "interface_count": len(raw.get("interface_list") or []),
        "hostname_present": bool(raw.get("hostname")),
    }


def main() -> int:
    requested = {"edge-a", "edge-b"}
    username = os.environ["NORNIR_USERNAME"]
    password = os.environ["NORNIR_PASSWORD"]

    with InitNornir(config_file="config.yaml") as nr:
        selected = nr.filter(filter_func=lambda host: host.name in requested)
        resolved = set(selected.inventory.hosts)
        if resolved != requested:
            raise RuntimeError(
                f"target mismatch: requested={len(requested)} resolved={len(resolved)}"
            )

        records = {}
        try:
            for host in selected.inventory.hosts.values():
                host.username = username
                host.password = password

            aggregate = selected.run(
                name="read-only facts",
                task=napalm_get,
                getters=["facts"],
            )

            for label, multi in aggregate.items():
                if not multi:
                    raise RuntimeError(f"missing result for {label}")
                facts_results = [
                    item
                    for item in multi
                    if isinstance(item.result, dict) and "facts" in item.result
                ]
                if len(facts_results) != 1:
                    raise RuntimeError(f"unexpected facts result shape for {label}")
                facts_result = facts_results[0]
                records[label] = {
                    "failed": bool(multi.failed or any(item.failed for item in multi)),
                    "changed": any(bool(item.changed) for item in multi),
                    "facts": sanitized_facts(facts_result.result["facts"]),
                }
        finally:
            for host in selected.inventory.hosts.values():
                host.username = None
                host.password = None

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_count": len(records),
        "successful": sum(not item["failed"] for item in records.values()),
        "failed": sum(item["failed"] for item in records.values()),
        "changed": sum(item["changed"] for item in records.values()),
        "results": records,
    }
    if (
        summary["target_count"] != len(requested)
        or summary["failed"] != 0
        or summary["changed"] != 0
    ):
        raise RuntimeError("read-only canary failed acceptance")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The code retains neutral labels but excludes raw hostname, FQDN, serial number, interface names, addresses, and credentials. Tighten the result schema further when those fields are not needed.

## Sequential fallback

If shared lab capacity, duplicate virtual identities, jump-host limits, or device boot behavior makes concurrency unreliable, serialize by exact target:

1. start or prepare one disposable target through its owning control plane;
2. verify device identity and management readiness;
3. run the exact one-host read-only canary;
4. preserve sanitized result evidence;
5. close the device connection;
6. stop the disposable target when lifecycle ownership and cleanup authority are unambiguous;
7. repeat for the next target;
8. aggregate only already-passing per-target evidence.

When a shared SSH jump transport supplies per-device sockets, **open the jump channel inside the per-host task** immediately before the NAPALM child task and close it in that task's `finally` block. Do not pre-open channels for the whole serial target set: later unauthenticated channels can time out while earlier hosts run, producing misleading EOF/connection failures. Keep the outer trusted jump session open only for the bounded run.

NAPALM `cli()` uses ordinary prompt detection. Asynchronous commands such as spanning-tree debug can keep emitting text and cause a prompt timeout even though the command took effect. For an explicitly authorized observation task, call the backend's timing-aware method such as `send_command_timing`, capture only sanitized evidence, and issue the paired cleanup such as `undebug all` in `finally`. Keep normalized getters and ordinary show commands on the normal NAPALM path.

Do not treat VM process state as network-OS readiness. Console state, management reachability, authenticated connection, getter success, and clean shutdown are separate checks.

## Acceptance

Require all of the following:

- resolved labels exactly equal requested labels;
- each host has the expected task and child result shape;
- `failed` is false for every host and child;
- `changed` is false for every read-only child;
- aggregate totals reconcile with enumerated records;
- connections close even on failure;
- evidence contains only approved, sanitized fields;
- no configuration task or retry branch ran.

Mock or offline results do not satisfy this live-device acceptance gate.
