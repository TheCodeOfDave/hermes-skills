#!/usr/bin/env python
"""Reusable, network-free helpers for testing Nornir task code."""

from __future__ import annotations

from collections.abc import Mapping, Set
from typing import Any

from nornir.core import Nornir
from nornir.core.configuration import Config
from nornir.core.inventory import Defaults, Groups, Host, Hosts, Inventory
from nornir.core.state import GlobalState
from nornir.core.task import AggregatedResult, MultiResult, Result
from nornir.plugins.runners import SerialRunner, ThreadedRunner


class ExactHostSelectionError(ValueError):
    """Raised when a test's requested and resolved host sets differ."""


def build_test_nornir(
    host_specs: Mapping[str, Mapping[str, Any]],
    *,
    runner: str = "serial",
    num_workers: int = 2,
    dry_run: bool = True,
) -> Nornir:
    """Build a Nornir instance from neutral, in-memory host specifications."""
    defaults = Defaults()
    hosts = Hosts(
        {
            name: Host(
                name=name,
                hostname=spec.get("hostname"),
                platform=spec.get("platform", "demo"),
                port=spec.get("port"),
                data=dict(spec.get("data", {})),
                groups=[],
                defaults=defaults,
            )
            for name, spec in host_specs.items()
        }
    )
    inventory = Inventory(hosts=hosts, groups=Groups(), defaults=defaults)
    if runner == "serial":
        runner_plugin = SerialRunner()
    elif runner == "threaded":
        runner_plugin = ThreadedRunner(num_workers=num_workers)
    else:
        raise ValueError("runner must be 'serial' or 'threaded'")
    return Nornir(
        inventory=inventory,
        config=Config(),
        data=GlobalState(dry_run=dry_run),
        runner=runner_plugin,
    )


def select_exact_hosts(nr: Nornir, expected: Set[str]) -> Nornir:
    """Return exactly the named hosts or fail closed on empty/missing targets."""
    requested = set(expected)
    if not requested:
        raise ExactHostSelectionError("expected host set must not be empty")
    selected = nr.filter(filter_func=lambda host: host.name in requested)
    resolved = set(selected.inventory.hosts)
    if resolved != requested:
        raise ExactHostSelectionError(
            f"exact host selection failed: requested={len(requested)} resolved={len(resolved)}"
        )
    return selected


def iter_results(multi: MultiResult):
    """Yield every leaf Result from a host MultiResult, including nested groups."""
    for item in multi:
        if isinstance(item, MultiResult):
            yield from iter_results(item)
        else:
            yield item


def assert_clean_run(
    aggregate: AggregatedResult,
    *,
    expected_hosts: Set[str],
    allow_changed: bool = False,
) -> None:
    """Assert exact result coverage and inspect every nested Result."""
    expected = set(expected_hosts)
    actual = set(aggregate)
    if actual != expected:
        raise AssertionError(
            f"result host mismatch: expected={len(expected)} actual={len(actual)}"
        )
    for multi in aggregate.values():
        for result in iter_results(multi):
            if result.failed:
                raise AssertionError("failed result found")
            if result.changed and not allow_changed:
                raise AssertionError("changed result found")
