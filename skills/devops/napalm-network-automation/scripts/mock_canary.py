#!/usr/bin/env python
"""Exercise NAPALM's current mock contract without network access."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from napalm import get_network_driver


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="napalm-mock-") as directory:
        fixtures = Path(directory)
        write_json(fixtures / "get_facts.1", {"hostname": "mock-target", "sequence": 1})
        write_json(fixtures / "get_facts.2", {"hostname": "mock-target", "sequence": 2})
        write_json(fixtures / "get_interfaces.1", {"Ethernet1": {"is_up": True}})

        driver = get_network_driver("mock")
        device = driver(
            hostname="mock-target",
            username="",
            password="",
            optional_args={"path": str(fixtures)},
        )

        unsupported = False
        with device:
            if device.is_alive() != {"is_alive": True}:
                raise RuntimeError("mock connection did not open")
            first = device.get_facts()
            second = device.get_facts()
            interfaces = device.get_interfaces()
            try:
                device.get_lldp_neighbors()
            except NotImplementedError:
                unsupported = True

        if first.get("sequence") != 1 or second.get("sequence") != 2:
            raise RuntimeError("per-method facts sequence failed")
        if "Ethernet1" not in interfaces:
            raise RuntimeError("independent interface counter failed")
        if not unsupported:
            raise RuntimeError("missing fixture did not report unsupported behavior")
        if device.is_alive() != {"is_alive": False}:
            raise RuntimeError("context manager did not close")

    print("mock_canary=PASS facts_calls=2 interface_calls=1 unsupported=1 closed=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
