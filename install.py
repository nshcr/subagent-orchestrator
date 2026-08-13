#!/usr/bin/env python3
"""Safely install the subagent-orchestrator package."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import tomllib


PACKAGE_ROOT = Path(__file__).resolve().parent
PAYLOAD_ROOT = PACKAGE_ROOT / "payload"
MANIFEST_PATH = PACKAGE_ROOT / "manifest.json"
SKILL_NAME = "subagent-orchestrator"
ROLES = (
    "evidence_tester",
    "boundary_mapper",
    "risk_reviewer",
    "risk_reviewer_max",
)
CONFIG_KEYS = (
    "enabled",
    "max_concurrent_threads_per_session",
    "interrupt_message",
    "default_subagent_model",
    "default_subagent_reasoning_effort",
)
STATE_RELATIVE = Path("skills") / SKILL_NAME / ".managed-package-state.json"
AGENTS_HEADING = "## Subagents and parallelism"
LEGACY_AGENTS_HEADING = "## 子代理与并行"
AGENTS_SECTION_FILES = {
    "en": "AGENTS.section.en.md",
    "zh": "AGENTS.section.zh.md",
}
LEGACY_GLOBAL_POLICY_SHA256 = (
    "37d9a41d324d5fbc259baf8f893288aaef70003b0259b6de95b6ab0a76e392e2"
)
ACCEPTED_STATE_MANIFESTS = {
    # Package states written by accepted predecessor bundles.
    "9eec02b6314206067d07b18596e9b3f9d454706652b235c827a32135bd99bce5",
    "481ad7ab43f2e4229489cd99052a2af50a30ac8b172ccc459c4c1f5efd6f2661",
    "498be7e574c86c9ab6c56c1f4ab09ffbcc237ad3a44d9b09975ead935f392742",
}
ACCEPTED_PREDECESSORS = {
    "skills/subagent-orchestrator/SKILL.md": {
        "b8f41ceebfe3efa0aad4485bd00f058e03b04bcd9a0ad5f83825d00b668ee8b2",
    },
    "skills/subagent-orchestrator/scripts/validate-routing-config.py": {
        "8adb983c172bfdf8f839a12cd3c92b014477203a955259103eb4bda1f85b7eb3",
    },
    "skills/subagent-orchestrator/tests/test_validate_routing_config.py": {
        "346745466fae4ab43c51560812c59df6045764dbbc7cd1d5f56f07d0cd9fb358",
    },
    "skills/subagent-orchestrator/tests/fixtures/lifecycle-trace.json": {
        "2ed78edc9d5513135fe9da271b1b5286b38d80e7e00db88d6d118e7d35f494cf",
    },
}


class InstallError(RuntimeError):
    """A fail-closed preflight or installation error."""


@dataclass(frozen=True)
class PlannedWrite:
    relative: str
    path: Path
    content: bytes
    managed_hash: str
    expected_prior_exists: bool
    expected_prior_sha256: str | None


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_json_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    )


def load_manifest() -> dict:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise InstallError(f"package manifest is unreadable: {error}") from error
    declared = manifest.get("files")
    if not isinstance(declared, list):
        raise InstallError("package manifest has no files list")
    for item in declared:
        relative = item.get("path", "")
        path = PACKAGE_ROOT / relative
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise InstallError(f"unsafe manifest path: {relative!r}")
        if not path.is_file():
            raise InstallError(f"manifest file is missing: {relative}")
        actual = sha256_bytes(path.read_bytes())
        if actual != item.get("sha256"):
            raise InstallError(f"manifest hash mismatch: {relative}")
    return manifest


def validate_codex_home(raw: Path) -> Path:
    if not raw.is_absolute():
        raise InstallError("--codex-home must be an absolute path")
    resolved = raw.resolve(strict=False)
    if resolved == Path(resolved.anchor):
        raise InstallError("refusing to use a filesystem root as --codex-home")
    return resolved


def read_state(codex_home: Path) -> dict[str, str]:
    path = codex_home / STATE_RELATIVE
    content = safe_existing_bytes(path, codex_home)
    if content is None:
        return {}
    try:
        document = json.loads(content.decode())
    except (UnicodeError, ValueError) as error:
        raise InstallError(f"managed state is unreadable: {error}") from error
    expected_document_keys = {
        "format_version",
        "package_id",
        "package_manifest_sha256",
        "managed_hashes",
    }
    if not isinstance(document, dict) or set(document) != expected_document_keys:
        raise InstallError("managed state has an unknown document schema")
    if document.get("package_id") != SKILL_NAME:
        raise InstallError("managed state package identity mismatch")
    if document.get("format_version") != 1:
        raise InstallError("managed state format_version must be 1")
    lineage = document.get("package_manifest_sha256")
    accepted_lineage = {
        sha256_bytes(MANIFEST_PATH.read_bytes()),
        *ACCEPTED_STATE_MANIFESTS,
    }
    if lineage not in accepted_lineage:
        raise InstallError("managed state manifest lineage is not accepted")
    managed = document.get("managed_hashes")
    if not isinstance(managed, dict) or not all(
        isinstance(key, str)
        and isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value)
        for key, value in managed.items()
    ):
        raise InstallError("managed state has an invalid managed_hashes map")
    expected_domain = expected_managed_domain()
    if set(managed) != expected_domain:
        unexpected = sorted(set(managed) - expected_domain)
        missing = sorted(expected_domain - set(managed))
        raise InstallError(
            "managed state owned-key domain mismatch; "
            f"missing={missing}; unexpected={unexpected}"
        )
    verify_recorded_state(codex_home, managed)
    return managed


def expected_managed_domain() -> set[str]:
    domain = {
        "AGENTS.md#subagent-policy",
        "config.toml#agents",
        *(f"agents/{role}.toml" for role in ROLES),
    }
    skill_source = PAYLOAD_ROOT / "skills" / SKILL_NAME
    for source in skill_source.rglob("*"):
        if not source.is_file() or source.name == ".DS_Store" or source.suffix == ".pyc":
            continue
        domain.add(
            str(Path("skills") / SKILL_NAME / source.relative_to(skill_source))
        )
    return domain


def verify_recorded_state(codex_home: Path, managed: dict[str, str]) -> None:
    agents_content = safe_existing_bytes(codex_home / "AGENTS.md", codex_home)
    if agents_content is None:
        raise InstallError("managed state target is missing: AGENTS.md")
    try:
        agents_text = agents_content.decode()
    except UnicodeError as error:
        raise InstallError(f"managed AGENTS.md is unreadable: {error}") from error
    agents_policy = agents_policy_section(agents_text)
    if agents_policy is None:
        raise InstallError("managed state target section is missing: AGENTS.md")
    _, _, agents_body = agents_policy
    current_hashes = {
        "AGENTS.md#subagent-policy": sha256_bytes(agents_body.encode()),
    }

    config_content = safe_existing_bytes(codex_home / "config.toml", codex_home)
    if config_content is None:
        raise InstallError("managed state target is missing: config.toml")
    try:
        config_document = tomllib.loads(config_content.decode())
    except (UnicodeError, tomllib.TOMLDecodeError) as error:
        raise InstallError(f"managed config.toml is unreadable: {error}") from error
    current_hashes["config.toml#agents"] = canonical_json_hash(
        config_projection(config_document)
    )

    for relative in sorted(expected_managed_domain() - set(current_hashes)):
        content = safe_existing_bytes(codex_home / relative, codex_home)
        if content is None:
            raise InstallError(f"managed state target is missing: {relative}")
        current_hashes[relative] = sha256_bytes(content)
    mismatches = sorted(
        key for key, expected in managed.items() if current_hashes.get(key) != expected
    )
    if mismatches:
        raise InstallError(
            "managed state does not match current targets: " + ", ".join(mismatches)
        )


def render_role(template: Path, skill_path: Path) -> bytes:
    text = template.read_text(encoding="utf-8")
    if text.count("{{SKILL_PATH}}") != 1:
        raise InstallError(f"role template must contain one SKILL_PATH token: {template}")
    rendered = text.replace("{{SKILL_PATH}}", str(skill_path))
    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as error:
        raise InstallError(f"rendered role is invalid TOML: {template}: {error}") from error
    return rendered.encode()


def section_span(text: str, heading: str) -> tuple[int, int] | None:
    matches = list(re.finditer(rf"(?m)^{re.escape(heading)}\s*$", text))
    if len(matches) > 1:
        raise InstallError(f"multiple {heading!r} sections are ambiguous")
    if not matches:
        return None
    start = matches[0].start()
    following = re.search(r"(?m)^##\s", text[matches[0].end():])
    end = matches[0].end() + following.start() if following else len(text)
    return start, end


def section_body(text: str, heading: str) -> str:
    span = section_span(text, heading)
    if span is None:
        return ""
    start, end = span
    return text[start:end].split("\n", 1)[1].strip()


def agents_policy_section(text: str) -> tuple[str, tuple[int, int], str] | None:
    found = []
    for heading in (AGENTS_HEADING, LEGACY_AGENTS_HEADING):
        span = section_span(text, heading)
        if span is not None:
            found.append((heading, span, section_body(text, heading)))
    if len(found) > 1:
        raise InstallError("multiple managed AGENTS.md policy sections are ambiguous")
    return found[0] if found else None


def merge_agents(
    existing: str,
    desired_section: str,
    state: dict[str, str],
) -> tuple[str, str]:
    desired_policy = agents_policy_section(desired_section)
    if desired_policy is None:
        raise InstallError("selected AGENTS policy template is missing its managed section")
    _, _, desired_body = desired_policy
    desired_hash = sha256_bytes(desired_body.encode())
    existing_policy = agents_policy_section(existing)
    if existing_policy is None:
        separator = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
        return existing + separator + desired_section.rstrip() + "\n", desired_hash
    _, span, current_body = existing_policy
    current_hash = sha256_bytes(current_body.encode())
    state_key = "AGENTS.md#subagent-policy"
    known_predecessor = current_hash == LEGACY_GLOBAL_POLICY_SHA256
    if (
        current_hash != desired_hash
        and state.get(state_key) != current_hash
        and not known_predecessor
    ):
        raise InstallError("AGENTS.md managed policy section conflicts with the package")
    if current_hash == desired_hash:
        return existing, desired_hash
    start, end = span
    replacement = desired_section.rstrip() + "\n\n"
    return existing[:start] + replacement + existing[end:].lstrip("\n"), desired_hash


def find_agents_table(text: str) -> tuple[int, int] | None:
    matches = list(re.finditer(r"(?m)^\[agents\]\s*(?:#.*)?$", text))
    if len(matches) > 1:
        raise InstallError("multiple [agents] tables are ambiguous")
    if not matches:
        return None
    start = matches[0].start()
    following = re.search(r"(?m)^\[", text[matches[0].end():])
    end = matches[0].end() + following.start() if following else len(text)
    return start, end


def config_projection(document: dict) -> dict:
    agents = document.get("agents", {})
    if not isinstance(agents, dict):
        return {}
    return {key: agents[key] for key in CONFIG_KEYS if key in agents}


def merge_config(
    existing: str,
    desired_snippet: str,
    state: dict[str, str],
) -> tuple[str, str]:
    try:
        desired_document = tomllib.loads(desired_snippet)
        existing_document = tomllib.loads(existing) if existing.strip() else {}
    except tomllib.TOMLDecodeError as error:
        raise InstallError(f"config.toml cannot be merged safely: {error}") from error
    desired = config_projection(desired_document)
    if set(desired) != set(CONFIG_KEYS):
        raise InstallError("package config snippet does not own the expected [agents] keys")
    current = config_projection(existing_document)
    current_hash = canonical_json_hash(current)
    desired_hash = canonical_json_hash(desired)
    state_key = "config.toml#agents"
    conflicts = {
        key: value
        for key, value in current.items()
        if key in desired and value != desired[key]
    }
    if conflicts and state.get(state_key) != current_hash:
        raise InstallError(
            "config.toml has conflicting package-owned [agents] values: "
            + ", ".join(sorted(conflicts))
        )
    span = find_agents_table(existing)
    if span is None:
        if "agents" in existing_document:
            raise InstallError("config.toml defines agents without a mergeable [agents] table")
        separator = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
        return existing + separator + desired_snippet.rstrip() + "\n", desired_hash
    start, end = span
    region = existing[start:end]
    for key in CONFIG_KEYS:
        line = f"{key} = {json.dumps(desired[key]) if isinstance(desired[key], str) else str(desired[key]).lower()}"
        pattern = re.compile(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*=.*$")
        matches = list(pattern.finditer(region))
        if len(matches) > 1:
            raise InstallError(f"config.toml has duplicate [agents].{key}")
        if matches:
            region = pattern.sub(line, region, count=1)
        else:
            region = region.rstrip() + "\n" + line + "\n"
    merged = existing[:start] + region + existing[end:]
    try:
        merged_document = tomllib.loads(merged)
    except tomllib.TOMLDecodeError as error:
        raise InstallError(f"merged config.toml is invalid: {error}") from error
    if config_projection(merged_document) != desired:
        raise InstallError("merged config.toml does not match the package projection")
    return merged, desired_hash


def safe_existing_bytes(path: Path, codex_home: Path) -> bytes | None:
    current = codex_home
    relative_parts = path.relative_to(codex_home).parts
    for part in relative_parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise InstallError(f"refusing to traverse symlink: {current}")
    if path.is_symlink():
        raise InstallError(f"refusing to overwrite symlink: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise InstallError(f"target is not a regular file: {path}")
    return path.read_bytes()


def allow_owned_replacement(
    relative: str,
    current: bytes,
    desired: bytes,
    state: dict[str, str],
) -> None:
    current_hash = sha256_bytes(current)
    if current == desired:
        return
    if state.get(relative) == current_hash:
        return
    if current_hash in ACCEPTED_PREDECESSORS.get(relative, set()):
        return
    raise InstallError(f"target conflicts with package ownership: {relative}")


def planned_write(
    relative: str,
    path: Path,
    content: bytes,
    managed_hash: str,
    prior: bytes | None,
) -> PlannedWrite:
    return PlannedWrite(
        relative=relative,
        path=path,
        content=content,
        managed_hash=managed_hash,
        expected_prior_exists=prior is not None,
        expected_prior_sha256=sha256_bytes(prior) if prior is not None else None,
    )


def verify_precondition(plan: PlannedWrite, codex_home: Path) -> None:
    current = safe_existing_bytes(plan.path, codex_home)
    current_exists = current is not None
    current_hash = sha256_bytes(current) if current is not None else None
    if (
        current_exists != plan.expected_prior_exists
        or current_hash != plan.expected_prior_sha256
    ):
        expected = plan.expected_prior_sha256 or "<absent>"
        actual = current_hash or "<absent>"
        raise InstallError(
            f"target drifted after preflight: {plan.relative}; "
            f"expected {expected}, got {actual}"
        )


def verify_all_preconditions(
    plans: list[PlannedWrite],
    codex_home: Path,
) -> None:
    """Bind every planned target before the first write."""
    for plan in plans:
        verify_precondition(plan, codex_home)


def plan_install(
    codex_home: Path,
    agents_language: str,
) -> tuple[list[PlannedWrite], dict[str, str]]:
    load_manifest()
    if agents_language not in AGENTS_SECTION_FILES:
        raise InstallError(f"unsupported AGENTS policy language: {agents_language}")
    state = read_state(codex_home)
    plans: list[PlannedWrite] = []
    managed_hashes: dict[str, str] = {}

    agents_path = codex_home / "AGENTS.md"
    agents_existing = safe_existing_bytes(agents_path, codex_home)
    agents_text = agents_existing.decode() if agents_existing is not None else ""
    agents_merged, agents_hash = merge_agents(
        agents_text,
        (PAYLOAD_ROOT / AGENTS_SECTION_FILES[agents_language]).read_text(
            encoding="utf-8"
        ),
        state,
    )
    managed_hashes["AGENTS.md#subagent-policy"] = agents_hash
    agents_desired = agents_merged.encode()
    if agents_existing != agents_desired:
        plans.append(
            planned_write(
                "AGENTS.md",
                agents_path,
                agents_desired,
                agents_hash,
                agents_existing,
            )
        )

    config_path = codex_home / "config.toml"
    config_existing = safe_existing_bytes(config_path, codex_home)
    config_text = config_existing.decode() if config_existing is not None else ""
    config_merged, config_hash = merge_config(
        config_text,
        (PAYLOAD_ROOT / "config.agents.toml").read_text(encoding="utf-8"),
        state,
    )
    managed_hashes["config.toml#agents"] = config_hash
    config_desired = config_merged.encode()
    if config_existing != config_desired:
        plans.append(
            planned_write(
                "config.toml",
                config_path,
                config_desired,
                config_hash,
                config_existing,
            )
        )

    skill_path = codex_home / "skills" / SKILL_NAME / "SKILL.md"
    for role in ROLES:
        relative = f"agents/{role}.toml"
        desired = render_role(PAYLOAD_ROOT / relative, skill_path)
        target = codex_home / relative
        current = safe_existing_bytes(target, codex_home)
        if current is not None:
            allow_owned_replacement(relative, current, desired, state)
        managed_hash = sha256_bytes(desired)
        managed_hashes[relative] = managed_hash
        if current != desired:
            plans.append(
                planned_write(relative, target, desired, managed_hash, current)
            )
    skill_source = PAYLOAD_ROOT / "skills" / SKILL_NAME
    for source in sorted(skill_source.rglob("*")):
        if not source.is_file() or source.name == ".DS_Store" or source.suffix == ".pyc":
            continue
        relative = str(Path("skills") / SKILL_NAME / source.relative_to(skill_source))
        desired = source.read_bytes()
        target = codex_home / relative
        current = safe_existing_bytes(target, codex_home)
        if current is not None:
            allow_owned_replacement(relative, current, desired, state)
        managed_hash = sha256_bytes(desired)
        managed_hashes[relative] = managed_hash
        if current != desired:
            plans.append(
                planned_write(relative, target, desired, managed_hash, current)
            )

    state_document = {
        "format_version": 1,
        "package_id": SKILL_NAME,
        "package_manifest_sha256": sha256_bytes(MANIFEST_PATH.read_bytes()),
        "managed_hashes": managed_hashes,
    }
    state_content = (json.dumps(state_document, indent=2, sort_keys=True) + "\n").encode()
    state_path = codex_home / STATE_RELATIVE
    current_state = safe_existing_bytes(state_path, codex_home)
    if current_state != state_content:
        plans.append(
            planned_write(
                str(STATE_RELATIVE),
                state_path,
                state_content,
                sha256_bytes(state_content),
                current_state,
            )
        )
    return plans, managed_hashes


def atomic_write(
    plan: PlannedWrite,
    codex_home: Path,
) -> None:
    path = plan.path
    content = plan.content
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        else:
            os.chmod(temporary, 0o644)
        # Recheck after staging and immediately before replacement. This catches
        # target or parent-path drift that occurs after the all-target gate.
        verify_precondition(plan, codex_home)
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply_plans(
    plans: list[PlannedWrite],
    codex_home: Path,
) -> list[tuple[str, str]]:
    """Apply a preflighted plan with an all-target gate and per-file rechecks."""
    verify_all_preconditions(plans, codex_home)
    touched = []
    for plan in plans:
        atomic_write(plan, codex_home)
        actual = sha256_bytes(plan.path.read_bytes())
        if actual != sha256_bytes(plan.content):
            raise InstallError(f"post-write hash mismatch: {plan.relative}")
        touched.append((plan.relative, actual))
    return touched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", required=True, type=Path, metavar="ABS")
    parser.add_argument(
        "--agents-language",
        required=True,
        choices=sorted(AGENTS_SECTION_FILES),
        help="language for the managed AGENTS.md policy section",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="preflight without writes")
    action.add_argument("--apply", action="store_true", help="apply the preflighted writes")
    args = parser.parse_args()
    try:
        codex_home = validate_codex_home(args.codex_home)
        plans, _ = plan_install(codex_home, args.agents_language)
        if args.check:
            for plan in plans:
                print(f"WOULD_TOUCH {plan.relative} {sha256_bytes(plan.content)}")
            print(f"PASS: preflight complete; {len(plans)} path(s) would change")
            return 0
        for relative, actual in apply_plans(plans, codex_home):
            print(f"TOUCHED {relative} {actual}")
        print(f"PASS: installed {len(plans)} changed path(s)")
        return 0
    except (InstallError, OSError, UnicodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
