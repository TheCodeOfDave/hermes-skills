#!/usr/bin/env python
"""Exercise Nornir orchestration without network access."""

from __future__ import annotations

from nornir.core import Nornir
from nornir.core.configuration import Config
from nornir.core.inventory import Defaults, Host, Hosts, Groups, Inventory
from nornir.core.task import Result, Task
from nornir.plugins.runners import ThreadedRunner


EXPECTED = {"node-a", "node-b"}


def observe(task: Task) -> Result:
    """Return neutral deterministic data without opening a connection."""
    return Result(
        host=task.host,
        changed=False,
        result={"platform": task.host.platform, "role": task.host.data["role"]},
    )


def build_nornir() -> Nornir:
    hosts = Hosts(
        {
            label: Host(
                name=label,
                platform="demo",
                data={"role": "canary"},
                groups=[],
                defaults=Defaults(),
            )
            for label in sorted(EXPECTED)
        }
    )
    inventory = Inventory(hosts=hosts, groups=Groups(), defaults=Defaults())
    config = Config()
    return Nornir(
        inventory=inventory,
        config=config,
        runner=ThreadedRunner(num_workers=2),
    )


def main() -> int:
    with build_nornir() as nr:
        selected = nr.filter(filter_func=lambda host: host.name in EXPECTED)
        resolved = set(selected.inventory.hosts)
        if resolved != EXPECTED:
            raise RuntimeError("exact target filter failed")
        aggregate = selected.run(name="offline read-only canary", task=observe)
        records = {}
        for label, multi in aggregate.items():
            if len(multi) != 1:
                raise RuntimeError("unexpected offline result shape")
            child = multi[-1]
            records[label] = {
                "failed": bool(multi.failed or child.failed),
                "changed": bool(child.changed),
                "platform": child.result["platform"],
                "role": child.result["role"],
            }

    if set(records) != EXPECTED:
        raise RuntimeError("result labels differ from requested labels")
    if any(item["failed"] or item["changed"] for item in records.values()):
        raise RuntimeError("offline canary reported failure or change")
    print("offline_canary=PASS targets=2 failed=0 changed=0 workers=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
