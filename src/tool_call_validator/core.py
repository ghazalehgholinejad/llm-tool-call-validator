import json
import math
from itertools import islice

from jsonschema import Draft202012Validator
from referencing import Registry

MAX_BYTES = 65536
MAX_ERRORS = 20


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Non-finite JSON number")


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite JSON number")
    return result


def _failure(code, message, path=""):
    return {"valid": False, "errors": [{"code": code, "path": path, "message": message}]}


def _pointer(parts):
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def validate_call(raw: str, schemas: dict) -> dict:
    """Validate a normalized call; schemas must be trusted local configuration.

    Does not execute tools, coerce arguments, or fetch remote schema references.
    Invalid schema configuration raises an exception rather than blaming a call.
    """
    if len(raw.encode("utf-8")) > MAX_BYTES:
        return _failure("size_limit", "Call exceeds 65536 UTF-8 bytes")
    try:
        call = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    except (ValueError, RecursionError):
        return _failure("invalid_json", "Expected strict JSON without duplicate keys or non-finite numbers")
    if not isinstance(call, dict) or set(call) != {"name", "arguments"}:
        return _failure("invalid_envelope", "Expected exactly name and arguments fields")
    if not isinstance(call["name"], str):
        return _failure("invalid_envelope", "Name must be a string", "/name")
    if call["name"] not in schemas:
        return _failure("unknown_tool", "Tool is not registered", "/name")
    if not isinstance(call["arguments"], dict):
        return _failure("invalid_envelope", "Arguments must be an object", "/arguments")
    schema = schemas[call["name"]]
    Draft202012Validator.check_schema(schema)
    # Explicit empty registry disables the default remote retrieval behavior.
    validator = Draft202012Validator(schema, registry=Registry())
    try:
        errors = list(islice(validator.iter_errors(call["arguments"]), MAX_ERRORS + 1))
    except RecursionError:
        return _failure("nesting_limit", "Call nesting exceeds runtime validation limits")
    if errors:
        return {"valid": False, "errors": [
            {"code": "schema_" + e.validator,
             "path": "/arguments" + _pointer(e.absolute_path), "message": e.message}
            for e in errors[:MAX_ERRORS]
        ], "errors_truncated": len(errors) > MAX_ERRORS}
    return {"valid": True, "errors": [], "call": call}
