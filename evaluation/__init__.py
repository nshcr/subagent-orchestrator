"""Deterministic, stdlib-only evaluation campaign validation and reporting."""

from .campaign import EvaluationError, build_report, load_json, validate_campaign

__all__ = ["EvaluationError", "build_report", "load_json", "validate_campaign"]
