from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import copy
import unittest


skill_dir = Path(__file__).parents[1]
spec = spec_from_file_location("lifecycle_conformance", skill_dir / "scripts" / "lifecycle_conformance.py")
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
fixture_path = skill_dir / "tests" / "fixtures" / "lifecycle-trace.json"
authority_fixture_path = skill_dir / "tests" / "fixtures" / "lifecycle-authority-receipts.json"


class LifecycleConformanceTest(unittest.TestCase):
    def setUp(self):
        self.trace = module.load_trace(fixture_path)
        self.authority = module.load_trusted_authority_receipts(authority_fixture_path)

    def events(self, trace=None):
        return (trace or self.trace)["scenarios"][0]["events"]

    def event(self, kind, *, child=None, trace=None):
        return next(item for item in self.events(trace) if item["type"] == kind and (child is None or item.get("child") == child))

    def errors(self, trace=None, authority=None):
        return module.validate_trace_document(
            trace or self.trace,
            self.authority if authority is None else authority,
        )

    def assert_rejected(self, trace, marker, authority=None):
        self.assertTrue(
            any(marker in error for error in self.errors(trace, authority)),
            self.errors(trace, authority),
        )

    def reseal(self, value, *, excluded=("type", "receipt_digest")):
        value["receipt_digest"] = module.canonical_digest(
            {key: item for key, item in value.items() if key not in excluded}
        )

    def test_accepts_complete_evidence_bus_slice(self):
        self.assertEqual(self.errors(), [])

    def test_rejects_full_history(self):
        trace = copy.deepcopy(self.trace)
        self.event("spawn", child="writer-governance", trace=trace)["fork_context"] = "all"
        self.assert_rejected(trace, "full-history")

    def test_rejects_self_issued_or_token_materiality(self):
        for key, value, marker in (
            ("issued_by", "writer-governance", "self-issued"),
            ("asset_kind", "verification-token", "verification-token"),
        ):
            trace = copy.deepcopy(self.trace)
            self.event("spawn", child="writer-governance", trace=trace)["materiality_manifest"][key] = value
            self.assert_rejected(trace, marker)

    def test_rejects_tiny_split_padding_and_duplicate_ranges(self):
        for mutation, marker in (("tiny", "materiality predicate"), ("padding", "materiality predicate"), ("duplicate", "duplicate content")):
            with self.subTest(mutation=mutation):
                trace = copy.deepcopy(self.trace)
                ranges = self.event("spawn", child="writer-governance", trace=trace)["materiality_manifest"]["source_ranges"]
                if mutation == "tiny":
                    ranges[:] = ranges[:2]
                elif mutation == "padding":
                    for item in ranges:
                        item["non_padding_bytes"] = 1
                else:
                    ranges[1]["content_sha256"] = ranges[0]["content_sha256"]
                self.assert_rejected(trace, marker)

    def test_rejects_primary_replay_and_full_allowlist(self):
        for mutation, marker in (("replay", "not admitted"), ("full", "strict 10%"), ("opaque", "opaque/unavailable")):
            trace = copy.deepcopy(self.trace)
            access = self.event("primary_access", trace=trace)
            if mutation == "replay":
                access["kind"] = "transferred_source_replay"
            elif mutation == "full":
                access["unique_ranges"] = access["manifest_ranges"]
                access["unique_bytes"] = access["manifest_bytes"]
            else:
                access["attribution"] = "unavailable"
            self.assert_rejected(trace, marker)

    def test_integration_cannot_replay_full_transferred_source(self):
        trace = copy.deepcopy(self.trace)
        access = self.event("primary_access", trace=trace)
        access["kind"] = "integration"
        access["receipt_digest"] = module.canonical_digest(
            {key: value for key, value in access.items() if key not in {"type", "receipt_digest"}}
        )
        self.assert_rejected(trace, "integration cannot replay transferred source")

    def test_rejects_pre_spawn_sampling_laundering(self):
        trace = copy.deepcopy(self.trace)
        access = self.event("primary_access", trace=trace)
        self.events(trace).remove(access)
        self.events(trace).insert(1, access)
        self.assert_rejected(trace, "pre-spawn sampling")

    def test_rejects_cumulative_sampling_above_task_budget(self):
        trace = copy.deepcopy(self.trace)
        access = self.event("primary_access", trace=trace)
        index = self.events(trace).index(access)
        second = copy.deepcopy(access)
        second["receipt_digest"] = "c" * 64
        self.events(trace).insert(index + 1, second)
        self.assert_rejected(trace, "strict 10%")

    def test_owner_alias_preserves_writer_compaction_budget(self):
        for reason in ("overlap", "rename", "split", "merge"):
            with self.subTest(reason=reason):
                trace = copy.deepcopy(self.trace)
                authority = copy.deepcopy(self.authority)
                self.event("owner_union", trace=trace)["reason"] = reason
                spawn = self.event("spawn", child="writer-governance", trace=trace)
                old = spawn["authority_receipts"]["compaction_baseline"]
                baseline = next(item for item in authority["compaction_receipts"] if item["receipt_digest"] == old)
                baseline["cumulative_count"] = 2
                baseline["receipt_digest"] = module.canonical_digest({key: value for key, value in baseline.items() if key != "receipt_digest"})
                spawn["authority_receipts"]["compaction_baseline"] = baseline["receipt_digest"]
                self.assert_rejected(trace, "writer compaction budget exhausted", authority)

    def test_rejects_illegal_send_message_to_custom_role(self):
        trace = copy.deepcopy(self.trace)
        index = self.events(trace).index(self.event("spawn", child="tester", trace=trace))
        self.events(trace).insert(index + 1, {
            "type": "send_message", "producer": "primary", "consumer": "tester",
            "dependency": "status", "digest": "a" * 64, "purpose": "evidence",
            "admitted": True, "starts_turn": False, "changes_handoff": False,
        })
        self.assert_rejected(trace, "custom-role or peer message")

    def test_rejects_status_poll_or_custom_followup(self):
        for target, reason, poll, marker in (
            ("writer-governance", "status_poll", True, "reason/scope"),
            ("tester", "authorized_continue", False, "custom/reviewer followup"),
        ):
            trace = copy.deepcopy(self.trace)
            receipt = self.event("receipt", child=target, trace=trace)
            index = self.events(trace).index(receipt)
            self.events(trace).insert(index + 1, {
                "type": "followup_task", "target": target, "reason": reason,
                "same_scope": True, "authorized": True, "changes_scope": False,
                "scope_digest": self.event("spawn", child=target, trace=trace)["work_transfer"]["admitted_state_digest"],
                "status_poll": poll,
            })
            self.assert_rejected(trace, marker)

    def test_rejects_stale_freeze_readback(self):
        trace = copy.deepcopy(self.trace)
        self.event("gate_result", child="review-method", trace=trace)["readback"]["worktree"] = "0" * 64
        self.assert_rejected(trace, "stale or invalid gate attempt")

    def test_repair_invalidates_every_gate(self):
        trace = copy.deepcopy(self.trace)
        close = self.event("close", trace=trace)
        index = self.events(trace).index(close)
        changed = copy.deepcopy(close["readback"])
        changed["worktree"] = "0" * 64
        self.events(trace).insert(index, {"type": "repair", "readback": changed})
        close["readback"] = changed
        self.assert_rejected(trace, "all fresh required gates PASS")

    def test_rejects_duplicate_invariant_registry(self):
        trace = copy.deepcopy(self.trace)
        gate = self.event("gate_register", trace=trace)
        duplicate = copy.deepcopy(gate)
        duplicate["gate_id"] = "duplicate-gate"
        index = self.events(trace).index(gate)
        self.events(trace).insert(index + 1, duplicate)
        self.assert_rejected(trace, "duplicate invariant ownership")

    def test_rejects_nonterminal_tree(self):
        trace = copy.deepcopy(self.trace)
        self.events(trace).remove(self.event("gate_result", child="review-governance", trace=trace))
        self.assert_rejected(trace, "terminal tree")

    def test_rejects_invalid_pilot_admission(self):
        for key, value in (("issued_by", "agent"), ("status", "expired"), ("task_id", "other-task")):
            trace = copy.deepcopy(self.trace)
            self.event("pilot_admission", trace=trace)[key] = value
            self.assertTrue(self.errors(trace))

    def test_requires_externally_trusted_authority_receipts(self):
        self.assert_rejected(self.trace, "trusted authority receipts are missing", authority={})

    def test_rejects_forged_materiality_issuer_even_after_rehash(self):
        trace = copy.deepcopy(self.trace)
        manifest = self.event("spawn", child="writer-governance", trace=trace)["materiality_manifest"]
        manifest["issued_by"] = "forged-owner"
        manifest["manifest_digest"] = module.canonical_digest(
            {key: value for key, value in manifest.items() if key != "manifest_digest"}
        )
        self.assert_rejected(trace, "not admitted by trusted authority")

    def test_three_writer_followups_cannot_replay_zero_compaction_receipt(self):
        trace = copy.deepcopy(self.trace)
        receipt = self.event("receipt", child="writer-governance", trace=trace)
        index = self.events(trace).index(receipt) + 1
        scope = self.event("spawn", child="writer-governance", trace=trace)["work_transfer"]["admitted_state_digest"]
        injected = []
        for _ in range(3):
            injected.extend((
                {
                    "type": "followup_task", "target": "writer-governance",
                    "reason": "authorized_continue", "same_scope": True,
                    "scope_digest": scope, "authorized": True,
                    "changes_scope": False, "status_poll": False,
                },
                copy.deepcopy(receipt),
            ))
        self.events(trace)[index:index] = injected
        self.assert_rejected(trace, "writer compaction is not admitted by trusted authority")

    def test_rejects_noop_default_without_descendants_or_material_relay(self):
        trace = copy.deepcopy(self.trace)
        removed = {"peer-producer", "peer-consumer"}
        self.events(trace)[:] = [
            event for event in self.events(trace)
            if event.get("child") not in removed
            and event.get("producer") not in removed
            and event.get("consumer") not in removed
        ]
        self.assert_rejected(trace, "default peer is a no-op")

    def test_scope_expanding_message_rejected_after_self_rehash(self):
        trace = copy.deepcopy(self.trace)
        message = self.event("send_message", trace=trace)
        spawn = self.event("spawn", child="writer-governance", trace=trace)
        message["dependency"] = "new out-of-scope dependency"
        message["receipt_digest"] = "fe" * 32
        spawn["work_transfer"]["admitted_receipt_digests"] = [message["receipt_digest"]]
        spawn["work_transfer"]["admitted_state_digest"] = module.canonical_digest(
            {key: value for key, value in spawn["work_transfer"].items() if key != "admitted_state_digest"}
        )
        message["scope_digest"] = spawn["work_transfer"]["admitted_state_digest"]
        message["digest"] = module.canonical_digest(
            {key: value for key, value in message.items() if key not in {"type", "digest"}}
        )
        self.assert_rejected(trace, "not admitted by trusted authority")

    def test_message_authority_binds_primary_producer(self):
        trace = copy.deepcopy(self.trace)
        message = self.event("send_message", trace=trace)
        message["producer"] = "host"
        message["digest"] = module.canonical_digest(
            {key: value for key, value in message.items() if key not in {"type", "digest"}}
        )
        self.assert_rejected(trace, "receipt/scope is not admitted by trusted authority")

    def test_pilot_admission_fail_closed_matrix(self):
        mutations = {
            "missing": lambda trace: self.events(trace).remove(self.event("pilot_admission", trace=trace)),
            "forged": lambda trace: self.event("pilot_admission", trace=trace).update(issued_by="proxy-host"),
            "typed-actions": lambda trace: self.event("pilot_admission", trace=trace).update(actions=[{"bad": "type"}]),
            "typed-exclusions": lambda trace: self.event("pilot_admission", trace=trace).update(excluded_active_task_ids=[1]),
            "cross-scope": lambda trace: self.event("pilot_admission", trace=trace).update(slice_id="other-slice"),
            "expired": lambda trace: self.event("pilot_admission", trace=trace).update(observed_at="2027-01-01T00:00:00Z"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                trace = copy.deepcopy(self.trace)
                mutate(trace)
                if label != "missing":
                    self.reseal(self.event("pilot_admission", trace=trace))
                self.assertTrue(self.errors(trace), label)

    def test_pilot_revision_must_match_frozen_head(self):
        trace = copy.deepcopy(self.trace)
        pilot = self.event("pilot_admission", trace=trace)
        pilot["revision"] = "f" * 64
        self.reseal(pilot)
        self.assert_rejected(trace, "pilot revision does not match frozen HEAD")

    def test_pilot_authorization_is_stale_after_repair_generation(self):
        trace = copy.deepcopy(self.trace)
        pilot = self.event("pilot_admission", trace=trace)
        close = self.event("close", trace=trace)
        changed = copy.deepcopy(close["readback"])
        changed["worktree"] = "9" * 64
        self.events(trace).insert(self.events(trace).index(close), {"type": "repair", "readback": changed})
        close["readback"] = changed
        self.assert_rejected(trace, "pilot authorization is stale for the final generation")

    def test_auto_create_action_normalization_uses_trusted_resigned_authority(self):
        variants = (
            "create task", "create-task", "create.task", "create_task", "createTask",
            "auto create task", "auto-create-task", "auto.create_task", "autoCreateTask",
        )
        for action in variants:
            with self.subTest(action=action):
                trace = copy.deepcopy(self.trace)
                authority = copy.deepcopy(self.authority)
                pilot = self.event("pilot_admission", trace=trace)
                pilot["actions"] = [action]
                self.reseal(pilot)
                authority["pilot_authorizations"] = [
                    {key: value for key, value in pilot.items() if key != "type"}
                ]
                self.assert_rejected(trace, "pilot admission exclusions/actions invalid", authority)

    def test_rejects_forged_or_missing_default_capability_anchor(self):
        for value in (None, "fa" * 32):
            trace = copy.deepcopy(self.trace)
            self.event("spawn", child="peer-coordinator", trace=trace)["authority_receipts"]["peer_capability"] = value
            self.assert_rejected(trace, "capability is not admitted by trusted authority")

    def test_binds_work_transfer_route_and_topology_to_spawn(self):
        trace = copy.deepcopy(self.trace)
        spawn = self.event("spawn", child="writer-governance", trace=trace)
        spawn["work_transfer"]["route"] = "garbage"
        self.assert_rejected(trace, "route/topology is not bound")

    def test_rejects_task_budget_denominator_laundering(self):
        trace = copy.deepcopy(self.trace)
        access = self.event("primary_access", trace=trace)
        second = copy.deepcopy(access)
        second.update(receipt_digest="d" * 64, manifest_ranges=1000, manifest_bytes=1000000)
        self.events(trace).insert(self.events(trace).index(access) + 1, second)
        self.assert_rejected(trace, "sampling denominator changed")

    def test_materiality_digest_binds_issuer_and_ranges(self):
        trace = copy.deepcopy(self.trace)
        manifest = self.event("spawn", child="writer-governance", trace=trace)["materiality_manifest"]
        manifest["issued_by"] = "different-host"
        self.assert_rejected(trace, "does not bind its canonical payload")

    def test_rejects_second_sequential_writer_in_one_slice(self):
        trace = copy.deepcopy(self.trace)
        first_spawn = self.event("spawn", child="writer-governance", trace=trace)
        second_spawn = copy.deepcopy(first_spawn)
        second_spawn["child"] = "writer-second"
        second_spawn["owner_component"] = "second-component"
        second_spawn["owner_paths"] = ["new/a", "new/b", "new/c"]
        second_spawn["work_transfer"]["consumer"] = "writer-second"
        manifest = second_spawn["materiality_manifest"]
        for index, item in enumerate(manifest["source_ranges"]):
            item["path"] = f"new/{chr(97 + index)}"
            item["path_sha256"] = chr(97 + index) * 64
            item["content_sha256"] = chr(100 + index) * 64
        manifest["manifest_digest"] = module.canonical_digest({key: value for key, value in manifest.items() if key != "manifest_digest"})
        second_receipt = copy.deepcopy(self.event("receipt", child="writer-governance", trace=trace))
        second_receipt["child"] = "writer-second"
        first_receipt = self.event("receipt", child="writer-governance", trace=trace)
        index = self.events(trace).index(first_receipt) + 1
        self.events(trace)[index:index] = [second_spawn, second_receipt]
        self.assert_rejected(trace, "at most one writer")

    def test_slice_digest_binds_state_summary_and_contract(self):
        trace = copy.deepcopy(self.trace)
        self.event("slice_open", trace=trace)["state_summary"].append("unbound")
        self.assert_rejected(trace, "does not bind canonical payload")

    def test_pilot_validity_uses_observed_timestamp(self):
        trace = copy.deepcopy(self.trace)
        pilot = self.event("pilot_admission", trace=trace)
        pilot.update(valid_from="1999-01-01T00:00:00Z", valid_until="2000-01-01T00:00:00Z")
        pilot["receipt_digest"] = module.canonical_digest({key: value for key, value in pilot.items() if key not in {"type", "receipt_digest"}})
        self.assert_rejected(trace, "outside its validity window")

    def test_pilot_digest_and_target_identity_are_bound(self):
        trace = copy.deepcopy(self.trace)
        pilot = self.event("pilot_admission", trace=trace)
        pilot["target"] = ""
        pilot["receipt_digest"] = module.canonical_digest({key: value for key, value in pilot.items() if key not in {"type", "receipt_digest"}})
        self.assert_rejected(trace, "signer/target/revision identity")

    def test_requires_exactly_three_unique_required_gates(self):
        trace = copy.deepcopy(self.trace)
        slice_open = self.event("slice_open", trace=trace)
        slice_open["required_gate_ids"] = ["methodology", "efficiency", "efficiency"]
        slice_open["state_digest"] = module.canonical_digest({key: value for key, value in slice_open.items() if key not in {"type", "state_digest"}})
        self.event("close", trace=trace)["required_gate_ids"] = ["methodology", "efficiency", "efficiency"]
        self.assert_rejected(trace, "exactly three unique gates")

    def test_readback_actor_must_be_running_matching_child(self):
        trace = copy.deepcopy(self.trace)
        readback = self.event("readback", trace=trace)
        self.events(trace).remove(readback)
        spawn = self.event("spawn", child="tester", trace=trace)
        self.events(trace).insert(self.events(trace).index(spawn), readback)
        self.assert_rejected(trace, "stale filesystem readback")

    def test_gate_terminal_requires_artifact_and_completion_digests(self):
        trace = copy.deepcopy(self.trace)
        result = self.event("gate_result", child="review-method", trace=trace)
        del result["artifact_receipt_digest"]
        self.assert_rejected(trace, "gate result role/state/schema invalid")

    def test_unique_ranges_and_bytes_each_obey_cumulative_ten_percent(self):
        trace = copy.deepcopy(self.trace)
        access = self.event("primary_access", trace=trace)
        access.update(unique_ranges=9, manifest_ranges=10, unique_bytes=1, manifest_bytes=1000)
        access["receipt_digest"] = module.canonical_digest({key: value for key, value in access.items() if key not in {"type", "receipt_digest"}})
        self.assert_rejected(trace, "strict 10% proper subset")

    def test_primary_access_receipt_binds_payload(self):
        trace = copy.deepcopy(self.trace)
        self.event("primary_access", trace=trace)["unique_bytes"] = 700
        self.assert_rejected(trace, "receipt digest does not bind canonical payload")

    def test_send_message_digest_binds_nonempty_dependency(self):
        trace = copy.deepcopy(self.trace)
        self.event("send_message", trace=trace)["dependency"] = "changed dependency"
        self.assert_rejected(trace, "digest/dependency does not bind canonical payload")
        trace = copy.deepcopy(self.trace)
        message = self.event("send_message", trace=trace)
        message["dependency"] = ""
        message["digest"] = module.canonical_digest({key: value for key, value in message.items() if key not in {"type", "digest"}})
        self.assert_rejected(trace, "digest/dependency does not bind canonical payload")

    def test_failed_or_incomplete_writer_cannot_successfully_close(self):
        for status, safe in (("failed", False), ("incomplete", True)):
            with self.subTest(status=status):
                trace = copy.deepcopy(self.trace)
                receipt = self.event("receipt", child="writer-governance", trace=trace)
                receipt.update(status=status, safe_incomplete=safe)
                self.assert_rejected(trace, "successful close requires every child complete")

    def test_unknown_agent_type_fails_closed(self):
        trace = copy.deepcopy(self.trace)
        spawn = self.event("spawn", child="tester", trace=trace)
        spawn["agent_type"] = "unknown_role"
        spawn["work_transfer"]["route"] = "unknown_role"
        spawn["work_transfer"]["admitted_state_digest"] = module.canonical_digest({key: value for key, value in spawn["work_transfer"].items() if key != "admitted_state_digest"})
        self.assert_rejected(trace, "unknown or unregistered agent type")

    def test_followup_scope_digest_must_match_original_transfer(self):
        trace = copy.deepcopy(self.trace)
        receipt = self.event("receipt", child="writer-governance", trace=trace)
        self.events(trace).insert(self.events(trace).index(receipt) + 1, {
            "type": "followup_task", "target": "writer-governance",
            "reason": "authorized_continue", "same_scope": True,
            "scope_digest": "0" * 64, "authorized": True,
            "changes_scope": False, "status_poll": False,
        })
        self.assert_rejected(trace, "scope digest does not match original work-transfer")

    def test_json_type_anomalies_return_validation_errors(self):
        mutations = (
            lambda trace: self.event("slice_open", trace=trace)["required_gate_ids"].__setitem__(0, {"bad": "gate"}),
            lambda trace: self.event("gate_register", trace=trace)["invariants"].__setitem__(0, ["bad"]),
            lambda trace: self.event("owner_union", trace=trace)["aliases"].__setitem__(0, {"bad": "alias"}),
            lambda trace: trace["scenarios"][0].update(task_id={"bad": "task"}),
            lambda trace: trace["scenarios"][0].update(declared_evidence_tier={"bad": "tier"}),
            lambda trace: self.event("owner_union", trace=trace).update(reason={"bad": "reason"}),
            lambda trace: self.event("spawn", child="writer-governance", trace=trace).update(owner_component={"bad": "component"}),
            lambda trace: self.event("spawn", child="writer-governance", trace=trace)["authority_receipts"].update(compaction_baseline={"bad": "receipt"}),
        )
        for mutate in mutations:
            trace = copy.deepcopy(self.trace)
            mutate(trace)
            self.assertTrue(self.errors(trace))

    def test_invalid_authority_active_task_types_return_errors(self):
        authority = copy.deepcopy(self.authority)
        authority["active_task_ids"] = [{"bad": "task"}]
        errors = self.errors(authority=authority)
        self.assertTrue(any("active-task set is invalid" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
