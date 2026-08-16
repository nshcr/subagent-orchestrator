#!/usr/bin/env python3
"""Safely install the subagent-orchestrator package."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass, replace
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import tomllib
from typing import Callable, Iterator


PACKAGE_ROOT = Path(__file__).resolve().parent
PAYLOAD_ROOT = PACKAGE_ROOT / "payload"
MANIFEST_PATH = PACKAGE_ROOT / "manifest.json"
MIGRATION_CATALOG_PATH = PACKAGE_ROOT / "install-migrations.json"
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
JOURNAL_RELATIVE = Path("skills") / SKILL_NAME / ".install-transaction.json"
APPLY_RECEIPT_JOURNAL_RELATIVE = (
    Path("skills") / SKILL_NAME / ".receipt-apply-transaction.json"
)
RESTORE_JOURNAL_RELATIVE = (
    Path("skills") / SKILL_NAME / ".receipt-restore-transaction.json"
)
RESTORE_VAULT_RELATIVE = Path("skills") / SKILL_NAME / ".restore-vault"
RESTORE_RECEIPTS_RELATIVE = Path("skills") / SKILL_NAME / ".restore-receipts"
QUARANTINE_RELATIVE = Path("skills") / SKILL_NAME / ".retired"
STAGING_RELATIVE = Path("skills") / SKILL_NAME / ".retirement-receipts"
WRITE_RECOVERY_RELATIVE = Path("skills") / SKILL_NAME / ".write-recovery"
AGENTS_HEADING = "## Subagents and parallelism"
LEGACY_AGENTS_HEADING = "## 子代理与并行"
AGENTS_SECTION_FILES = {
    "en": "AGENTS.section.en.md",
    "zh": "AGENTS.section.zh.md",
}
ACCEPTED_GLOBAL_POLICY_SHA256 = {
    "5274ac947738eeaddfa4e8c1c4538192ea5db17be042a19b1feca4e13cc45fe3",
    "50702c458d4adf38d2b4b86d578fd5b4ef36cd43ef6dd0306640b491061e09f3",
    "14d15f56754528d65d25a2434f0dfc88587c63b533309164d83433d718295bd4",
    "6cc3694505f0c58cc3fab99971a93aa2cf2204ebcf44963cdb039a81b60556f4",
    "57ac581a53881ce2152755d425c4e4c9e3608c29fd4257d500e1c7677aca467f",
    "37d9a41d324d5fbc259baf8f893288aaef70003b0259b6de95b6ab0a76e392e2",
    "f4bfedfca74f3c0b071329655002f788b08e0bbd8207ea549a4496d26f41068c",
    "8c25829e558be9a16ed32b0ff1ee21d2b6bc6d017c503e8953c9d80379e2ca7f",
    "a69936c2e62ed151ec70d50f902578f8bc46134e8e4d0a19ef0f52f64c8f9081",
    "76bafc03f3710f20b12270b2e289889092c5a0babf53b4b03a52962120d2045e",
    "c8ece2451004efe55738e7763a5048a368331e5a02c2b6ad993eb5260a33e7d5",
    "82ea8d7682749de120a9b332bfb415362a9e99bba9377e283db54711e0916894",
}
ACCEPTED_STATE_MANIFESTS = {
    # Package states written by accepted predecessor bundles.
    "8d79376f51a67743dccd1df29274d6e01d0884777a7fcf2deb0b04cbfcdccbbb",
    "9faba5962d104aa62c2b0484ba54b08856e326c1cd3d8ca74617fd1fe639738c",
    "965615dbeae99d751a6cde94544d93b36405ed79d85d4f611bc7336209b8379c",
    "20bef171c9a9e6390c9fdbdde90094497c76e8291090f736fe3ea206935bdbe2",
    "9eec02b6314206067d07b18596e9b3f9d454706652b235c827a32135bd99bce5",
    "481ad7ab43f2e4229489cd99052a2af50a30ac8b172ccc459c4c1f5efd6f2661",
    "498be7e574c86c9ab6c56c1f4ab09ffbcc237ad3a44d9b09975ead935f392742",
    "ff5b4d05d03027b2808862113e6706876193cf866214f9dfb0bba0b1d937714b",
}
DIRECT_PREDECESSOR_INSTALL_CONTRACT = (
    "91f9f7d927aa8776e83f4f0f1c4e813d3af2fdc42090782e998e06befd62d1fe"
)
DIRECT_PREDECESSOR_POLICY_SHA256 = {
    "c8ece2451004efe55738e7763a5048a368331e5a02c2b6ad993eb5260a33e7d5",
    "82ea8d7682749de120a9b332bfb415362a9e99bba9377e283db54711e0916894",
}
DIRECT_PREDECESSOR_MANAGED_HASHES = {
    "config.toml#agents": "8a23698e958a3496e9fc74b9e93f999b18bfb17e2ace0f9f5f45e75e5b68bdf0",
    "skills/subagent-orchestrator/SKILL.md": "e1fbf5508bb4491680245c21d2bf0524897e0983f35307836f91df2cf66ad61d",
    "skills/subagent-orchestrator/agents/openai.yaml": "ea4f34eb93016c580f09fd1e22c6920a78dfe51aeb43e9343ef051b4cc8479a3",
    "skills/subagent-orchestrator/references/delegation-contracts.md": "8da7a0d23855626d53bf834f4bb2020f72c13457fc12bceefbf3f1684e271293",
    "skills/subagent-orchestrator/references/evaluation-policy.md": "86c455304eb053bdaf6255dc9185b455a30a96d1f1958ef633afbd92dfdd5cb7",
    "skills/subagent-orchestrator/references/routing-policy.md": "7ad71e32f2cd794fb0371514fbb5c19c4a6df5759e54f3958a9a69d4d4c5a152",
    "skills/subagent-orchestrator/scripts/lifecycle_conformance.py": "99ccc18991fa87281ab7656385f9b53962055f80052dc4819eccc1507222dc05",
    "skills/subagent-orchestrator/scripts/validate-routing-config.py": "1d8ac347fea0a5c25109239c4120452eb637fa8191317188299a4d2f390bb659",
    "skills/subagent-orchestrator/tests/fixtures/lifecycle-authority-receipts.json": "f2f8ca311501ba43a7414e5c753724cd4e4792054713bddcf93cca031ee8db98",
    "skills/subagent-orchestrator/tests/fixtures/lifecycle-trace.json": "a7d4c0a095f585bf2c8e06ddac6622a4d244162511ce1a57e3e9826767480abb",
    "skills/subagent-orchestrator/tests/test_lifecycle_conformance.py": "29925d31fdb995d15d2fb359762c3ccd4f7596ec804acef85d3efa999567466e",
    "skills/subagent-orchestrator/tests/test_validate_routing_config.py": "c450daa0fd42d0bd0cf41242d22bb9e9e4367c6200bab8d55f8229efd84e6049",
}
ACCEPTED_PREDECESSORS = {
    "skills/subagent-orchestrator/SKILL.md": {
        "36df8d88592525fba7749b2618254751ba0f07eec4f61d4aea2533ae2aa3d112",
        "99ac84463ff80ac6b5fd0131e0d36dd96efadc0484d72f975688758c44936972",
        "b8f41ceebfe3efa0aad4485bd00f058e03b04bcd9a0ad5f83825d00b668ee8b2",
        "b82d2905847dc376bb99555b1d49675ede80bf2050d38ee87f11218e3641f4bc",
        "6fd3b830a80a72d2c07b89cea8a75e86560ba7a4072e3e8bafbed9270367d88c",
        "e1fbf5508bb4491680245c21d2bf0524897e0983f35307836f91df2cf66ad61d",
    },
    "skills/subagent-orchestrator/references/routing-policy.md": {
        "ac944ba5ec777cd1bf187ced8347332a051b09de8ce23f4b49c4edaaccb0c1d3",
        "2b50c5bedd653476710d490de5b77784d90cd6d8f0b1e90681357c657aadcde0",
        "60848931f487bfb55b576394e3fb6ba63d27dd6ad69736ab18bb9b2635a83465",
        "4bcceebe7e58e95ace680d45602ef9a37cc9eb936c86a6d4e55a37f52da5c517",
        "7ad71e32f2cd794fb0371514fbb5c19c4a6df5759e54f3958a9a69d4d4c5a152",
    },
    "skills/subagent-orchestrator/references/delegation-contracts.md": {
        "6831283a4643c1d7a538f3c02e36ee024d9188b87e6aa4042ec382cbf1635676",
        "842306b06c7501bdda207ed91357e16bddf3da17a3bf83822c29977e3640867f",
        "792b6dfb180571f33bf81fc2ccc1c5dd55ffb7c9c1fb28dde4ed90e9075385c5",
        "89e00d1000a619c4b6e33cddf65ef52d067609a9eee8a5dd605d80abcae1b764",
        "8da7a0d23855626d53bf834f4bb2020f72c13457fc12bceefbf3f1684e271293",
    },
    "skills/subagent-orchestrator/references/evaluation-policy.md": {
        "59280215f90eee72eb1463d7625a034c309e6545727d3b08005a8082f3b01354",
        "aea59b820434f7e3022aa7db93a6d13b4c5f6c7be954e5067bd4d7fd888f0173",
        "86c455304eb053bdaf6255dc9185b455a30a96d1f1958ef633afbd92dfdd5cb7",
    },
    "skills/subagent-orchestrator/scripts/validate-routing-config.py": {
        "47b4651594044d35eaba1549ec639d30ec39ae11328cb1dcd21839a983d326f8",
        "294f0e4af60aa03d417b13a5bc011bc69e36c56777cebf90c3ce1893cf4465bb",
        "8adb983c172bfdf8f839a12cd3c92b014477203a955259103eb4bda1f85b7eb3",
        "450fab5a3a4a0b0b2d143892dd1c747bbe07951550268543b3cfc10dd8c10fee",
        "1b3ff4b091d23d188e31a44ddf20169a340edc24d14ba5adf2176033a00d014a",
        "1d8ac347fea0a5c25109239c4120452eb637fa8191317188299a4d2f390bb659",
    },
    "skills/subagent-orchestrator/tests/test_validate_routing_config.py": {
        "2b39e4e8cfac0fd266d1d7ed7e6de550180cfff47c071e84a2614a107d7640d6",
        "346745466fae4ab43c51560812c59df6045764dbbc7cd1d5f56f07d0cd9fb358",
        "c450daa0fd42d0bd0cf41242d22bb9e9e4367c6200bab8d55f8229efd84e6049",
    },
    "skills/subagent-orchestrator/tests/fixtures/lifecycle-trace.json": {
        "83c8ab6e54b7cb9a6ecb33edcdf2447b3a54c62a0c93ca252c1c59767ed586f5",
        "54c26f25b74909e8df7aa3aedea90926b6a0a7283bc4be8a940b6fdd018f8e42",
        "2ed78edc9d5513135fe9da271b1b5286b38d80e7e00db88d6d118e7d35f494cf",
        "9d5df95bc2a2baaa0548e87071fc499adcd23cb4b601685febb4e4fada4dd95c",
        "8850e1650822c24a47e72218ea759a9a0cc4b08b732199e7ccd0eb5f92534cac",
        "a7d4c0a095f585bf2c8e06ddac6622a4d244162511ce1a57e3e9826767480abb",
    },
    "skills/subagent-orchestrator/tests/fixtures/lifecycle-authority-receipts.json": {
        "aeccd7a24408946c0f9acb4c08d1d33c039ae8ff5f34dcffb998d82bede817ba",
        "0518e099d599ef3f20a2e2e764bb50c6361261309c510d32ccecb91fc204d91b",
        "f2f8ca311501ba43a7414e5c753724cd4e4792054713bddcf93cca031ee8db98",
    },
    "skills/subagent-orchestrator/scripts/lifecycle_conformance.py": {
        "3f48548fcd7feae76687e44f84f466d86d941224b54958b4c4df15662f4b1eef",
        "d1ffe6fb9a7663aa80e728efb0cb6dba208e2c14990a0fb926cbc5bf63903a49",
        "861c386725be6c784b62e5b0c05cde4bbcdbc7a1c66416084d6bf25ff1a4910a",
        "4f0ee07cd211e300d1a7e8403611d227bf7cc34d9143b4041201ae0f8c591add",
        "62fd8158fd9b0b2c8ac765df3f0665bf92e62e9bf3e278e0c618fd4005a7376e",
        "06cb869d981a0b76fbcd018fda95541af39b62a902fde2a2721d6743f457c2b2",
        "b6e870d6f1d6b906e2bad4fc5114fad647a5e67f13693732af5aaa7fa4db3343",
        "6c416cb314c95aa3980f2a0a83d008a341d82e4e394fdd84454438812aa123f5",
        "5cb331a096730e13e36f23b88ef06a4a81c889ea653e0dfcef348267bf64c55c",
        "24c6343f756da99267c674ed5ffe46d9ef821f467a0885395c6752b2ee853484",
        "99ccc18991fa87281ab7656385f9b53962055f80052dc4819eccc1507222dc05",
        "5f098953bfd936823b5511c6a8b363c5912d255c35b4d83ecacd9b90acd4da62",
    },
    "skills/subagent-orchestrator/tests/test_lifecycle_conformance.py": {
        "e9a9d5046035c08040780596a0530ccfd1bb2d0d67a2031ed4f7f8e9e8d1f9ca",
        "e5db6b19f5de2fe41f44af5468409891f3f5aaf54563ff77dc8e03ee0c38ac0c",
        "801a39220ea8f0fbd9ac18ac5bf6e618fc5ebd0080066484dc1d1434060da00a",
        "a6c97013b5c0d7d56ee617f14d77e2b1a55f3f09d7921551bb169763a70065f8",
        "29925d31fdb995d15d2fb359762c3ccd4f7596ec804acef85d3efa999567466e",
    },
}


class InstallError(RuntimeError):
    """A fail-closed preflight or installation error."""


@dataclass(frozen=True)
class PlannedWrite:
    relative: str
    path: Path
    content: bytes | None
    managed_hash: str | None
    expected_prior_exists: bool
    expected_prior_sha256: str | None
    expected_prior_mode: int | None
    managed_key: str | None = None
    quarantine_path: Path | None = None
    staging_path: Path | None = None
    write_recovery_path: Path | None = None

    @property
    def operation(self) -> str:
        if self.content is not None:
            return "write"
        return "quarantine" if self.quarantine_path is not None else "invalid"

    @property
    def desired_sha256(self) -> str | None:
        return sha256_bytes(self.content) if self.content is not None else None

    @property
    def desired_mode(self) -> int | None:
        if self.content is None:
            return None
        return self.expected_prior_mode if self.expected_prior_exists else 0o644


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def same_physical_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return False


def rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically move a path without replacing an existing destination."""
    library = ctypes.CDLL(None, use_errno=True)
    encoded_source = os.fsencode(source)
    encoded_destination = os.fsencode(destination)
    if sys.platform == "darwin":
        rename = library.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(encoded_source, encoded_destination, 0x00000004)
    elif sys.platform.startswith("linux") and hasattr(library, "renameat2"):
        rename = library.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(-100, encoded_source, -100, encoded_destination, 1)
    else:
        raise InstallError("atomic no-replace rename is unsupported on this platform")
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise InstallError(f"staging destination already exists: {destination}")
    raise OSError(
        error_number,
        os.strerror(error_number),
        str(source),
        str(destination),
    )


def canonical_json_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    )


def strict_json_loads(content: str, label: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise InstallError(f"{label} contains duplicate key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(content, object_pairs_hook=reject_duplicates)
    except InstallError:
        raise
    except ValueError as error:
        raise InstallError(f"{label} is invalid JSON: {error}") from error


def load_manifest() -> dict:
    try:
        content = MANIFEST_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InstallError(f"package manifest is unreadable: {error}") from error
    manifest = strict_json_loads(content, "package manifest")
    if not isinstance(manifest, dict):
        raise InstallError("package manifest has an unknown schema")
    declared = manifest.get("files")
    if not isinstance(declared, list):
        raise InstallError("package manifest has no files list")
    declared_paths = set()
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
        declared_paths.add(relative)
    migration_relative = "install-migrations.json"
    if migration_relative not in declared_paths:
        raise InstallError("package manifest does not declare install-migrations.json")
    return manifest


def load_migration_catalog() -> dict:
    try:
        content = MIGRATION_CATALOG_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InstallError(f"install migration catalog is unreadable: {error}") from error
    document = strict_json_loads(content, "install migration catalog")
    expected_keys = {
        "format_version",
        "package_id",
        "accepted_install_contracts",
        "retired_paths",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise InstallError("install migration catalog has an unknown schema")
    if document.get("format_version") != 1:
        raise InstallError("install migration catalog format_version must be 1")
    if document.get("package_id") != SKILL_NAME:
        raise InstallError("install migration catalog package identity mismatch")
    accepted = document.get("accepted_install_contracts")
    if not isinstance(accepted, list) or not all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in accepted
    ) or len(set(accepted)) != len(accepted):
        raise InstallError("install migration catalog has invalid contract lineage")
    retired = document.get("retired_paths")
    if not isinstance(retired, list):
        raise InstallError("install migration catalog retired_paths must be a list")
    seen = set()
    current_domain = expected_managed_domain()
    for entry in retired:
        if not isinstance(entry, dict) or set(entry) != {"path", "accepted_sha256"}:
            raise InstallError("install migration catalog has an invalid retirement entry")
        relative = entry.get("path")
        hashes = entry.get("accepted_sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative in current_domain
            or relative in {str(STATE_RELATIVE), str(JOURNAL_RELATIVE)}
            or Path(relative).is_relative_to(QUARANTINE_RELATIVE)
            or Path(relative).is_relative_to(STAGING_RELATIVE)
            or relative in seen
        ):
            raise InstallError(f"unsafe or duplicate retired path: {relative!r}")
        if not isinstance(hashes, list) or not hashes or not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in hashes
        ) or len(set(hashes)) != len(hashes):
            raise InstallError(f"invalid accepted hashes for retired path: {relative}")
        seen.add(relative)
    return document


def retired_path_hashes(catalog: dict) -> dict[str, set[str]]:
    return {
        entry["path"]: set(entry["accepted_sha256"])
        for entry in catalog["retired_paths"]
    }


def install_contract_sha256(catalog: dict | None = None) -> str:
    """Hash only install-relevant inputs, not release docs/tests/CI metadata."""
    catalog = catalog or load_migration_catalog()
    sources = {}
    for relative in [
        *(f"payload/{name}" for name in AGENTS_SECTION_FILES.values()),
        "payload/config.agents.toml",
        *(f"payload/agents/{role}.toml" for role in ROLES),
    ]:
        sources[relative] = sha256_bytes((PACKAGE_ROOT / relative).read_bytes())
    skill_source = PAYLOAD_ROOT / "skills" / SKILL_NAME
    for source in sorted(skill_source.rglob("*")):
        if not source.is_file() or source.name == ".DS_Store" or source.suffix == ".pyc":
            continue
        relative = str(source.relative_to(PACKAGE_ROOT))
        sources[relative] = sha256_bytes(source.read_bytes())
    contract = {
        "format_version": 2,
        "package_id": SKILL_NAME,
        "config_keys": list(CONFIG_KEYS),
        "roles": list(ROLES),
        "managed_sources": sources,
        "retired_paths": catalog["retired_paths"],
    }
    return canonical_json_hash(contract)


def validate_codex_home(raw: Path) -> Path:
    if not raw.is_absolute():
        raise InstallError("--codex-home must be an absolute path")
    if raw.is_symlink():
        raise InstallError(f"--codex-home is a symlink: {raw}")
    resolved = raw.resolve(strict=False)
    if resolved == Path(resolved.anchor):
        raise InstallError("refusing to use a filesystem root as --codex-home")
    return resolved


def current_managed_state_profiles(codex_home: Path) -> list[dict[str, str]]:
    skill_path = codex_home / "skills" / SKILL_NAME / "SKILL.md"
    common = {
        "config.toml#agents": canonical_json_hash(
            config_projection(
                tomllib.loads(
                    (PAYLOAD_ROOT / "config.agents.toml").read_text(encoding="utf-8")
                )
            )
        ),
        **{
            f"agents/{role}.toml": sha256_bytes(
                render_role(PAYLOAD_ROOT / "agents" / f"{role}.toml", skill_path)
            )
            for role in ROLES
        },
    }
    skill_source = PAYLOAD_ROOT / "skills" / SKILL_NAME
    for source in sorted(skill_source.rglob("*")):
        if not source.is_file() or source.name == ".DS_Store" or source.suffix == ".pyc":
            continue
        relative = str(Path("skills") / SKILL_NAME / source.relative_to(skill_source))
        common[relative] = sha256_bytes(source.read_bytes())
    profiles = []
    for language in AGENTS_SECTION_FILES:
        section = (PAYLOAD_ROOT / AGENTS_SECTION_FILES[language]).read_text(
            encoding="utf-8"
        )
        policy = agents_policy_section(section)
        if policy is None:
            raise InstallError(
                f"{language} AGENTS policy template has no managed section"
            )
        profile = dict(common)
        profile["AGENTS.md#subagent-policy"] = sha256_bytes(policy[2].encode())
        profiles.append(profile)
    return profiles


def direct_predecessor_state_profiles(codex_home: Path) -> list[dict[str, str]]:
    skill_path = codex_home / "skills" / SKILL_NAME / "SKILL.md"
    common = dict(DIRECT_PREDECESSOR_MANAGED_HASHES)
    for role in ROLES:
        common[f"agents/{role}.toml"] = sha256_bytes(
            render_role(PAYLOAD_ROOT / "agents" / f"{role}.toml", skill_path)
        )
    profiles = []
    for policy_hash in DIRECT_PREDECESSOR_POLICY_SHA256:
        profile = dict(common)
        profile["AGENTS.md#subagent-policy"] = policy_hash
        profiles.append(profile)
    return profiles


def expand_retired_state_profiles(
    profiles: list[dict[str, str]],
    catalog: dict,
) -> list[dict[str, str]]:
    expanded = profiles
    for entry in catalog["retired_paths"]:
        next_profiles = list(expanded)
        for profile in expanded:
            for accepted_hash in entry["accepted_sha256"]:
                retired = dict(profile)
                retired[entry["path"]] = accepted_hash
                next_profiles.append(retired)
        expanded = next_profiles
    return expanded


def authenticate_managed_state(
    codex_home: Path,
    document: dict,
    managed: dict[str, str],
) -> None:
    """Authenticate the complete map against package-owned external profiles."""
    catalog = load_migration_catalog()
    allowed_profiles = current_managed_state_profiles(codex_home)
    if (
        document["format_version"] == 2
        and document["install_contract_sha256"] == DIRECT_PREDECESSOR_INSTALL_CONTRACT
    ):
        allowed_profiles.extend(direct_predecessor_state_profiles(codex_home))
    allowed_profiles = expand_retired_state_profiles(allowed_profiles, catalog)
    if managed not in allowed_profiles:
        raise InstallError("managed state document identity is not accepted")


def read_state(
    codex_home: Path,
    recovery_journal: dict | None = None,
) -> dict[str, str]:
    path = codex_home / STATE_RELATIVE
    content = safe_existing_bytes(path, codex_home)
    if content is None:
        return {}
    try:
        decoded = content.decode()
    except UnicodeError as error:
        raise InstallError(f"managed state is unreadable: {error}") from error
    document = strict_json_loads(decoded, "managed state")
    if not isinstance(document, dict):
        raise InstallError("managed state has an unknown document schema")
    if document.get("package_id") != SKILL_NAME:
        raise InstallError("managed state package identity mismatch")
    format_version = document.get("format_version")
    if format_version == 1:
        expected_document_keys = {
            "format_version",
            "package_id",
            "package_manifest_sha256",
            "managed_hashes",
        }
        if set(document) != expected_document_keys:
            raise InstallError("managed state has an unknown v1 document schema")
        lineage = document.get("package_manifest_sha256")
        accepted_lineage = {
            sha256_bytes(MANIFEST_PATH.read_bytes()),
            *ACCEPTED_STATE_MANIFESTS,
        }
        if lineage not in accepted_lineage:
            raise InstallError("managed state manifest lineage is not accepted")
    elif format_version == 2:
        expected_document_keys = {
            "format_version",
            "package_id",
            "install_contract_sha256",
            "managed_hashes",
        }
        if set(document) != expected_document_keys:
            raise InstallError("managed state has an unknown v2 document schema")
        catalog = load_migration_catalog()
        lineage = document.get("install_contract_sha256")
        accepted_lineage = {
            install_contract_sha256(catalog),
            *catalog["accepted_install_contracts"],
        }
        if lineage not in accepted_lineage:
            raise InstallError("managed state install-contract lineage is not accepted")
    else:
        raise InstallError("managed state format_version must be 1 or 2")
    managed = document.get("managed_hashes")
    if not isinstance(managed, dict) or not all(
        isinstance(key, str)
        and isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value)
        for key, value in managed.items()
    ):
        raise InstallError("managed state has an invalid managed_hashes map")
    expected_domain = expected_managed_domain()
    catalog = load_migration_catalog()
    retirement_hashes = retired_path_hashes(catalog)
    unexpected = sorted(set(managed) - expected_domain - set(retirement_hashes))
    missing = sorted(expected_domain - set(managed))
    if unexpected or missing:
        raise InstallError(
            "managed state owned-key domain mismatch; "
            f"missing={missing}; unexpected={unexpected}"
        )
    for relative in sorted(set(managed) - expected_domain):
        if managed[relative] not in retirement_hashes[relative]:
            raise InstallError(
                f"managed state retired-path hash is not authorized: {relative}"
            )
    authenticate_managed_state(codex_home, document, managed)
    verify_recorded_state(codex_home, managed, recovery_journal)
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


def current_managed_hash(codex_home: Path, key: str) -> str | None:
    if key == "AGENTS.md#subagent-policy":
        agents_content = safe_existing_bytes(codex_home / "AGENTS.md", codex_home)
        if agents_content is None:
            return None
        try:
            agents_text = agents_content.decode()
        except UnicodeError as error:
            raise InstallError(f"managed AGENTS.md is unreadable: {error}") from error
        agents_policy = agents_policy_section(agents_text)
        if agents_policy is None:
            return None
        return sha256_bytes(agents_policy[2].encode())
    if key == "config.toml#agents":
        config_content = safe_existing_bytes(codex_home / "config.toml", codex_home)
        if config_content is None:
            return None
        try:
            config_document = tomllib.loads(config_content.decode())
        except (UnicodeError, tomllib.TOMLDecodeError) as error:
            raise InstallError(f"managed config.toml is unreadable: {error}") from error
        return canonical_json_hash(config_projection(config_document))
    content = safe_existing_bytes(codex_home / key, codex_home)
    return sha256_bytes(content) if content is not None else None


def journal_recovery_hashes(journal: dict | None) -> dict[str, str | None]:
    if journal is None:
        return {}
    return {
        target["managed_key"]: target["desired_managed_sha256"]
        for target in journal["targets"]
        if target["managed_key"] is not None
    }


def verify_recorded_state(
    codex_home: Path,
    managed: dict[str, str],
    recovery_journal: dict | None = None,
) -> None:
    recovery = journal_recovery_hashes(recovery_journal)
    mismatches = []
    for key, expected in managed.items():
        actual = current_managed_hash(codex_home, key)
        if actual == expected:
            continue
        if key in recovery and actual == recovery[key]:
            continue
        mismatches.append(key)
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
    known_predecessor = current_hash in ACCEPTED_GLOBAL_POLICY_SHA256
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
    content: bytes | None,
    managed_hash: str | None,
    prior: bytes | None,
    managed_key: str | None = None,
    quarantine_path: Path | None = None,
    staging_path: Path | None = None,
) -> PlannedWrite:
    return PlannedWrite(
        relative=relative,
        path=path,
        content=content,
        managed_hash=managed_hash,
        expected_prior_exists=prior is not None,
        expected_prior_sha256=sha256_bytes(prior) if prior is not None else None,
        expected_prior_mode=(
            path.stat(follow_symlinks=False).st_mode & 0o777
            if prior is not None
            else None
        ),
        managed_key=managed_key,
        quarantine_path=quarantine_path,
        staging_path=staging_path,
    )


def quarantine_relative(relative: str, content_hash: str) -> Path:
    return QUARANTINE_RELATIVE / content_hash / Path(relative)


def staging_relative(relative: str, content_hash: str) -> Path:
    return STAGING_RELATIVE / content_hash / Path(relative)


def write_recovery_relative(
    transaction_id: str,
    relative: str,
) -> Path:
    path_id = sha256_bytes(relative.encode())
    return WRITE_RECOVERY_RELATIVE / transaction_id / path_id / Path(relative).name


def exact_path_state(
    path: Path,
    codex_home: Path,
    expected_exists: bool,
    expected_sha256: str | None,
    expected_mode: int | None,
) -> bool:
    content = safe_existing_bytes(path, codex_home)
    actual_exists = content is not None
    actual_sha256 = sha256_bytes(content) if content is not None else None
    actual_mode = (
        path.stat(follow_symlinks=False).st_mode & 0o777
        if content is not None
        else None
    )
    return (actual_exists, actual_sha256, actual_mode) == (
        expected_exists,
        expected_sha256,
        expected_mode,
    )


def return_claimed_path(staging: Path, path: Path) -> Path:
    """Best-effort return of a drifted claimed object without replacing a collision."""
    try:
        rename_noreplace(staging, path)
        fsync_directory(staging.parent)
        if path.parent != staging.parent:
            fsync_directory(path.parent)
        return path
    except (InstallError, OSError):
        return staging


def verify_precondition(plan: PlannedWrite, codex_home: Path) -> None:
    current = safe_existing_bytes(plan.path, codex_home)
    current_exists = current is not None
    current_hash = sha256_bytes(current) if current is not None else None
    current_mode = (
        plan.path.stat(follow_symlinks=False).st_mode & 0o777
        if current is not None
        else None
    )
    if (
        current_exists != plan.expected_prior_exists
        or current_hash != plan.expected_prior_sha256
        or current_mode != plan.expected_prior_mode
    ):
        expected = plan.expected_prior_sha256 or "<absent>"
        actual = current_hash or "<absent>"
        raise InstallError(
            f"target drifted after preflight: {plan.relative}; "
            f"expected {expected} mode {plan.expected_prior_mode}, "
            f"got {actual} mode {current_mode}"
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
    recovery_journal: dict | None = None,
) -> tuple[list[PlannedWrite], dict[str, str]]:
    load_manifest()
    catalog = load_migration_catalog()
    if agents_language not in AGENTS_SECTION_FILES:
        raise InstallError(f"unsupported AGENTS policy language: {agents_language}")
    if recovery_journal is None and safe_existing_bytes(
        codex_home / JOURNAL_RELATIVE, codex_home
    ) is not None:
        raise InstallError("unfinished install transaction; run --doctor or --apply")
    state = read_state(codex_home, recovery_journal)
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
                "AGENTS.md#subagent-policy",
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
                "config.toml#agents",
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
                planned_write(
                    relative, target, desired, managed_hash, current, relative
                )
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
                planned_write(
                    relative, target, desired, managed_hash, current, relative
                )
            )

    for relative in sorted(set(state) - expected_managed_domain()):
        target = codex_home / relative
        current = safe_existing_bytes(target, codex_home)
        if current is None:
            if recovery_journal is None:
                raise InstallError(f"managed retired target is missing: {relative}")
            continue
        current_hash = sha256_bytes(current)
        allowed = retired_path_hashes(catalog)[relative]
        if current_hash != state[relative] or current_hash not in allowed:
            raise InstallError(f"managed retired target changed: {relative}")
        quarantine_path = codex_home / quarantine_relative(relative, current_hash)
        staging_path = codex_home / staging_relative(relative, current_hash)
        quarantined = safe_existing_bytes(quarantine_path, codex_home)
        recoverable_link = (
            recovery_journal is not None
            and quarantined is not None
            and sha256_bytes(quarantined) == current_hash
            and same_physical_file(target, quarantine_path)
        )
        if quarantined is not None and not recoverable_link:
            raise InstallError(
                f"retired-path quarantine destination already exists: {relative}"
            )
        plans.append(
            planned_write(
                relative,
                target,
                None,
                None,
                current,
                relative,
                quarantine_path,
                staging_path,
            )
        )

    state_document = {
        "format_version": 2,
        "package_id": SKILL_NAME,
        "install_contract_sha256": install_contract_sha256(catalog),
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
                None,
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
    if content is None:
        raise InstallError(f"internal error: write has no content: {plan.relative}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, plan.desired_mode)
        # Bind the live namespace object immediately before claiming it. An
        # existing preimage is moved to a deterministic transaction-owned path;
        # an absent preimage is asserted by the candidate no-replace rename.
        verify_precondition(plan, codex_home)
        if plan.expected_prior_exists:
            staging = plan.write_recovery_path or (
                codex_home
                / write_recovery_relative(secrets.token_hex(32), plan.relative)
            )
            staging.parent.mkdir(parents=True, exist_ok=True)
            if safe_existing_bytes(staging, codex_home) is not None:
                raise InstallError(
                    f"write recovery staging already exists: {plan.relative}"
                )
            rename_noreplace(path, staging)
            fsync_directory(path.parent)
            if staging.parent != path.parent:
                fsync_directory(staging.parent)
            if not exact_path_state(
                staging,
                codex_home,
                True,
                plan.expected_prior_sha256,
                plan.expected_prior_mode,
            ):
                preserved = return_claimed_path(staging, path)
                raise InstallError(
                    f"write target changed while being claimed: {plan.relative}; "
                    f"preserved at {preserved}"
                )
        rename_noreplace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_quarantine(plan: PlannedWrite, codex_home: Path) -> None:
    if (
        plan.content is not None
        or plan.quarantine_path is None
        or plan.staging_path is None
    ):
        raise InstallError(f"internal error: invalid quarantine plan: {plan.relative}")
    destination = plan.quarantine_path
    staging = plan.staging_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging.parent.mkdir(parents=True, exist_ok=True)
    if safe_existing_bytes(staging, codex_home) is not None:
        raise InstallError(f"quarantine staging already exists: {plan.relative}")
    verify_precondition(plan, codex_home)
    quarantined = safe_existing_bytes(destination, codex_home)
    if quarantined is None:
        try:
            os.link(plan.path, destination)
        except FileExistsError as error:
            raise InstallError(
                f"quarantine destination appeared: {plan.relative}"
            ) from error
    elif not (
        sha256_bytes(quarantined) == plan.expected_prior_sha256
        and same_physical_file(plan.path, destination)
    ):
        raise InstallError(f"quarantine destination already exists: {plan.relative}")

    actual = sha256_bytes(destination.read_bytes())
    if actual != plan.expected_prior_sha256:
        raise InstallError(f"post-quarantine hash mismatch: {plan.relative}")
    if not same_physical_file(plan.path, destination):
        raise InstallError(f"quarantine source changed after linking: {plan.relative}")

    destination_descriptor = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(destination_descriptor)
    finally:
        os.close(destination_descriptor)
    destination_directory_descriptor = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(destination_directory_descriptor)
    finally:
        os.close(destination_directory_descriptor)

    verify_precondition(plan, codex_home)
    if not same_physical_file(plan.path, destination):
        raise InstallError(f"quarantine source changed before staging: {plan.relative}")
    rename_noreplace(plan.path, staging)

    staged = safe_existing_bytes(staging, codex_home)
    staged_matches = (
        staged is not None
        and sha256_bytes(staged) == plan.expected_prior_sha256
        and same_physical_file(staging, destination)
    )
    for directory in {plan.path.parent, staging.parent}:
        directory_descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    if not staged_matches:
        restored = False
        if staged is not None:
            try:
                rename_noreplace(staging, plan.path)
                restored = True
            except (InstallError, OSError):
                pass
        preserved = plan.path if restored else staging
        raise InstallError(
            f"quarantine source changed during staging; preserved at {preserved}"
        )


def apply_plans(
    plans: list[PlannedWrite],
    codex_home: Path,
    on_touched: Callable[[str, str], None] | None = None,
) -> list[tuple[str, str]]:
    """Apply a preflighted plan with an all-target gate and per-file rechecks."""
    verify_all_preconditions(plans, codex_home)
    touched = []
    for plan in plans:
        if plan.operation == "write":
            atomic_write(plan, codex_home)
            actual = sha256_bytes(plan.path.read_bytes())
            if actual != plan.desired_sha256:
                raise InstallError(f"post-write hash mismatch: {plan.relative}")
        elif plan.operation == "quarantine":
            atomic_quarantine(plan, codex_home)
            if plan.path.exists() or plan.path.is_symlink():
                raise InstallError(f"post-quarantine target still exists: {plan.relative}")
            actual = "<absent>"
        else:
            raise InstallError(f"unsupported planned operation: {plan.operation}")
        touched.append((plan.relative, actual))
        if on_touched is not None:
            on_touched(plan.relative, actual)
    return touched


def lock_path(codex_home: Path) -> Path:
    return codex_home.parent / f".{codex_home.name}.{SKILL_NAME}.install.lock"


@contextmanager
def apply_lock(codex_home: Path) -> Iterator[None]:
    path = lock_path(codex_home)
    content = (
        json.dumps(
            {"format_version": 1, "pid": os.getpid(), "target": str(codex_home)},
            sort_keys=True,
        )
        + "\n"
    ).encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise InstallError(
            f"another installer holds apply lock (target lock): {path}"
        ) from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        try:
            if path.read_bytes() == content:
                path.unlink()
        except FileNotFoundError:
            pass


def source_package_identity() -> dict:
    """Return a reproducible identity for a manifest-verified source archive.

    A real checkout must be clean and exactly bound to HEAD. Only a source with
    no discoverable Git metadata may use the manifest-verified archive mode.
    """
    manifest = load_manifest()
    archive_entries = [
        {
            "path": item["path"],
            "sha256": item["sha256"],
            "size": item["size"],
        }
        for item in sorted(manifest["files"], key=lambda item: item["path"])
    ]
    identity = {
        "archive_sha256": canonical_json_hash(archive_entries),
        "install_contract_sha256": install_contract_sha256(),
        "manifest_sha256": sha256_bytes(MANIFEST_PATH.read_bytes()),
        "source_revision": None,
        "source_revision_status": "unavailable-archive-identity-used",
    }
    default_manifest = PACKAGE_ROOT / "manifest.json"
    if MANIFEST_PATH.resolve(strict=False) != default_manifest.resolve(strict=False):
        return identity
    try:
        discovered = subprocess.run(
            ["git", "-C", str(PACKAGE_ROOT), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        if (PACKAGE_ROOT / ".git").exists():
            raise InstallError(f"cannot verify Git source identity: {error}") from error
        return identity
    if discovered.returncode != 0:
        if (PACKAGE_ROOT / ".git").exists() or (PACKAGE_ROOT / ".git").is_symlink():
            raise InstallError(
                "package has Git metadata but its worktree identity is unverifiable"
            )
        return identity
    try:
        git_root = Path(discovered.stdout.strip()).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise InstallError(f"Git worktree root is invalid: {error}") from error
    if git_root != PACKAGE_ROOT.resolve(strict=True):
        raise InstallError(
            f"package source is inside an unexpected Git worktree: {git_root}"
        )
    head_result = subprocess.run(
        ["git", "-C", str(PACKAGE_ROOT), "rev-parse", "--verify", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    head = head_result.stdout.strip()
    if head_result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40,64}", head) is None:
        raise InstallError("Git source has no valid HEAD revision")
    tracked = ["manifest.json", *(item["path"] for item in manifest["files"])]
    for relative in tracked:
        result = subprocess.run(
            ["git", "-C", str(PACKAGE_ROOT), "cat-file", "-e", f"{head}:{relative}"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise InstallError(f"Git HEAD does not track package path: {relative}")
    status = subprocess.run(
        [
            "git",
            "-C",
            str(PACKAGE_ROOT),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if status.returncode != 0:
        raise InstallError(f"cannot verify clean Git source: {status.stderr.strip()}")
    if status.stdout:
        raise InstallError("Git package source is dirty; use a clean checkout or archive")
    identity["source_revision"] = head
    identity["source_revision_status"] = "verified-clean-git"
    return identity


def target_identity(codex_home: Path) -> dict:
    codex_home = validate_codex_home(codex_home)
    if codex_home.exists() and not codex_home.is_dir():
        raise InstallError(f"--codex-home is not a directory: {codex_home}")
    anchor = codex_home
    while not anchor.exists():
        if anchor == anchor.parent:
            raise InstallError("cannot identify target filesystem")
        anchor = anchor.parent
    return {
        "device": os.stat(anchor, follow_symlinks=False).st_dev,
        "realpath": str(codex_home),
    }


def planned_mode(plan: PlannedWrite) -> int | None:
    if plan.content is None:
        return None
    if plan.expected_prior_exists:
        return plan.expected_prior_mode
    return 0o644


def plan_receipt_document(
    codex_home: Path,
    agents_language: str,
    plans: list[PlannedWrite] | None = None,
) -> dict:
    codex_home = validate_codex_home(codex_home)
    if plans is None:
        plans, _ = plan_install(codex_home, agents_language)
    document = {
        "agents_language": agents_language,
        "format_version": 1,
        "package_id": SKILL_NAME,
        "plan_digest": None,
        "source": source_package_identity(),
        "target": target_identity(codex_home),
        "targets": [
            {
                "desired_exists": plan.content is not None,
                "desired_mode": planned_mode(plan),
                "desired_sha256": plan.desired_sha256,
                "managed_key": plan.managed_key,
                "operation": plan.operation,
                "prior_exists": plan.expected_prior_exists,
                "prior_mode": (
                    plan.expected_prior_mode
                ),
                "prior_sha256": plan.expected_prior_sha256,
                "relative": plan.relative,
            }
            for plan in plans
        ],
    }
    digest_input = dict(document)
    digest_input.pop("plan_digest")
    document["plan_digest"] = canonical_json_hash(digest_input)
    return document


def validate_source_identity(value: object) -> dict:
    expected_keys = {
        "archive_sha256",
        "install_contract_sha256",
        "manifest_sha256",
        "source_revision",
        "source_revision_status",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise InstallError("receipt source identity has an unknown schema")
    for key in ("archive_sha256", "install_contract_sha256", "manifest_sha256"):
        if not validate_optional_hash(value[key]) or value[key] is None:
            raise InstallError(f"receipt source identity has invalid {key}")
    if value["source_revision"] is not None:
        if not isinstance(value["source_revision"], str) or not value["source_revision"]:
            raise InstallError("receipt source revision is invalid")
    if value["source_revision_status"] not in {
        "verified-clean-git",
        "unavailable-archive-identity-used",
    }:
        raise InstallError("receipt source revision status is invalid")
    return value


def validate_target_identity(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"device", "realpath"}:
        raise InstallError("receipt target identity has an unknown schema")
    if not isinstance(value["device"], int) or value["device"] < 0:
        raise InstallError("receipt target device is invalid")
    if not isinstance(value["realpath"], str) or not Path(value["realpath"]).is_absolute():
        raise InstallError("receipt target realpath is invalid")
    return value


def validate_plan_receipt(document: object) -> dict:
    expected_keys = {
        "agents_language",
        "format_version",
        "package_id",
        "plan_digest",
        "source",
        "target",
        "targets",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise InstallError("plan receipt has an unknown schema")
    if document["format_version"] != 1 or document["package_id"] != SKILL_NAME:
        raise InstallError("plan receipt identity mismatch")
    if document["agents_language"] not in AGENTS_SECTION_FILES:
        raise InstallError("plan receipt has an invalid AGENTS language")
    validate_source_identity(document["source"])
    validate_target_identity(document["target"])
    if not validate_optional_hash(document["plan_digest"]) or document["plan_digest"] is None:
        raise InstallError("plan receipt has an invalid digest")
    targets = document["targets"]
    if not isinstance(targets, list):
        raise InstallError("plan receipt targets must be a list")
    target_keys = {
        "desired_exists",
        "desired_mode",
        "desired_sha256",
        "managed_key",
        "operation",
        "prior_exists",
        "prior_mode",
        "prior_sha256",
        "relative",
    }
    seen = set()
    for target in targets:
        if not isinstance(target, dict) or set(target) != target_keys:
            raise InstallError("plan receipt has an invalid target schema")
        relative = target["relative"]
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative in seen
        ):
            raise InstallError(f"plan receipt has an unsafe or duplicate target: {relative!r}")
        if target["operation"] not in {"write", "quarantine"}:
            raise InstallError(f"plan receipt has an invalid operation: {relative}")
        if not isinstance(target["prior_exists"], bool) or not isinstance(
            target["desired_exists"], bool
        ):
            raise InstallError(f"plan receipt has invalid existence state: {relative}")
        for prefix in ("prior", "desired"):
            exists = target[f"{prefix}_exists"]
            digest = target[f"{prefix}_sha256"]
            mode = target[f"{prefix}_mode"]
            if exists:
                if not validate_optional_hash(digest) or digest is None:
                    raise InstallError(f"plan receipt has invalid {prefix} hash: {relative}")
                if not isinstance(mode, int) or not 0 <= mode <= 0o777:
                    raise InstallError(f"plan receipt has invalid {prefix} mode: {relative}")
            elif digest is not None or mode is not None:
                raise InstallError(f"plan receipt has inconsistent {prefix} absence: {relative}")
        if target["operation"] == "write" and not target["desired_exists"]:
            raise InstallError(f"plan receipt write is absent: {relative}")
        if target["operation"] == "quarantine" and target["desired_exists"]:
            raise InstallError(f"plan receipt quarantine is not absent: {relative}")
        if target["managed_key"] is not None and not isinstance(target["managed_key"], str):
            raise InstallError(f"plan receipt managed key is invalid: {relative}")
        seen.add(relative)
    digest_input = dict(document)
    digest_input.pop("plan_digest")
    if canonical_json_hash(digest_input) != document["plan_digest"]:
        raise InstallError("plan receipt digest mismatch")
    return document


def read_strict_json(path: Path, label: str) -> object:
    if not path.is_absolute():
        raise InstallError(f"--{label}-receipt must be an absolute path")
    if path.is_symlink():
        raise InstallError(f"{label} receipt is a symlink: {path}")
    if not path.is_file():
        raise InstallError(f"{label} receipt is not a regular file: {path}")
    try:
        return strict_json_loads(
            path.read_text(encoding="utf-8"), f"{label} receipt"
        )
    except (OSError, UnicodeError) as error:
        raise InstallError(f"{label} receipt is unreadable: {error}") from error


def read_plan_receipt(path: Path) -> dict:
    return validate_plan_receipt(read_strict_json(path, "plan"))


def verify_plan_receipt_current(
    receipt: dict,
    codex_home: Path,
    agents_language: str,
) -> list[PlannedWrite]:
    if receipt["agents_language"] != agents_language:
        raise InstallError("plan receipt AGENTS language mismatch")
    if receipt["target"] != target_identity(codex_home):
        raise InstallError("plan receipt belongs to another target identity")
    if receipt["source"] != source_package_identity():
        raise InstallError("source package drifted after check")
    plans, _ = plan_install(codex_home, agents_language)
    if receipt != plan_receipt_document(codex_home, agents_language, plans):
        raise InstallError("target or install plan drifted after check")
    return plans


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_new_json(path: Path, document: dict, mode: int = 0o600) -> None:
    if path.exists() or path.is_symlink():
        raise InstallError(f"refusing to replace receipt artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write((json.dumps(document, indent=2, sort_keys=True) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.link(temporary, path)
        fsync_directory(path.parent)
    except FileExistsError as error:
        raise InstallError(f"receipt artifact appeared concurrently: {path}") from error
    finally:
        if temporary.exists():
            temporary.unlink()


def vault_relative(kind: str, plan_digest: str, relative: str) -> Path:
    path_id = sha256_bytes(relative.encode())
    return RESTORE_VAULT_RELATIVE / kind / plan_digest / path_id / Path(relative).name


def preserve_snapshot(
    source: Path,
    destination: Path,
    codex_home: Path,
    expected_sha256: str,
    expected_mode: int,
) -> None:
    existing = safe_existing_bytes(destination, codex_home)
    if existing is not None:
        if (
            sha256_bytes(existing) != expected_sha256
            or destination.stat(follow_symlinks=False).st_mode & 0o777 != expected_mode
            or same_physical_file(source, destination)
        ):
            raise InstallError(f"restore vault artifact mismatch: {destination}")
        return

    source_content = safe_existing_bytes(source, codex_home)
    source_mode = (
        source.stat(follow_symlinks=False).st_mode & 0o777
        if source_content is not None
        else None
    )
    if (
        source_content is None
        or sha256_bytes(source_content) != expected_sha256
        or source_mode != expected_mode
    ):
        raise InstallError(f"restore snapshot source drifted: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.snapshot.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(source_content)
            stream.flush()
            os.fchmod(stream.fileno(), expected_mode)
            os.fsync(stream.fileno())

        current_source = safe_existing_bytes(source, codex_home)
        current_mode = (
            source.stat(follow_symlinks=False).st_mode & 0o777
            if current_source is not None
            else None
        )
        if (
            current_source is None
            or sha256_bytes(current_source) != expected_sha256
            or current_mode != expected_mode
        ):
            raise InstallError(f"restore snapshot source drifted: {source}")
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise InstallError(
                f"restore vault artifact appeared concurrently: {destination}"
            ) from error
        fsync_directory(destination.parent)
    finally:
        if temporary.exists():
            temporary.unlink()

    snapshot = safe_existing_bytes(destination, codex_home)
    if (
        snapshot is None
        or sha256_bytes(snapshot) != expected_sha256
        or destination.stat(follow_symlinks=False).st_mode & 0o777 != expected_mode
        or same_physical_file(source, destination)
    ):
        raise InstallError(f"failed to preserve independent restore snapshot: {source}")


def journal_document(plans: list[PlannedWrite], agents_language: str) -> dict:
    transaction_id = secrets.token_hex(32)
    return {
        "agents_language": agents_language,
        "format_version": 2,
        "install_contract_sha256": install_contract_sha256(),
        "package_id": SKILL_NAME,
        "transaction_id": transaction_id,
        "targets": [
            {
                "desired_managed_sha256": plan.managed_hash,
                "desired_mode": plan.desired_mode,
                "desired_sha256": plan.desired_sha256,
                "managed_key": plan.managed_key,
                "operation": plan.operation,
                "prior_exists": plan.expected_prior_exists,
                "prior_mode": plan.expected_prior_mode,
                "prior_sha256": plan.expected_prior_sha256,
                "quarantine_relative": (
                    str(quarantine_relative(plan.relative, plan.expected_prior_sha256))
                    if plan.quarantine_path is not None
                    else None
                ),
                "staging_relative": (
                    str(staging_relative(plan.relative, plan.expected_prior_sha256))
                    if plan.staging_path is not None
                    else None
                ),
                "relative": plan.relative,
                "write_recovery_relative": (
                    str(
                        write_recovery_relative(
                            transaction_id,
                            plan.relative,
                        )
                    )
                    if plan.operation == "write" and plan.expected_prior_exists
                    else None
                ),
            }
            for plan in plans
        ],
    }


def validate_optional_hash(value: object) -> bool:
    return value is None or (
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    )


def validate_journal(document: object) -> dict:
    expected_keys = {
        "agents_language",
        "format_version",
        "install_contract_sha256",
        "package_id",
        "targets",
        "transaction_id",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise InstallError("install transaction has an unknown schema")
    if document.get("format_version") != 2:
        raise InstallError("install transaction format_version must be 2")
    if document.get("package_id") != SKILL_NAME:
        raise InstallError("install transaction package identity mismatch")
    if document.get("agents_language") not in AGENTS_SECTION_FILES:
        raise InstallError("install transaction has an invalid AGENTS language")
    if not isinstance(document.get("transaction_id"), str) or re.fullmatch(
        r"[0-9a-f]{64}", document["transaction_id"]
    ) is None:
        raise InstallError("install transaction has an invalid transaction id")
    if not validate_optional_hash(document.get("install_contract_sha256")) or document.get(
        "install_contract_sha256"
    ) is None:
        raise InstallError("install transaction has an invalid contract hash")
    targets = document.get("targets")
    if not isinstance(targets, list) or not targets:
        raise InstallError("install transaction has no targets")
    expected_target_keys = {
        "desired_managed_sha256",
        "desired_mode",
        "desired_sha256",
        "managed_key",
        "operation",
        "prior_exists",
        "prior_mode",
        "prior_sha256",
        "quarantine_relative",
        "relative",
        "staging_relative",
        "write_recovery_relative",
    }
    seen = set()
    catalog = load_migration_catalog()
    allowed_physical = {
        "AGENTS.md",
        "config.toml",
        str(STATE_RELATIVE),
        *(key for key in expected_managed_domain() if "#" not in key),
        *retired_path_hashes(catalog),
    }
    for target in targets:
        if not isinstance(target, dict) or set(target) != expected_target_keys:
            raise InstallError("install transaction has an invalid target entry")
        relative = target.get("relative")
        operation = target.get("operation")
        managed_key = target.get("managed_key")
        quarantine = target.get("quarantine_relative")
        staging = target.get("staging_relative")
        write_recovery = target.get("write_recovery_relative")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative in seen
            or relative == str(JOURNAL_RELATIVE)
            or relative not in allowed_physical
        ):
            raise InstallError(f"install transaction has an unsafe target: {relative!r}")
        if operation not in {"write", "quarantine"}:
            raise InstallError(f"install transaction has an invalid operation: {relative}")
        if not validate_optional_hash(target.get("prior_sha256")) or not validate_optional_hash(
            target.get("desired_sha256")
        ) or not validate_optional_hash(target.get("desired_managed_sha256")):
            raise InstallError(f"install transaction has an invalid hash: {relative}")
        if operation == "write" and target.get("desired_sha256") is None:
            raise InstallError(f"install transaction write has no desired hash: {relative}")
        if not isinstance(target.get("prior_exists"), bool):
            raise InstallError(
                f"install transaction has invalid prior existence: {relative}"
            )
        if target["prior_exists"]:
            if target["prior_sha256"] is None or not isinstance(
                target.get("prior_mode"), int
            ) or not 0 <= target["prior_mode"] <= 0o777:
                raise InstallError(
                    f"install transaction has invalid prior state: {relative}"
                )
        elif target["prior_sha256"] is not None or target.get("prior_mode") is not None:
            raise InstallError(
                f"install transaction has inconsistent prior absence: {relative}"
            )
        if operation == "quarantine":
            if target.get("desired_sha256") is not None or target.get("prior_sha256") is None:
                raise InstallError(
                    f"install transaction quarantine has invalid hashes: {relative}"
                )
            expected_quarantine = str(
                quarantine_relative(relative, target["prior_sha256"])
            )
            expected_staging = str(staging_relative(relative, target["prior_sha256"]))
            if quarantine != expected_quarantine or staging != expected_staging:
                raise InstallError(
                    f"install transaction has invalid quarantine or staging target: {relative}"
                )
            if target.get("desired_mode") is not None or write_recovery is not None:
                raise InstallError(
                    f"install transaction quarantine has invalid write state: {relative}"
                )
        elif quarantine is not None or staging is not None:
            raise InstallError(
                f"install transaction write has a quarantine or staging target: {relative}"
            )
        else:
            if not isinstance(target.get("desired_mode"), int) or not 0 <= target[
                "desired_mode"
            ] <= 0o777:
                raise InstallError(
                    f"install transaction has invalid desired mode: {relative}"
                )
            expected_write_recovery = (
                str(
                    write_recovery_relative(
                        document["transaction_id"],
                        relative,
                    )
                )
                if target["prior_exists"]
                else None
            )
            if write_recovery != expected_write_recovery:
                raise InstallError(
                    f"install transaction has invalid write recovery target: {relative}"
                )
        if managed_key is not None and not isinstance(managed_key, str):
            raise InstallError(f"install transaction has an invalid managed key: {relative}")
        if relative == "AGENTS.md":
            expected_managed_key = "AGENTS.md#subagent-policy"
        elif relative == "config.toml":
            expected_managed_key = "config.toml#agents"
        elif relative == str(STATE_RELATIVE):
            expected_managed_key = None
        else:
            expected_managed_key = relative
        if managed_key != expected_managed_key:
            raise InstallError(f"install transaction managed-key mismatch: {relative}")
        if managed_key is None and target["desired_managed_sha256"] is not None:
            raise InstallError(f"install transaction has an ownerless managed hash: {relative}")
        if operation == "quarantine" and target["desired_managed_sha256"] is not None:
            raise InstallError(
                f"install transaction quarantine retained a managed hash: {relative}"
            )
        if (
            operation == "write"
            and managed_key not in {None, "AGENTS.md#subagent-policy", "config.toml#agents"}
            and target["desired_managed_sha256"] != target["desired_sha256"]
        ):
            raise InstallError(f"install transaction managed hash mismatch: {relative}")
        seen.add(relative)
    return document


def read_journal(codex_home: Path) -> dict | None:
    content = safe_existing_bytes(codex_home / JOURNAL_RELATIVE, codex_home)
    if content is None:
        return None
    try:
        document = strict_json_loads(content.decode(), "install transaction")
    except UnicodeError as error:
        raise InstallError(f"install transaction is unreadable: {error}") from error
    return validate_journal(document)


def create_journal(codex_home: Path, document: dict) -> None:
    path = codex_home / JOURNAL_RELATIVE
    if safe_existing_bytes(path, codex_home) is not None:
        raise InstallError("refusing to replace an existing install transaction")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise InstallError("install transaction appeared concurrently") from error
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def classify_journal(codex_home: Path, journal: dict) -> tuple[str, list[tuple[str, str]]]:
    classifications = []
    for target in journal["targets"]:
        path = codex_home / target["relative"]
        actual_state = file_state(path, codex_home)
        if target["operation"] == "quarantine":
            quarantine_path = codex_home / target["quarantine_relative"]
            staging_path = codex_home / target["staging_relative"]
            quarantine_state = file_state(quarantine_path, codex_home)
            staged_state = file_state(staging_path, codex_home)
            prior_state = (
                target["prior_exists"],
                target["prior_sha256"],
                target["prior_mode"],
            )
            linked = (
                actual_state == prior_state
                and quarantine_state == prior_state
                and same_physical_file(path, quarantine_path)
            )
            if linked:
                classification = "linked"
            elif (
                actual_state == (False, None, None)
                and quarantine_state == prior_state
                and staged_state == prior_state
                and same_physical_file(staging_path, quarantine_path)
            ):
                classification = "staged"
            elif actual_state == prior_state and quarantine_state == (False, None, None):
                classification = "prior"
            elif (
                actual_state == (False, None, None)
                and quarantine_state == prior_state
                and staged_state == (False, None, None)
            ):
                classification = "desired"
            else:
                classification = "conflict"
        else:
            recovery_relative = target["write_recovery_relative"]
            recovery_state = (
                file_state(codex_home / recovery_relative, codex_home)
                if recovery_relative is not None
                else (False, None, None)
            )
            expected_recovery_state = (
                (
                    True,
                    target["prior_sha256"],
                    target["prior_mode"],
                )
                if target["prior_exists"]
                else (False, None, None)
            )
            prior_state = (
                target["prior_exists"],
                target["prior_sha256"],
                target["prior_mode"],
            )
            desired_state = (
                True,
                target["desired_sha256"],
                target["desired_mode"],
            )
            if actual_state == desired_state and recovery_state == expected_recovery_state:
                classification = "desired"
            elif actual_state == prior_state and recovery_state == (False, None, None):
                classification = "prior"
            elif (
                target["prior_exists"]
                and actual_state == (False, None, None)
                and recovery_state == expected_recovery_state
            ):
                classification = "claimed"
            else:
                classification = "conflict"
        classifications.append((target["relative"], classification))
    states = {classification for _, classification in classifications}
    if "conflict" in states:
        status = "PARTIAL_CONFLICT"
    elif states and states.issubset({"desired", "staged"}):
        status = "COMPLETE_PENDING_CLEANUP"
    elif states == {"prior"}:
        status = "PREPARED_RECOVERABLE"
    else:
        status = "PARTIAL_RECOVERABLE"
    return status, classifications


def recover_claimed_writes(
    codex_home: Path,
    journal: dict,
    classifications: list[tuple[str, str]],
) -> None:
    targets = {target["relative"]: target for target in journal["targets"]}
    for relative, classification in classifications:
        if classification != "claimed":
            continue
        target = targets[relative]
        staging = codex_home / target["write_recovery_relative"]
        path = codex_home / relative
        rename_noreplace(staging, path)
        fsync_directory(staging.parent)
        if staging.parent != path.parent:
            fsync_directory(path.parent)
        if not exact_path_state(
            path,
            codex_home,
            True,
            target["prior_sha256"],
            target["prior_mode"],
        ):
            raise InstallError(
                f"claimed write preimage changed during recovery: {relative}"
            )


def validate_recovery_plan(plans: list[PlannedWrite], journal: dict) -> None:
    journal_targets = {target["relative"]: target for target in journal["targets"]}
    for plan in plans:
        target = journal_targets.get(plan.relative)
        if target is None:
            raise InstallError(f"recovery plan introduced a new target: {plan.relative}")
        if (
            target["operation"] != plan.operation
            or target["desired_sha256"] != plan.desired_sha256
            or target["desired_mode"] != plan.desired_mode
            or target["desired_managed_sha256"] != plan.managed_hash
            or target["prior_exists"] != plan.expected_prior_exists
            or target["prior_mode"] != plan.expected_prior_mode
            or target["prior_sha256"] != plan.expected_prior_sha256
            or target["quarantine_relative"]
            != (
                str(quarantine_relative(plan.relative, plan.expected_prior_sha256))
                if plan.quarantine_path is not None
                else None
            )
            or target["staging_relative"]
            != (
                str(staging_relative(plan.relative, plan.expected_prior_sha256))
                if plan.staging_path is not None
                else None
            )
            or target["write_recovery_relative"]
            != (
                str(
                    write_recovery_relative(
                        journal["transaction_id"],
                        plan.relative,
                    )
                )
                if plan.operation == "write" and plan.expected_prior_exists
                else None
            )
        ):
            raise InstallError(f"recovery plan changed target contract: {plan.relative}")


def bind_journal_write_recovery(
    plans: list[PlannedWrite],
    journal: dict,
    codex_home: Path,
) -> list[PlannedWrite]:
    targets = {target["relative"]: target for target in journal["targets"]}
    bound = []
    for plan in plans:
        target = targets.get(plan.relative)
        if target is None:
            raise InstallError(f"install transaction is missing target: {plan.relative}")
        relative = target["write_recovery_relative"]
        bound.append(
            replace(
                plan,
                write_recovery_path=(codex_home / relative if relative is not None else None),
            )
        )
    return bound


def finish_journal(codex_home: Path, journal: dict) -> None:
    path = codex_home / JOURNAL_RELATIVE
    current = read_journal(codex_home)
    if current != journal:
        raise InstallError("install transaction changed before cleanup")
    status, _ = classify_journal(codex_home, journal)
    if status != "COMPLETE_PENDING_CLEANUP":
        raise InstallError(f"install transaction did not reach completion: {status}")
    path.unlink()
    directory_descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def apply_install(
    codex_home: Path,
    agents_language: str,
    on_touched: Callable[[str, str], None] | None = None,
) -> list[tuple[str, str]]:
    codex_home = validate_codex_home(codex_home)
    with apply_lock(codex_home):
        journal = read_journal(codex_home)
        if journal is not None:
            if journal["install_contract_sha256"] != install_contract_sha256():
                raise InstallError(
                    "unfinished install transaction belongs to another install contract"
                )
            if journal["agents_language"] != agents_language:
                raise InstallError(
                    "unfinished install transaction uses a different AGENTS language"
                )
            status, classifications = classify_journal(codex_home, journal)
            if status == "PARTIAL_CONFLICT":
                raise InstallError("unfinished install transaction has conflicting targets")
            recover_claimed_writes(codex_home, journal, classifications)
            plans, _ = plan_install(codex_home, agents_language, journal)
            validate_recovery_plan(plans, journal)
        else:
            plans, _ = plan_install(codex_home, agents_language)
            if not plans:
                return []
            journal = journal_document(plans, agents_language)
            create_journal(codex_home, journal)
        plans = bind_journal_write_recovery(plans, journal, codex_home)
        touched = apply_plans(plans, codex_home, on_touched)
        finish_journal(codex_home, journal)
        return touched


def validate_apply_receipt_journal(document: object) -> dict:
    if not isinstance(document, dict) or set(document) != {
        "format_version",
        "package_id",
        "plan_digest",
        "restore_targets",
        "source",
        "target",
    }:
        raise InstallError("receipt-bound apply transaction has an unknown schema")
    if document["format_version"] != 1 or document["package_id"] != SKILL_NAME:
        raise InstallError("receipt-bound apply transaction identity mismatch")
    if not validate_optional_hash(document["plan_digest"]) or document["plan_digest"] is None:
        raise InstallError("receipt-bound apply transaction has an invalid plan digest")
    validate_source_identity(document["source"])
    validate_target_identity(document["target"])
    if not isinstance(document["restore_targets"], list):
        raise InstallError("receipt-bound apply transaction has invalid targets")
    expected = {
        "candidate_exists",
        "candidate_mode",
        "candidate_sha256",
        "prior_backup_relative",
        "prior_exists",
        "prior_mode",
        "prior_sha256",
        "relative",
    }
    seen = set()
    for target in document["restore_targets"]:
        if not isinstance(target, dict) or set(target) != expected:
            raise InstallError("receipt-bound apply transaction has an invalid target")
        relative = target["relative"]
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative in seen
        ):
            raise InstallError(
                "receipt-bound apply transaction has unsafe or duplicate targets"
            )
        for prefix in ("prior", "candidate"):
            exists = target[f"{prefix}_exists"]
            digest = target[f"{prefix}_sha256"]
            mode = target[f"{prefix}_mode"]
            if not isinstance(exists, bool):
                raise InstallError(
                    f"receipt-bound apply transaction has invalid {prefix} existence: {relative}"
                )
            if exists:
                if not validate_optional_hash(digest) or digest is None:
                    raise InstallError(
                        f"receipt-bound apply transaction has invalid {prefix} hash: {relative}"
                    )
                if not isinstance(mode, int) or not 0 <= mode <= 0o777:
                    raise InstallError(
                        f"receipt-bound apply transaction has invalid {prefix} mode: {relative}"
                    )
            elif digest is not None or mode is not None:
                raise InstallError(
                    f"receipt-bound apply transaction has inconsistent {prefix} absence: {relative}"
                )
        expected_backup = (
            str(vault_relative("prior", document["plan_digest"], relative))
            if target["prior_exists"]
            else None
        )
        if target["prior_backup_relative"] != expected_backup:
            raise InstallError(
                f"receipt-bound apply transaction has invalid prior vault path: {relative}"
            )
        seen.add(relative)
    return document


def read_managed_json(codex_home: Path, relative: Path, label: str) -> dict | None:
    content = safe_existing_bytes(codex_home / relative, codex_home)
    if content is None:
        return None
    try:
        return strict_json_loads(content.decode(), label)
    except UnicodeError as error:
        raise InstallError(f"{label} is unreadable: {error}") from error


def verify_restore_target_backups(codex_home: Path, targets: list[dict]) -> None:
    for target in targets:
        backup_relative = target["prior_backup_relative"]
        if target["prior_exists"]:
            if not isinstance(backup_relative, str):
                raise InstallError(f"missing prior backup: {target['relative']}")
            backup = safe_existing_bytes(codex_home / backup_relative, codex_home)
            if (
                backup is None
                or sha256_bytes(backup) != target["prior_sha256"]
                or (codex_home / backup_relative).stat(follow_symlinks=False).st_mode
                & 0o777
                != target["prior_mode"]
            ):
                raise InstallError(f"prior restore vault mismatch: {target['relative']}")
        elif backup_relative is not None:
            raise InstallError(f"absent prior has a restore vault path: {target['relative']}")


def receipt_bound_apply_document(
    receipt: dict,
    plans: list[PlannedWrite],
) -> dict:
    targets = []
    receipt_targets = {target["relative"]: target for target in receipt["targets"]}
    for plan in plans:
        target = receipt_targets[plan.relative]
        backup_relative = (
            str(vault_relative("prior", receipt["plan_digest"], plan.relative))
            if target["prior_exists"]
            else None
        )
        targets.append(
            {
                "candidate_exists": target["desired_exists"],
                "candidate_mode": target["desired_mode"],
                "candidate_sha256": target["desired_sha256"],
                "prior_backup_relative": backup_relative,
                "prior_exists": target["prior_exists"],
                "prior_mode": target["prior_mode"],
                "prior_sha256": target["prior_sha256"],
                "relative": plan.relative,
            }
        )
    return {
        "format_version": 1,
        "package_id": SKILL_NAME,
        "plan_digest": receipt["plan_digest"],
        "restore_targets": targets,
        "source": receipt["source"],
        "target": receipt["target"],
    }


def prepare_receipt_bound_apply(
    codex_home: Path,
    receipt: dict,
    plans: list[PlannedWrite],
) -> dict:
    document = receipt_bound_apply_document(receipt, plans)
    targets = {target["relative"]: target for target in document["restore_targets"]}
    for plan in plans:
        target = targets[plan.relative]
        if target["prior_exists"]:
            preserve_snapshot(
                plan.path,
                codex_home / target["prior_backup_relative"],
                codex_home,
                target["prior_sha256"],
                target["prior_mode"],
            )
    write_new_json(codex_home / APPLY_RECEIPT_JOURNAL_RELATIVE, document)
    return document


def restore_receipt_document(apply_document: dict) -> dict:
    document = {
        "format_version": 1,
        "package_id": SKILL_NAME,
        "plan_digest": apply_document["plan_digest"],
        "receipt_digest": None,
        "source": apply_document["source"],
        "target": apply_document["target"],
        "targets": apply_document["restore_targets"],
    }
    digest_input = dict(document)
    digest_input.pop("receipt_digest")
    document["receipt_digest"] = canonical_json_hash(digest_input)
    return document


def validate_restore_receipt(document: object) -> dict:
    if not isinstance(document, dict) or set(document) != {
        "format_version",
        "package_id",
        "plan_digest",
        "receipt_digest",
        "source",
        "target",
        "targets",
    }:
        raise InstallError("restore receipt has an unknown schema")
    if document["format_version"] != 1 or document["package_id"] != SKILL_NAME:
        raise InstallError("restore receipt identity mismatch")
    validate_source_identity(document["source"])
    validate_target_identity(document["target"])
    for name in ("plan_digest", "receipt_digest"):
        if not validate_optional_hash(document[name]) or document[name] is None:
            raise InstallError(f"restore receipt has an invalid {name}")
    if not isinstance(document["targets"], list) or not document["targets"]:
        raise InstallError("restore receipt has no targets")
    apply_like = {
        "format_version": 1,
        "package_id": SKILL_NAME,
        "plan_digest": document["plan_digest"],
        "restore_targets": document["targets"],
        "source": document["source"],
        "target": document["target"],
    }
    validate_apply_receipt_journal(apply_like)
    digest_input = dict(document)
    digest_input.pop("receipt_digest")
    if canonical_json_hash(digest_input) != document["receipt_digest"]:
        raise InstallError("restore receipt digest mismatch")
    return document


def verify_candidate_postimages(codex_home: Path, apply_document: dict) -> None:
    for target in apply_document["restore_targets"]:
        current = safe_existing_bytes(codex_home / target["relative"], codex_home)
        actual_hash = sha256_bytes(current) if current is not None else None
        actual_mode = (
            (codex_home / target["relative"]).stat(follow_symlinks=False).st_mode
            & 0o777
            if current is not None
            else None
        )
        if (
            (current is not None) != target["candidate_exists"]
            or actual_hash != target["candidate_sha256"]
            or actual_mode != target["candidate_mode"]
        ):
            raise InstallError(f"candidate postimage mismatch: {target['relative']}")


def bind_receipt_preconditions(
    plans: list[PlannedWrite],
    apply_document: dict,
) -> list[PlannedWrite]:
    """Bind recovery plans to receipt modes as well as hashes and absence."""
    targets = {
        target["relative"]: target for target in apply_document["restore_targets"]
    }
    bound = []
    for plan in plans:
        target = targets.get(plan.relative)
        if target is None:
            raise InstallError(
                f"receipt-bound apply introduced a new target: {plan.relative}"
            )
        current_identity = (
            plan.expected_prior_exists,
            plan.expected_prior_sha256,
        )
        prior_identity = (target["prior_exists"], target["prior_sha256"])
        candidate_identity = (
            target["candidate_exists"],
            target["candidate_sha256"],
        )
        if current_identity == prior_identity:
            expected_mode = target["prior_mode"]
        elif current_identity == candidate_identity:
            expected_mode = target["candidate_mode"]
        else:
            raise InstallError(
                f"receipt-bound target identity drifted: {plan.relative}"
            )
        bound.append(replace(plan, expected_prior_mode=expected_mode))
    return bound


def ensure_restore_receipt(
    codex_home: Path,
    apply_document: dict,
    *,
    may_create: bool,
) -> Path:
    restore_receipt = restore_receipt_document(apply_document)
    receipt_path = (
        codex_home
        / RESTORE_RECEIPTS_RELATIVE
        / f"{restore_receipt['receipt_digest']}.json"
    )
    existing = safe_existing_bytes(receipt_path, codex_home)
    expected_bytes = (json.dumps(restore_receipt, indent=2, sort_keys=True) + "\n").encode()
    if existing is None:
        if not may_create:
            raise InstallError(
                "completed apply is missing its durable restore receipt"
            )
        write_new_json(receipt_path, restore_receipt)
    elif existing != expected_bytes:
        raise InstallError("restore receipt path collision")
    return receipt_path


def classify_receipt_bound_apply(
    codex_home: Path,
    apply_document: dict,
) -> str:
    classifications = []
    for target in apply_document["restore_targets"]:
        state = file_state(codex_home / target["relative"], codex_home)
        matches_prior = state_matches(target, "prior", state)
        matches_candidate = state_matches(target, "candidate", state)
        if matches_prior == matches_candidate:
            classifications.append("conflict")
        elif matches_prior:
            classifications.append("prior")
        else:
            classifications.append("candidate")
    states = set(classifications)
    if states == {"prior"}:
        return "PREPARED"
    if states == {"candidate"}:
        ensure_restore_receipt(codex_home, apply_document, may_create=False)
        return "CANDIDATE_COMPLETE"
    raise InstallError("receipt-bound apply state is mixed or conflicting")


def apply_install_with_receipt(
    codex_home: Path,
    agents_language: str,
    receipt: dict | Path,
    on_touched: Callable[[str, str], None] | None = None,
) -> tuple[list[tuple[str, str]], Path | None]:
    codex_home = validate_codex_home(codex_home)
    with apply_lock(codex_home):
        receipt = (
            read_plan_receipt(receipt)
            if isinstance(receipt, Path)
            else validate_plan_receipt(receipt)
        )
        restore_journal = read_managed_json(
            codex_home, RESTORE_JOURNAL_RELATIVE, "restore transaction"
        )
        if restore_journal is not None:
            raise InstallError("cannot apply while a restore transaction is unfinished")
        apply_document_raw = read_managed_json(
            codex_home,
            APPLY_RECEIPT_JOURNAL_RELATIVE,
            "receipt-bound apply transaction",
        )
        journal = read_journal(codex_home)
        if apply_document_raw is None:
            if journal is not None:
                raise InstallError(
                    "unfinished unbound install transaction; continue it through the compatible internal recovery path"
                )
            plans = verify_plan_receipt_current(receipt, codex_home, agents_language)
            if not plans:
                return [], None
            apply_document = prepare_receipt_bound_apply(codex_home, receipt, plans)
            journal = journal_document(plans, agents_language)
            create_journal(codex_home, journal)
        else:
            apply_document = validate_apply_receipt_journal(apply_document_raw)
            if (
                apply_document["plan_digest"] != receipt["plan_digest"]
                or apply_document["source"] != receipt["source"]
                or apply_document["target"] != receipt["target"]
                or receipt["agents_language"] != agents_language
            ):
                raise InstallError("unfinished apply belongs to another plan receipt")
            if receipt["source"] != source_package_identity():
                raise InstallError("source package drifted during apply recovery")
            if receipt["target"] != target_identity(codex_home):
                raise InstallError("target identity changed during apply recovery")
            if journal is not None:
                if journal["install_contract_sha256"] != install_contract_sha256():
                    raise InstallError("unfinished apply belongs to another install contract")
                if journal["agents_language"] != agents_language:
                    raise InstallError("unfinished apply uses a different AGENTS language")
                status, classifications = classify_journal(codex_home, journal)
                if status == "PARTIAL_CONFLICT":
                    raise InstallError("unfinished apply has conflicting targets")
                recover_claimed_writes(codex_home, journal, classifications)
                plans, _ = plan_install(codex_home, agents_language, journal)
                validate_recovery_plan(plans, journal)
            else:
                verify_restore_target_backups(
                    codex_home, apply_document["restore_targets"]
                )
                recovery_status = classify_receipt_bound_apply(
                    codex_home, apply_document
                )
                if recovery_status == "PREPARED":
                    plans = verify_plan_receipt_current(
                        receipt, codex_home, agents_language
                    )
                    expected_apply_document = receipt_bound_apply_document(
                        receipt, plans
                    )
                    if expected_apply_document != apply_document:
                        raise InstallError(
                            "prepared apply metadata does not match the plan receipt"
                        )
                    journal = journal_document(plans, agents_language)
                    create_journal(codex_home, journal)
                else:
                    # The only journal-free completion state is exact candidate
                    # postimages plus the already durable restore receipt.
                    plans = []
        plans = bind_receipt_preconditions(plans, apply_document)
        if journal is not None:
            plans = bind_journal_write_recovery(plans, journal, codex_home)
        verify_restore_target_backups(codex_home, apply_document["restore_targets"])
        touched = apply_plans(plans, codex_home, on_touched)
        verify_candidate_postimages(codex_home, apply_document)
        receipt_path = ensure_restore_receipt(
            codex_home,
            apply_document,
            may_create=journal is not None,
        )
        if journal is not None:
            finish_journal(codex_home, journal)
        meta_path = codex_home / APPLY_RECEIPT_JOURNAL_RELATIVE
        current_meta = read_managed_json(
            codex_home,
            APPLY_RECEIPT_JOURNAL_RELATIVE,
            "receipt-bound apply transaction",
        )
        if validate_apply_receipt_journal(current_meta) != apply_document:
            raise InstallError("receipt-bound apply transaction changed before cleanup")
        meta_path.unlink()
        fsync_directory(meta_path.parent)
        return touched, receipt_path


def read_restore_receipt(path: Path) -> dict:
    return validate_restore_receipt(read_strict_json(path, "restore"))


def file_state(path: Path, codex_home: Path) -> tuple[bool, str | None, int | None]:
    content = safe_existing_bytes(path, codex_home)
    if content is None:
        return False, None, None
    return (
        True,
        sha256_bytes(content),
        path.stat(follow_symlinks=False).st_mode & 0o777,
    )


def state_matches(target: dict, prefix: str, state: tuple[bool, str | None, int | None]) -> bool:
    return state == (
        target[f"{prefix}_exists"],
        target[f"{prefix}_sha256"],
        target[f"{prefix}_mode"],
    )


def validate_restore_journal(document: object) -> dict:
    if not isinstance(document, dict) or set(document) != {
        "candidate_backups",
        "candidate_staging",
        "format_version",
        "package_id",
        "receipt_digest",
        "target",
    }:
        raise InstallError("restore transaction has an unknown schema")
    if document["format_version"] != 2 or document["package_id"] != SKILL_NAME:
        raise InstallError("restore transaction identity mismatch")
    if not validate_optional_hash(document["receipt_digest"]) or document["receipt_digest"] is None:
        raise InstallError("restore transaction has an invalid receipt digest")
    validate_target_identity(document["target"])
    if not isinstance(document["candidate_backups"], dict) or not all(
        isinstance(key, str) and (value is None or isinstance(value, str))
        for key, value in document["candidate_backups"].items()
    ):
        raise InstallError("restore transaction has invalid candidate backups")
    if not isinstance(document["candidate_staging"], dict) or not all(
        isinstance(key, str) and (value is None or isinstance(value, str))
        for key, value in document["candidate_staging"].items()
    ):
        raise InstallError("restore transaction has invalid candidate staging")
    return document


def atomic_restore_prior(
    codex_home: Path,
    target: dict,
    candidate_staging_relative: str | None,
) -> None:
    path = codex_home / target["relative"]
    current = file_state(path, codex_home)
    if state_matches(target, "prior", current):
        if candidate_staging_relative is not None and not state_matches(
            target,
            "candidate",
            file_state(codex_home / candidate_staging_relative, codex_home),
        ):
            raise InstallError(
                f"candidate restore staging mismatch: {target['relative']}"
            )
        return

    candidate_staging = (
        codex_home / candidate_staging_relative
        if candidate_staging_relative is not None
        else None
    )
    if target["candidate_exists"]:
        if candidate_staging is None:
            raise InstallError(f"missing candidate restore staging: {target['relative']}")
        staged_state = file_state(candidate_staging, codex_home)
        if state_matches(target, "candidate", current):
            if staged_state != (False, None, None):
                raise InstallError(
                    f"candidate restore staging collision: {target['relative']}"
                )
            candidate_staging.parent.mkdir(parents=True, exist_ok=True)
            rename_noreplace(path, candidate_staging)
            fsync_directory(path.parent)
            if candidate_staging.parent != path.parent:
                fsync_directory(candidate_staging.parent)
            if not state_matches(
                target, "candidate", file_state(candidate_staging, codex_home)
            ):
                preserved = return_claimed_path(candidate_staging, path)
                raise InstallError(
                    f"restore target changed while being claimed: {target['relative']}; "
                    f"preserved at {preserved}"
                )
        elif not (
            current == (False, None, None)
            and state_matches(target, "candidate", staged_state)
        ):
            raise InstallError(f"restore target drifted: {target['relative']}")
    elif current != (False, None, None) or candidate_staging is not None:
        raise InstallError(f"restore target drifted: {target['relative']}")

    if not target["prior_exists"]:
        if candidate_staging is not None and not state_matches(
            target, "candidate", file_state(candidate_staging, codex_home)
        ):
            raise InstallError(
                f"candidate restore staging mismatch: {target['relative']}"
            )
        return
    backup = codex_home / target["prior_backup_relative"]
    backup_content = safe_existing_bytes(backup, codex_home)
    if backup_content is None or sha256_bytes(backup_content) != target["prior_sha256"]:
        raise InstallError(f"prior restore vault mismatch: {target['relative']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.restore.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(backup_content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, target["prior_mode"])
        if file_state(path, codex_home) != (False, None, None):
            raise InstallError(f"restore target collision: {target['relative']}")
        rename_noreplace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()
    if not state_matches(target, "prior", file_state(path, codex_home)):
        raise InstallError(f"restored prior postimage mismatch: {target['relative']}")
    if candidate_staging is not None and not state_matches(
        target, "candidate", file_state(candidate_staging, codex_home)
    ):
        raise InstallError(f"candidate restore staging mismatch: {target['relative']}")


def restore_install(
    codex_home: Path,
    receipt: dict | Path,
    on_restored: Callable[[str, str], None] | None = None,
) -> list[tuple[str, str]]:
    codex_home = validate_codex_home(codex_home)
    with apply_lock(codex_home):
        receipt = (
            read_restore_receipt(receipt)
            if isinstance(receipt, Path)
            else validate_restore_receipt(receipt)
        )
        if receipt["target"] != target_identity(codex_home):
            raise InstallError("restore receipt belongs to another target identity")
        if receipt["source"] != source_package_identity():
            raise InstallError("restore receipt belongs to another source package")
        if read_journal(codex_home) is not None or read_managed_json(
            codex_home,
            APPLY_RECEIPT_JOURNAL_RELATIVE,
            "receipt-bound apply transaction",
        ) is not None:
            raise InstallError("cannot restore while an apply transaction is unfinished")
        verify_restore_target_backups(codex_home, receipt["targets"])
        journal_raw = read_managed_json(
            codex_home, RESTORE_JOURNAL_RELATIVE, "restore transaction"
        )
        if journal_raw is None:
            for target in receipt["targets"]:
                if not state_matches(
                    target,
                    "candidate",
                    file_state(codex_home / target["relative"], codex_home),
                ):
                    raise InstallError(
                        f"candidate postimage drifted before restore: {target['relative']}"
                    )
            candidate_backups = {}
            candidate_staging = {}
            for target in receipt["targets"]:
                backup_relative = None
                if target["candidate_exists"]:
                    backup_relative = str(
                        vault_relative(
                            "candidate", receipt["receipt_digest"], target["relative"]
                        )
                    )
                    preserve_snapshot(
                        codex_home / target["relative"],
                        codex_home / backup_relative,
                        codex_home,
                        target["candidate_sha256"],
                        target["candidate_mode"],
                    )
                candidate_backups[target["relative"]] = backup_relative
                candidate_staging[target["relative"]] = (
                    str(
                        vault_relative(
                            "staged-candidate",
                            receipt["receipt_digest"],
                            target["relative"],
                        )
                    )
                    if target["candidate_exists"]
                    else None
                )
            journal = {
                "candidate_backups": candidate_backups,
                "candidate_staging": candidate_staging,
                "format_version": 2,
                "package_id": SKILL_NAME,
                "receipt_digest": receipt["receipt_digest"],
                "target": receipt["target"],
            }
            write_new_json(codex_home / RESTORE_JOURNAL_RELATIVE, journal)
        else:
            journal = validate_restore_journal(journal_raw)
            if (
                journal["receipt_digest"] != receipt["receipt_digest"]
                or journal["target"] != receipt["target"]
                or set(journal["candidate_backups"])
                != {target["relative"] for target in receipt["targets"]}
                or set(journal["candidate_staging"])
                != {target["relative"] for target in receipt["targets"]}
            ):
                raise InstallError("unfinished restore belongs to another receipt")
        for target in receipt["targets"]:
            candidate_backup = journal["candidate_backups"][target["relative"]]
            candidate_staging = journal["candidate_staging"][target["relative"]]
            expected_candidate_backup = (
                str(
                    vault_relative(
                        "candidate", receipt["receipt_digest"], target["relative"]
                    )
                )
                if target["candidate_exists"]
                else None
            )
            if candidate_backup != expected_candidate_backup:
                raise InstallError(
                    f"restore transaction has invalid candidate vault path: {target['relative']}"
                )
            expected_candidate_staging = (
                str(
                    vault_relative(
                        "staged-candidate",
                        receipt["receipt_digest"],
                        target["relative"],
                    )
                )
                if target["candidate_exists"]
                else None
            )
            if candidate_staging != expected_candidate_staging:
                raise InstallError(
                    f"restore transaction has invalid candidate staging path: {target['relative']}"
                )
            if target["candidate_exists"]:
                candidate = safe_existing_bytes(
                    codex_home / candidate_backup, codex_home
                )
                if (
                    candidate is None
                    or sha256_bytes(candidate) != target["candidate_sha256"]
                    or (codex_home / candidate_backup).stat(follow_symlinks=False).st_mode
                    & 0o777
                    != target["candidate_mode"]
                ):
                    raise InstallError(f"candidate restore vault mismatch: {target['relative']}")
            elif candidate_backup is not None:
                raise InstallError(f"absent candidate has a vault path: {target['relative']}")
            atomic_restore_prior(codex_home, target, candidate_staging)
            result = target["prior_sha256"] or "<absent>"
            if on_restored is not None:
                on_restored(target["relative"], result)
        journal_path = codex_home / RESTORE_JOURNAL_RELATIVE
        if validate_restore_journal(
            read_managed_json(codex_home, RESTORE_JOURNAL_RELATIVE, "restore transaction")
        ) != journal:
            raise InstallError("restore transaction changed before cleanup")
        journal_path.unlink()
        fsync_directory(journal_path.parent)
        return [
            (target["relative"], target["prior_sha256"] or "<absent>")
            for target in receipt["targets"]
        ]


def artifact_receipts(
    codex_home: Path,
    root_relative: Path,
    artifact_label: str,
) -> list[dict[str, str]]:
    root = codex_home / root_relative
    if root.is_symlink():
        raise InstallError(f"{artifact_label} root is a symlink: {root}")
    if not root.exists():
        return []
    if not root.is_dir():
        raise InstallError(f"{artifact_label} root is not a directory: {root}")
    receipts = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise InstallError(f"{artifact_label} contains a symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if len(relative.parts) < 2 or re.fullmatch(r"[0-9a-f]{64}", relative.parts[0]) is None:
            raise InstallError(f"{artifact_label} has an unknown artifact: {relative}")
        expected = relative.parts[0]
        actual = sha256_bytes(path.read_bytes())
        if actual != expected:
            raise InstallError(f"{artifact_label} hash mismatch: {relative}")
        original = str(Path(*relative.parts[1:]))
        receipts.append(
            {
                "original_path": original,
                "receipt_path": relative.as_posix(),
                "sha256": actual,
            }
        )
    return receipts


def quarantine_receipts(codex_home: Path) -> list[str]:
    return [
        "QUARANTINED {original_path} {receipt_path} {sha256}".format(**receipt)
        for receipt in artifact_receipts(
            codex_home,
            QUARANTINE_RELATIVE,
            "retired-path quarantine",
        )
    ]


def retirement_staging_receipts(codex_home: Path) -> list[str]:
    return [
        "RETAINED_STAGING {original_path} {receipt_path} {sha256}".format(
            **receipt
        )
        for receipt in artifact_receipts(
            codex_home,
            STAGING_RELATIVE,
            "retirement receipt",
        )
    ]


def restore_receipt_reports(codex_home: Path) -> list[dict[str, str]]:
    root = codex_home / RESTORE_RECEIPTS_RELATIVE
    if root.is_symlink():
        raise InstallError(f"restore receipt root is a symlink: {root}")
    if not root.exists():
        return []
    if not root.is_dir():
        raise InstallError(f"restore receipt root is not a directory: {root}")
    reports = []
    for path in sorted(root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            raise InstallError(f"invalid restore receipt artifact: {path}")
        try:
            receipt = validate_restore_receipt(
                strict_json_loads(path.read_text(encoding="utf-8"), "restore receipt")
            )
        except UnicodeError as error:
            raise InstallError(f"restore receipt is unreadable: {path}: {error}") from error
        if receipt["target"] != target_identity(codex_home):
            raise InstallError(f"restore receipt target identity mismatch: {path}")
        verify_restore_target_backups(codex_home, receipt["targets"])
        states = []
        for target in receipt["targets"]:
            current = file_state(codex_home / target["relative"], codex_home)
            if state_matches(target, "candidate", current):
                states.append("candidate")
            elif state_matches(target, "prior", current):
                states.append("prior")
            else:
                states.append("conflict")
        if "conflict" in states:
            status = "CONFLICT"
        elif set(states) == {"candidate"}:
            status = "READY"
        elif set(states) == {"prior"}:
            status = "RESTORED"
            for target in receipt["targets"]:
                if not target["candidate_exists"]:
                    continue
                candidate = codex_home / vault_relative(
                    "candidate", receipt["receipt_digest"], target["relative"]
                )
                content = safe_existing_bytes(candidate, codex_home)
                if content is None or sha256_bytes(content) != target["candidate_sha256"]:
                    raise InstallError(
                        f"displaced candidate vault mismatch: {target['relative']}"
                    )
        else:
            status = "PARTIAL"
        reports.append(
            {
                "receipt_digest": receipt["receipt_digest"],
                "receipt_path": str(path.relative_to(codex_home)),
                "status": status,
            }
        )
    return reports


def doctor_report(codex_home: Path, agents_language: str) -> dict:
    """Return a stable, read-only diagnostic report for text or JSON rendering."""
    codex_home = validate_codex_home(codex_home)
    load_manifest()
    locked = lock_path(codex_home).exists() or lock_path(codex_home).is_symlink()
    report = {
        "agents_language": agents_language,
        "codex_home": str(codex_home),
        "format_version": 1,
        "healthy": False,
        "locked": locked,
        "package_id": SKILL_NAME,
        "quarantined": [],
        "retirement_receipts": [],
        "restore_receipts": [],
        "status": "ACTIVE_APPLY" if locked else "UNKNOWN",
        "targets": [],
    }
    if locked:
        return report
    restore_journal = read_managed_json(
        codex_home, RESTORE_JOURNAL_RELATIVE, "restore transaction"
    )
    if restore_journal is not None:
        validate_restore_journal(restore_journal)
        report["status"] = "RESTORE_PARTIAL"
        report["targets"] = [
            {"path": relative, "state": "RESTORE_PENDING"}
            for relative in sorted(restore_journal["candidate_backups"])
        ]
        report["restore_receipts"] = restore_receipt_reports(codex_home)
        return report
    journal = read_journal(codex_home)
    if journal is not None:
        status, classifications = classify_journal(codex_home, journal)
        if journal["install_contract_sha256"] != install_contract_sha256():
            status = "INCOMPATIBLE_TRANSACTION"
        report["status"] = status
        report["targets"] = [
            {"path": relative, "state": classification.upper()}
            for relative, classification in classifications
        ]
    else:
        state_exists = (
            safe_existing_bytes(codex_home / STATE_RELATIVE, codex_home) is not None
        )
        plans, _ = plan_install(codex_home, agents_language)
        report["healthy"] = True
        if not state_exists:
            report["status"] = "NOT_INSTALLED"
        elif plans:
            report["status"] = "UPDATE_AVAILABLE"
            report["targets"] = [
                {"path": plan.relative, "state": "PENDING"} for plan in plans
            ]
        else:
            report["status"] = "HEALTHY"
    report["quarantined"] = artifact_receipts(
        codex_home,
        QUARANTINE_RELATIVE,
        "retired-path quarantine",
    )
    report["retirement_receipts"] = artifact_receipts(
        codex_home,
        STAGING_RELATIVE,
        "retirement receipt",
    )
    report["restore_receipts"] = restore_receipt_reports(codex_home)
    return report


def render_doctor_report(report: dict) -> list[str]:
    lines = []
    if report["locked"]:
        lines.append(f"LOCKED {lock_path(Path(report['codex_home']))}")
    status = report["status"]
    if status == "UPDATE_AVAILABLE":
        lines.append(f"DOCTOR {status} {len(report['targets'])}")
    else:
        lines.append(f"DOCTOR {status}")
    lines.extend(
        f"TARGET {target['path']} {target['state']}" for target in report["targets"]
    )
    lines.extend(
        "RESTORE_RECEIPT {receipt_path} {status} {receipt_digest}".format(**receipt)
        for receipt in report["restore_receipts"]
    )
    lines.extend(
        "QUARANTINED {original_path} {receipt_path} {sha256}".format(**receipt)
        for receipt in report["quarantined"]
    )
    lines.extend(
        "RETAINED_STAGING {original_path} {receipt_path} {sha256}".format(
            **receipt
        )
        for receipt in report["retirement_receipts"]
    )
    return lines


def doctor(codex_home: Path, agents_language: str) -> tuple[bool, list[str]]:
    report = doctor_report(codex_home, agents_language)
    return report["healthy"], render_doctor_report(report)


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
    action.add_argument(
        "--restore-receipt",
        type=Path,
        metavar="ABS",
        help="restore exact prior state from a target-bound receipt",
    )
    action.add_argument(
        "--doctor",
        action="store_true",
        help="diagnose managed state and unfinished transactions without writes",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="check or doctor output format (default: text)",
    )
    parser.add_argument(
        "--plan-receipt",
        type=Path,
        metavar="ABS",
        help="strict JSON receipt previously emitted by --check --format json",
    )
    args = parser.parse_args()
    if args.format != "text" and not (args.doctor or args.check):
        parser.error("--format is only valid with --check or --doctor")
    if args.apply and args.plan_receipt is None:
        parser.error("--apply requires --plan-receipt ABS")
    if not args.apply and args.plan_receipt is not None:
        parser.error("--plan-receipt is only valid with --apply")
    try:
        codex_home = validate_codex_home(args.codex_home)
        if args.doctor:
            report = doctor_report(codex_home, args.agents_language)
            if args.format == "json":
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                for line in render_doctor_report(report):
                    print(line)
            return 0 if report["healthy"] else 1
        if args.restore_receipt is not None:
            restored = restore_install(
                codex_home,
                args.restore_receipt,
                lambda relative, actual: print(
                    f"RESTORED {relative} {actual}", flush=True
                ),
            )
            print(f"PASS: restored {len(restored)} path(s)")
            return 0
        if args.apply:
            touched, restore_receipt_path = apply_install_with_receipt(
                codex_home,
                args.agents_language,
                args.plan_receipt,
                lambda relative, actual: print(
                    f"TOUCHED {relative} {actual}", flush=True
                ),
            )
            if restore_receipt_path is not None:
                print(f"RESTORE_RECEIPT {restore_receipt_path}")
            print(f"PASS: installed {len(touched)} changed path(s)")
            return 0
        with apply_lock(codex_home):
            plans, _ = plan_install(codex_home, args.agents_language)
            receipt = plan_receipt_document(codex_home, args.agents_language, plans)
        if args.format == "json":
            print(json.dumps(receipt, indent=2, sort_keys=True))
            return 0
        for plan in plans:
            desired = plan.desired_sha256 or "<absent>"
            print(f"WOULD_TOUCH {plan.relative} {desired}")
        print(f"PASS: preflight complete; {len(plans)} path(s) would change")
        return 0
    except (InstallError, OSError, UnicodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
