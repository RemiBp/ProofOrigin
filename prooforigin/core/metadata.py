"""Metadata validation helpers."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import get_settings

logger = get_logger(__name__)


DEFAULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 512},
        "description": {"type": "string", "maxLength": 5000},
        "license": {"type": "string", "maxLength": 128},
        "tags": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 64},
            "maxItems": 64,
        },
        "original_url": {"type": "string", "format": "uri"},
        "author": {"type": "string", "maxLength": 255},
        "language": {"type": "string", "pattern": "^[a-zA-Z-]{2,10}$"},
        "jurisdiction": {"type": "string", "maxLength": 64},
        "version": {"type": "string", "maxLength": 64},
        "checksum": {"type": "string", "maxLength": 128},
    },
}


@lru_cache()
def _load_schema() -> Draft202012Validator:
    settings = get_settings()
    schema_path = settings.metadata_schema_path
    schema: dict[str, Any] = DEFAULT_SCHEMA
    if schema_path and Path(schema_path).exists():
        try:
            schema = json.loads(Path(schema_path).read_text())
        except Exception as exc:  # pragma: no cover - IO
            logger.warning("metadata_schema_failed", error=str(exc))
    return Draft202012Validator(schema)


def validate_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    validator = _load_schema()
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if errors:
        messages = [f"{'.'.join(map(str, err.path)) or '<root>'}: {err.message}" for err in errors]
        raise ValidationError(
            "Metadata validation failed: " + "; ".join(messages)
        )
    return payload


__all__ = ["validate_metadata"]

