#!/usr/bin/env python3
"""Validate package integrity, portability, installation, and bundled tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
EXCLUDED_PARTS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
}
EXCLUDED_NAMES = {".coverage", ".DS_Store"}
ROLE_PROFILE_POLICY = {
    "evidence_tester": {
        "class": "evidence-owning-test-or-log-analyst",
        "eligibility": (
            "material structured test output or bounded runbook-driven logs with "
            "explicit acceptance fields and one requested artifact"
        ),
        "routing_markers": (
            "Structured multi-file test or bounded log evidence",
            "`evidence_tester`",
        ),
    },
    "boundary_mapper": {
        "class": "read-only-cross-component-boundary-analyst",
        "eligibility": (
            "one named unresolved execution, state, or persistence boundary after "
            "a targeted primary check"
        ),
        "routing_markers": (
            "One unresolved cross-component execution boundary",
            "`boundary_mapper`",
        ),
    },
    "risk_reviewer": {
        "class": "independent-high-risk-final-gate",
        "eligibility": (
            "required fresh independent review of named high-risk final-state or "
            "acceptance invariants"
        ),
        "routing_markers": (
            "Independent high-risk final decision",
            "fresh `risk_reviewer`",
        ),
    },
    "risk_reviewer_max": {
        "class": "single-escalation-variant-of-risk-reviewer",
        "eligibility": (
            "one fresh escalation only after sufficient evidence leaves competing "
            "causal explanations that can change an irreversible P0/P1, security, "
            "authorization, or data-integrity decision"
        ),
        "routing_markers": (
            "`risk_reviewer_max` is available only",
        ),
    },
}
ADAPTER_REQUIREMENTS = [
    "preserve-role-eligibility",
    "preserve-permission-boundaries",
    "preserve-leaf-non-recursion",
    "preserve-expansion-checkpoints",
    "preserve-terminal-collection",
    "preserve-output-language-contract",
    "treat-model-and-effort-values-as-client-specific-hints",
]


def fail(message: str) -> None:
    raise RuntimeError(message)


def package_files() -> dict[str, Path]:
    result = {}
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if (
            not path.is_file()
            or path == MANIFEST
            or EXCLUDED_PARTS.intersection(relative.parts)
            or path.name in EXCLUDED_NAMES
            or path.suffix == ".pyc"
        ):
            continue
        result[str(relative)] = path
    return result


def verify_manifest() -> None:
    try:
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail(f"manifest is unreadable: {error}")
    declared = {item["path"]: item for item in document.get("files", [])}
    actual = package_files()
    if set(declared) != set(actual):
        missing = sorted(set(declared) - set(actual))
        undeclared = sorted(set(actual) - set(declared))
        fail(f"manifest coverage mismatch; missing={missing}; undeclared={undeclared}")
    for relative, path in actual.items():
        content = path.read_bytes()
        if len(content) != declared[relative].get("size"):
            fail(f"manifest size mismatch: {relative}")
        digest = hashlib.sha256(content).hexdigest()
        if digest != declared[relative].get("sha256"):
            fail(f"manifest hash mismatch: {relative}")


def verify_portability() -> None:
    forbidden_patterns = (
        re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
        re.compile(rb"/home/[A-Za-z0-9._-]+/"),
        re.compile(rb"[A-Za-z]:\\\\Users\\\\[A-Za-z0-9._-]+\\\\"),
    )
    for relative, path in package_files().items():
        content = path.read_bytes()
        for pattern in forbidden_patterns:
            if pattern.search(content):
                fail(f"user-specific absolute path in {relative}")
    profile = json.loads((ROOT / "portable-profile.json").read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        fail("portable profile root must be an object")
    role_entries = profile.get("roles", [])
    if not isinstance(role_entries, list) or not all(
        isinstance(role, dict) for role in role_entries
    ):
        fail("portable profile roles must be a list of objects")
    role_ids = [role.get("id") for role in role_entries]
    if len(role_ids) != len(set(role_ids)):
        fail("portable profile contains duplicate role ids")
    roles = set(role_ids)
    expected = {
        "evidence_tester",
        "boundary_mapper",
        "risk_reviewer",
        "risk_reviewer_max",
    }
    if roles != expected:
        fail(f"portable profile role mismatch: {sorted(roles)}")
    templates = [role.get("template") for role in role_entries]
    if len(templates) != len(set(templates)):
        fail("portable profile contains duplicate role templates")
    if profile.get("primary") != {
        "model": "unconstrained",
        "reasoning_effort": "unconstrained",
        "owns": [
            "authorization",
            "scope",
            "single-writer-integration",
            "conflict-handling",
            "delegation-expansion-checkpoints",
            "final-acceptance",
        ],
    }:
        fail("portable profile constrains or changes primary ownership")

    config = tomllib.loads(
        (ROOT / "payload" / "config.agents.toml").read_text(encoding="utf-8")
    )["agents"]
    default_child = profile.get("default_child")
    if default_child != {
        "model_hint": config["default_subagent_model"],
        "reasoning_effort_hint": config["default_subagent_reasoning_effort"],
    }:
        fail("portable profile default child drifts from package config")
    expected_builtin_routes = [
        {
            "id": "explorer",
            "topology": "leaf",
            "eligibility": (
                "material narrow read-only codebase question whose focused scan "
                "replaces primary exploration"
            ),
        },
        {
            "id": "worker",
            "topology": "leaf",
            "eligibility": (
                "scoped implementation or fix with settled strategy and disjoint "
                "writer ownership"
            ),
        },
    ]
    if profile.get("builtin_routes") != expected_builtin_routes:
        fail("portable profile built-in routes drift from routing ownership")
    if profile.get("concurrency") != {
        "runtime_thread_cap": config["max_concurrent_threads_per_session"],
        "ordinary_first_wave_child_cap": 2,
        "ordinary_first_wave_writer_cap": 1,
        "later_wave_requires_expansion_checkpoint": True,
        "unapproved_expansion_route": "primary-or-close",
        "checkpoint_question_scope": "material-user-owned-choice-only",
        "explicit_final_review_cap": 3,
    }:
        fail("portable profile concurrency drifts from routing/config ownership")

    routing_policy = (
        ROOT
        / "payload"
        / "skills"
        / "subagent-orchestrator"
        / "references"
        / "routing-policy.md"
    ).read_text(encoding="utf-8")
    expected_write_scope = {
        "read-only": "none",
        "workspace-write": "one assigned workspace artifact only",
    }
    for entry in role_entries:
        role = entry["id"]
        expected_template = f"payload/agents/{role}.toml"
        if entry.get("template") != expected_template:
            fail(f"portable profile template mismatch: {role}")
        template = ROOT / expected_template
        if not template.is_file():
            fail(f"portable profile template is missing: {role}")
        document = tomllib.loads(template.read_text(encoding="utf-8"))
        if document.get("name") != role:
            fail(f"portable profile role name mismatch: {role}")
        for profile_key, role_key in (
            ("model_hint", "model"),
            ("reasoning_effort_hint", "model_reasoning_effort"),
            ("service_tier_hint", "service_tier"),
        ):
            if entry.get(profile_key) != document.get(role_key):
                fail(f"portable profile {profile_key} mismatch: {role}")
        sandbox = document.get("sandbox_mode")
        if entry.get("write_scope") != expected_write_scope.get(sandbox):
            fail(f"portable profile write scope mismatch: {role}")
        profile_policy = ROLE_PROFILE_POLICY[role]
        if entry.get("class") != profile_policy["class"]:
            fail(f"portable profile role class mismatch: {role}")
        if entry.get("eligibility") != profile_policy["eligibility"]:
            fail(f"portable profile role eligibility mismatch: {role}")
        for marker in profile_policy["routing_markers"]:
            if marker not in routing_policy:
                fail(f"routing policy no longer proves profile role {role}: {marker}")

    handoff = profile.get("handoff")
    expected_handoff = {
        "contract_reference": (
            "payload/skills/subagent-orchestrator/references/delegation-contracts.md"
        ),
        "state_bound": True,
        "context_default": "fresh",
        "children_are_leaves": True,
        "peer_messages": "none",
        "later_wave_requires_expansion_checkpoint": True,
        "operational_blocker_route": "report-next-owner-or-action",
        "user_facing_language": "user-preferred",
        "model_facing_language": "English",
    }
    if handoff != expected_handoff:
        fail("portable profile handoff contract mismatch")
    if not (ROOT / expected_handoff["contract_reference"]).is_file():
        fail("portable profile handoff reference is missing")
    if profile.get("adapter_requirements") != ADAPTER_REQUIREMENTS:
        fail("portable profile adapter requirements mismatch")
    if profile.get("unsupported_work_route") != "primary":
        fail("portable profile unsupported work route must remain primary")
    for route in expected_builtin_routes:
        for marker in (f"built-in `{route['id']}`", route["topology"]):
            if marker not in routing_policy:
                fail(f"routing policy no longer proves built-in route {route['id']}: {marker}")


def verify_manifest_builder() -> None:
    run(
        [
            sys.executable,
            "-B",
            str(ROOT / "build_manifest.py"),
            "--check",
        ]
    )


def run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        fail(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}{completed.stderr}"
        )
    return completed.stdout


def verify_hermetic_install() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        for language in ("en", "zh"):
            codex_home = Path(temporary) / f"codex-home-{language}"
            command = [
                sys.executable,
                "-B",
                str(ROOT / "install.py"),
                "--codex-home",
                str(codex_home),
                "--agents-language",
                language,
            ]
            check_output = run(command + ["--check"])
            if "WOULD_TOUCH" not in check_output:
                fail(f"{language}: empty-home preflight produced no touched-path hashes")
            run(command + ["--apply"])
            second_check = run(command + ["--check"])
            if "0 path(s) would change" not in second_check:
                fail(f"{language}: installer is not idempotent")
            validator = (
                codex_home
                / "skills"
                / "subagent-orchestrator"
                / "scripts"
                / "validate-routing-config.py"
            )
            run(
                [
                    sys.executable,
                    "-B",
                    str(validator),
                    "--codex-home",
                    str(codex_home),
                ]
            )
            tests = codex_home / "skills" / "subagent-orchestrator" / "tests"
            run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    str(tests),
                    "-p",
                    "test_*.py",
                ]
            )


def verify_package_tests() -> None:
    run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ]
    )


def verify_evaluation_smoke() -> None:
    run([sys.executable, "-B", "-m", "evaluation", "smoke"])


def main() -> int:
    try:
        verify_manifest()
        verify_manifest_builder()
        verify_portability()
        verify_package_tests()
        verify_evaluation_smoke()
        verify_hermetic_install()
    except (RuntimeError, OSError, UnicodeError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "PASS: manifest, portability, package tests, evaluation smoke, "
        "safe install, routing policy, and bundled tests"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
