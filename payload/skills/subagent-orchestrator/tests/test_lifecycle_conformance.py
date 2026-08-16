from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import copy
import unittest


skill_dir = Path(__file__).parents[1]
spec = spec_from_file_location(
    "lifecycle_conformance",
    skill_dir / "scripts" / "lifecycle_conformance.py",
)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
fixture_path = skill_dir / "tests" / "fixtures" / "lifecycle-trace.json"


class LifecycleConformanceTest(unittest.TestCase):
    def setUp(self):
        self.trace = module.load_trace(fixture_path)

    def validate(self, trace=None):
        return module.validate_trace_document(trace or self.trace)

    def scenario(self, name):
        return next(item for item in self.trace["scenarios"] if item["name"] == name)

    def event(self, scenario, event_type):
        return next(item for item in scenario["events"] if item["type"] == event_type)

    def test_accepts_canonical_lifecycle_trace(self):
        self.assertEqual(self.validate(), [])

    def test_rejects_timeout_as_cancellation_authority(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(item for item in trace["scenarios"] if item["name"] == "delayed_parallel_collection")
        event = next(item for item in scenario["events"] if item["type"] == "cancel_request")
        event["outcome"] = "accepted"
        self.assertTrue(any("violates authority" in error for error in self.validate(trace)))

    def test_rejects_finalize_before_terminal_collection(self):
        trace = copy.deepcopy(self.trace)
        events = trace["scenarios"][0]["events"]
        events.insert(2, {"type": "primary_finalize"})
        self.assertTrue(any("active task tree" in error for error in self.validate(trace)))

    def test_rejects_authorized_cancel_without_acknowledgement(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item
            for item in trace["scenarios"]
            if item["name"] == "nested_authorized_cancellation"
        )
        scenario["events"] = [
            event for event in scenario["events"] if event["type"] != "cancel_ack"
        ]
        errors = self.validate(trace)
        self.assertTrue(any("active task tree" in error for error in errors))
        self.assertTrue(any("authorized_cancel_acknowledged" in error for error in errors))

    def test_rejects_replacement_while_original_runs(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(item for item in trace["scenarios"] if item["name"] == "delayed_parallel_collection")
        event = next(item for item in scenario["events"] if item["type"] == "replacement_request")
        event["outcome"] = "accepted"
        self.assertTrue(any("replacement accepted" in error for error in self.validate(trace)))

    def test_requires_multiple_wait_windows_and_independent_peer(self):
        for mutation in ("remove_timeout", "remove_peer"):
            with self.subTest(mutation=mutation):
                trace = copy.deepcopy(self.trace)
                scenario = next(
                    item
                    for item in trace["scenarios"]
                    if item["name"] == "delayed_parallel_collection"
                )
                if mutation == "remove_timeout":
                    removed = False
                    retained = []
                    for event in scenario["events"]:
                        if event["type"] == "wait_timeout" and not removed:
                            removed = True
                        else:
                            retained.append(event)
                    scenario["events"] = retained
                else:
                    scenario["events"] = [
                        event
                        for event in scenario["events"]
                        if event.get("child") != "independent_gate"
                    ]
                self.assertTrue(any(
                    "missing lifecycle coverage" in error
                    for error in self.validate(trace)
                ))

    def test_rejects_governed_custom_peer_topology(self):
        trace = copy.deepcopy(self.trace)
        scenario = self.scenario("delayed_parallel_collection")
        target = copy.deepcopy(scenario["events"][0])
        target["topology"] = "bounded-peer"
        target["delegation_depth"] = 1
        trace["scenarios"][0]["events"][0] = target
        self.assertTrue(any(
            "governed custom route must remain a leaf" in error
            for error in self.validate(trace)
        ))

    def test_rejects_depth_above_one(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item for item in trace["scenarios"] if item["name"] == "bounded_peer_tree"
        )
        scenario["events"][0]["delegation_depth"] = 2
        self.assertTrue(any(
            "invalid topology or delegation depth" in error
            for error in self.validate(trace)
        ))

    def test_rejects_nested_spawn_from_leaf(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item for item in trace["scenarios"] if item["name"] == "bounded_peer_tree"
        )
        scenario["events"][0]["topology"] = "leaf"
        scenario["events"][0]["delegation_depth"] = 0
        self.assertTrue(any(
            "only a bounded peer may spawn a descendant" in error
            for error in self.validate(trace)
        ))

    def test_rejects_non_default_bounded_peer_coordinator(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item for item in trace["scenarios"] if item["name"] == "bounded_peer_tree"
        )
        scenario["events"][0]["agent_type"] = "explorer"
        self.assertTrue(any(
            "only built-in default may coordinate" in error
            for error in self.validate(trace)
        ))

    def test_rejects_third_sequential_leaf_descendant(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item for item in trace["scenarios"] if item["name"] == "bounded_peer_tree"
        )
        third_leaf = copy.deepcopy(scenario["events"][1])
        third_leaf["child"] = "peer_leaf_c"
        scenario["events"].insert(6, third_leaf)
        self.assertTrue(any(
            "bounded-peer leaf cap 2 exceeded" in error
            for error in self.validate(trace)
        ))

    def test_rejects_second_sequential_bounded_peer_coordinator(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item for item in trace["scenarios"] if item["name"] == "bounded_peer_tree"
        )
        second_coordinator = copy.deepcopy(scenario["events"][0])
        second_coordinator["child"] = "peer_coordinator_two"
        scenario["events"].insert(7, second_coordinator)
        self.assertTrue(any(
            "bounded-peer coordinator cap exceeded" in error
            for error in self.validate(trace)
        ))

    def test_rejects_peer_message_protected_field_change(self):
        for field in module.PROTECTED_MESSAGE_CHANGE_FIELDS:
            with self.subTest(field=field):
                trace = copy.deepcopy(self.trace)
                scenario = next(
                    item
                    for item in trace["scenarios"]
                    if item["name"] == "bounded_peer_tree"
                )
                message = next(
                    item for item in scenario["events"] if item["type"] == "message"
                )
                message[field] = True
                self.assertTrue(any(
                    "message cannot change protected handoff fields" in error
                    for error in self.validate(trace)
                ))

    def test_rejects_message_between_governed_custom_leaves(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item
            for item in trace["scenarios"]
            if item["name"] == "delayed_parallel_collection"
        )
        message = copy.deepcopy(
            self.event(self.scenario("bounded_peer_tree"), "message")
        )
        message.update(sender="slow_boundary", recipient="independent_gate")
        scenario["events"].insert(3, message)
        self.assertTrue(any(
            "only built-in leaves under one default bounded peer may message" in error
            for error in self.validate(trace)
        ))

    def test_rejects_message_between_direct_builtin_leaves(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item
            for item in trace["scenarios"]
            if item["name"] == "delayed_parallel_collection"
        )
        spawns = [event for event in scenario["events"] if event["type"] == "spawn"]
        for spawn, agent_type in zip(spawns, ("explorer", "worker"), strict=True):
            spawn["route"] = "built-in"
            spawn["agent_type"] = agent_type
        message = copy.deepcopy(
            self.event(self.scenario("bounded_peer_tree"), "message")
        )
        message.update(sender="slow_boundary", recipient="independent_gate")
        scenario["events"].insert(3, message)
        self.assertTrue(any(
            "only built-in leaves under one default bounded peer may message" in error
            for error in self.validate(trace)
        ))

    def test_rejects_parent_terminal_before_descendants(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item for item in trace["scenarios"] if item["name"] == "bounded_peer_tree"
        )
        scenario["events"].insert(3, {"type": "receipt", "child": "peer_coordinator"})
        self.assertTrue(any(
            "parent terminal before descendants" in error
            for error in self.validate(trace)
        ))

    def test_rejects_missing_permission_inheritance(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item for item in trace["scenarios"] if item["name"] == "bounded_peer_tree"
        )
        scenario["events"][1]["permission_inherited"] = False
        self.assertTrue(any(
            "must prove permission inheritance" in error
            for error in self.validate(trace)
        ))


if __name__ == "__main__":
    unittest.main()
