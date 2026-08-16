"""Strict, monotonic evidence-tier chain validation."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Sequence

from .campaign import EvaluationError, _require_exact_keys, _require_sha256, _require_string


SCHEMA_VERSION = "evidence-tier.v1"
TIERS = ("implemented", "verified-local", "verified-ci", "verified-target", "pilot-signed")
DOCUMENT_KEYS = {
    "schema_version",
    "tier",
    "revision",
    "package_digest",
    "artifact_digest",
    "predecessor",
    "provenance",
}
PREDECESSOR_KEYS = {"tier", "digest"}
PROVENANCE_KEYS = {
    "implemented": {
        "source_tree_sha256",
        "diff_sha256",
        "implementation_receipt_sha256",
    },
    "verified-local": {"command", "exit_code", "environment_sha256", "result_sha256"},
    "verified-ci": {"provider", "run_id", "run_url", "revision", "result_sha256"},
    "verified-target": {
        "target_id",
        "environment_sha256",
        "revision",
        "package_digest",
        "receipt_sha256",
    },
    "pilot-signed": {
        "authority",
        "authority_id",
        "signed_at",
        "signature_sha256",
        "target_receipt_sha256",
    },
}


def canonical_digest(document: dict) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_timestamp(value: object, location: str) -> None:
    text = _require_string(value, location)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvaluationError(f"{location} must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise EvaluationError(f"{location} must include a timezone")


def validate_evidence_chain(documents: Sequence[dict]) -> None:
    if not documents:
        raise EvaluationError("evidence chain must contain at least one document")
    expected_revision = None
    expected_package = None
    for index, raw_document in enumerate(documents):
        location = f"evidence[{index}]"
        document = _require_exact_keys(raw_document, DOCUMENT_KEYS, location)
        if document["schema_version"] != SCHEMA_VERSION:
            raise EvaluationError(f"{location}.schema_version must be {SCHEMA_VERSION}")
        tier = _require_string(document["tier"], f"{location}.tier")
        if tier not in TIERS:
            raise EvaluationError(f"{location}.tier is invalid")
        if TIERS.index(tier) != index:
            raise EvaluationError(
                f"{location}.tier skips or reorders the required predecessor chain"
            )
        revision = _require_string(document["revision"], f"{location}.revision")
        package_digest = _require_sha256(
            document["package_digest"], f"{location}.package_digest"
        )
        _require_sha256(document["artifact_digest"], f"{location}.artifact_digest")
        if expected_revision is None:
            expected_revision = revision
            expected_package = package_digest
        elif revision != expected_revision or package_digest != expected_package:
            raise EvaluationError(
                f"{location} revision/package does not match the evidence chain"
            )

        predecessor = document["predecessor"]
        if index == 0:
            if predecessor is not None:
                raise EvaluationError("implemented evidence must have null predecessor")
        else:
            predecessor = _require_exact_keys(
                predecessor, PREDECESSOR_KEYS, f"{location}.predecessor"
            )
            expected_tier = TIERS[index - 1]
            if predecessor["tier"] != expected_tier:
                raise EvaluationError(
                    f"{location}.predecessor must name exact tier {expected_tier}"
                )
            digest = _require_sha256(
                predecessor["digest"], f"{location}.predecessor.digest"
            )
            if digest != canonical_digest(documents[index - 1]):
                raise EvaluationError(
                    f"{location}.predecessor.digest does not match predecessor document"
                )

        provenance = _require_exact_keys(
            document["provenance"], PROVENANCE_KEYS[tier], f"{location}.provenance"
        )
        for key, value in provenance.items():
            field = f"{location}.provenance.{key}"
            if key.endswith("sha256") or key == "package_digest":
                _require_sha256(value, field)
            elif key == "exit_code":
                if value != 0 or isinstance(value, bool):
                    raise EvaluationError(f"{field} must be integer zero")
            elif key == "signed_at":
                _validate_timestamp(value, field)
            else:
                _require_string(value, field)
        if tier in {"verified-ci", "verified-target"} and provenance["revision"] != revision:
            raise EvaluationError(f"{location}.provenance.revision does not match revision")
        if tier == "verified-target" and provenance["package_digest"] != package_digest:
            raise EvaluationError(
                f"{location}.provenance.package_digest does not match package_digest"
            )
        if tier == "pilot-signed":
            target_receipt = documents[index - 1]["provenance"]["receipt_sha256"]
            if provenance["target_receipt_sha256"] != target_receipt:
                raise EvaluationError(
                    f"{location}.provenance.target_receipt_sha256 does not match "
                    "verified-target receipt_sha256"
                )


def load_evidence_chain(paths: Sequence[Path]) -> list[dict]:
    from .campaign import load_json

    documents = [load_json(path) for path in paths]
    validate_evidence_chain(documents)
    return documents
