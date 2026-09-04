from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

from nornir.core.inventory import Host
from nornir.core.task import Result, Task
from nornir_napalm.plugins.tasks import napalm_get


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from unit_test_harness import (  # noqa: E402
    ExactHostSelectionError,
    assert_clean_run,
    build_test_nornir,
    select_exact_hosts,
)


HOSTS = {
    "node-a": {"platform": "demo", "data": {"role": "edge"}},
    "node-b": {"platform": "demo", "data": {"role": "core"}},
}


def observe(task: Task) -> Result:
    return Result(host=task.host, changed=False, result=task.host.data["role"])


def changed_child(task: Task) -> Result:
    return Result(host=task.host, changed=True, result="candidate differs")


def failed_child(task: Task) -> Result:
    return Result(host=task.host, failed=True, result="synthetic child failure")


def fail_core(task: Task) -> Result:
    if task.host.data["role"] == "core":
        raise RuntimeError("synthetic task failure")
    return observe(task)


def grouped_observation(task: Task, *, changed: bool = False) -> Result:
    task.run(task=changed_child if changed else observe, name="inspect child")
    return Result(host=task.host, changed=False, result="group complete")


def grouped_failure(task: Task) -> Result:
    task.run(task=failed_child, name="failed child")
    return Result(host=task.host, result="unreachable")


class UnitTestHarnessTests(unittest.TestCase):
    def test_builds_in_memory_inventory_and_filters_exact_hosts(self):
        nr = build_test_nornir(HOSTS)

        selected = select_exact_hosts(nr, {"node-b"})

        self.assertEqual(set(nr.inventory.hosts), {"node-a", "node-b"})
        self.assertEqual(set(selected.inventory.hosts), {"node-b"})
        self.assertEqual(selected.inventory.hosts["node-b"].data["role"], "core")

    def test_exact_selection_rejects_empty_or_missing_hosts(self):
        nr = build_test_nornir(HOSTS)

        with self.assertRaises(ExactHostSelectionError):
            select_exact_hosts(nr, set())
        with self.assertRaises(ExactHostSelectionError):
            select_exact_hosts(nr, {"node-missing"})

    def test_clean_run_assertion_accepts_nested_unchanged_results(self):
        nr = build_test_nornir(HOSTS)
        selected = select_exact_hosts(nr, {"node-a"})

        aggregate = selected.run(task=grouped_observation)

        assert_clean_run(aggregate, expected_hosts={"node-a"})
        self.assertEqual(aggregate["node-a"][0].name, "grouped_observation")
        self.assertEqual(aggregate["node-a"][1].name, "inspect child")

    def test_clean_run_assertion_rejects_nested_changes(self):
        nr = build_test_nornir(HOSTS)
        selected = select_exact_hosts(nr, {"node-a"})

        aggregate = selected.run(task=grouped_observation, changed=True)

        with self.assertRaisesRegex(AssertionError, "changed result"):
            assert_clean_run(aggregate, expected_hosts={"node-a"})

    def test_clean_run_assertion_rejects_nested_failures(self):
        nr = build_test_nornir({"node-a": HOSTS["node-a"]})

        with self.assertLogs("nornir.core.task", level="ERROR"):
            aggregate = nr.run(task=grouped_failure)

        self.assertTrue(aggregate.failed)
        self.assertEqual(aggregate["node-a"][1].name, "failed child")
        with self.assertRaisesRegex(AssertionError, "failed result"):
            assert_clean_run(aggregate, expected_hosts={"node-a"})

    def test_failed_hosts_are_skipped_until_explicitly_reset(self):
        nr = build_test_nornir(HOSTS)

        with self.assertLogs("nornir.core.task", level="ERROR"):
            first = nr.run(task=fail_core)
        second = nr.run(task=observe)
        nr.data.reset_failed_hosts()
        third = nr.run(task=observe)

        self.assertTrue(first.failed)
        self.assertEqual(set(first.failed_hosts), {"node-b"})
        self.assertEqual(set(second), {"node-a"})
        self.assertEqual(set(third), {"node-a", "node-b"})

    def test_serial_and_threaded_runners_return_equivalent_results(self):
        observed = {}
        for runner in ("serial", "threaded"):
            nr = build_test_nornir(HOSTS, runner=runner, num_workers=2)
            aggregate = nr.run(task=observe)
            assert_clean_run(aggregate, expected_hosts=set(HOSTS))
            observed[runner] = {
                name: multi[0].result for name, multi in aggregate.items()
            }

        self.assertEqual(observed["serial"], observed["threaded"])

    def test_context_manager_closes_good_and_failed_host_connections(self):
        nr = build_test_nornir(HOSTS)

        with patch.object(Host, "close_connections", autospec=True) as close:
            with nr:
                with self.assertLogs("nornir.core.task", level="ERROR"):
                    aggregate = nr.run(task=fail_core)

        self.assertTrue(aggregate.failed)
        self.assertEqual(close.call_count, 2)

    def test_napalm_task_uses_mocked_connection_without_hardware(self):
        nr = build_test_nornir({"node-a": HOSTS["node-a"]})
        device = MagicMock()
        device.get_facts.return_value = {
            "hostname": "node-a",
            "vendor": "Example",
        }

        with patch.object(
            Host,
            "get_connection",
            autospec=True,
            return_value=device,
        ) as get_connection:
            aggregate = nr.run(task=napalm_get, getters=["facts"])

        assert_clean_run(aggregate, expected_hosts={"node-a"})
        self.assertEqual(
            aggregate["node-a"][0].result["facts"]["hostname"],
            "node-a",
        )
        get_connection.assert_called_once()
        device.get_facts.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
