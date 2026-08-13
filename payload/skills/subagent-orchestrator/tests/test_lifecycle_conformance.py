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
        self.assertTrue(any("active children" in error for error in self.validate(trace)))

    def test_rejects_authorized_cancel_without_acknowledgement(self):
        trace = copy.deepcopy(self.trace)
        scenario = next(
            item
            for item in trace["scenarios"]
            if item["name"] == "authorized_cancellation_acknowledgement"
        )
        scenario["events"] = [
            event for event in scenario["events"] if event["type"] != "cancel_ack"
        ]
        errors = self.validate(trace)
        self.assertTrue(any("active children" in error for error in errors))
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


if __name__ == "__main__":
    unittest.main()
