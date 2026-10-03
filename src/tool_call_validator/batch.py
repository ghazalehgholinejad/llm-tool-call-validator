"""Bounded JSON Lines validation and aggregate reporting."""
from collections import Counter

from jsonschema import Draft202012Validator

from .core import MAX_BYTES, _failure, validate_call

MAX_CALLS = 1000


def validate_batch(stream, schemas: dict) -> dict:
    """Read a binary JSONL stream. Each physical line is one proposed call.

    Blank lines are rejected records, not skipped. Configuration errors and
    excess record counts abort the report; call errors do not stop the batch.
    """
    if not isinstance(schemas, dict):
        raise ValueError("Schema registry must be an object")
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    results = []
    counts = Counter()
    while True:
        data = stream.readline(MAX_BYTES + 3)
        if not data:
            break
        if len(results) == MAX_CALLS:
            raise ValueError(f"Batch exceeds {MAX_CALLS} records; no report produced")
        # Drain an oversized physical line without treating its tail as a call.
        oversized = len(data) == MAX_BYTES + 3 and not data.endswith(b"\n")
        if oversized:
            while data and not data.endswith(b"\n"):
                data = stream.readline(MAX_BYTES + 3)
            result = _failure("size_limit", "Call exceeds 65536 UTF-8 bytes")
        else:
            payload = data.removesuffix(b"\n").removesuffix(b"\r")
            if len(payload) > MAX_BYTES:
                result = _failure("size_limit", "Call exceeds 65536 UTF-8 bytes")
            else:
                try:
                    result = validate_call(payload.decode("utf-8"), schemas)
                except UnicodeDecodeError:
                    result = _failure("invalid_encoding", "Call must be UTF-8")
        # Count records containing each code, not individual error occurrences.
        counts.update({error["code"] for error in result["errors"]})
        results.append({"line": len(results) + 1, **result})
    if not results:
        raise ValueError("Batch is empty; provide at least one JSONL record")
    accepted = sum(row["valid"] for row in results)
    return {
        "valid": accepted == len(results),
        "summary": {"total": len(results), "accepted": accepted,
                    "rejected": len(results) - accepted,
                    "records_by_error_code": dict(sorted(counts.items()))},
        "results": results,
    }
