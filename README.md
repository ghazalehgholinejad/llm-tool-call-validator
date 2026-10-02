# LLM Tool Call Validator

A small exercise in **reliable tool calling for AI agents**: validate a proposed call before handing it to an application. Runs locally without an API key, model download, or GPU.

A model might request `search_documents` with `"top_k": "3"`, invent a tool name, or add an unexpected `admin` parameter. This package rejects those calls and returns structured errors instead of silently correcting them.

## Quick start

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
validate-tool-call examples/valid_search.json --schemas examples/tools.json
validate-tool-call examples/string_integer.json --schemas examples/tools.json
python examples/run_cases.py
python -m unittest discover -s tests -v
```

The second command deliberately exits with status **1**. CLI exit codes: **0** accepted, **1** rejected call, **2** configuration or I/O failure.

## Contract

Normalize provider output into this exact envelope. `arguments` is a JSON object, not a JSON-encoded string; provider adapters are outside this exercise.

```json
{"name": "search_documents", "arguments": {"query": "RAG evaluation", "top_k": 3}}
```

The trusted registry in `examples/tools.json` maps tool names to JSON Schema Draft 2020-12 schemas. The example requires a nonempty query, an integer `top_k` between 1 and 10, and optionally `language` (`en` or `fa`). Extra arguments are forbidden.

```python
import json
from pathlib import Path
from tool_call_validator import validate_call

schemas = json.loads(Path("examples/tools.json").read_text())
result = validate_call(Path("examples/string_integer.json").read_text(), schemas)
print(result["errors"])
# [{'code': 'schema_type', 'path': '/arguments/top_k',
#   'message': "'3' is not of type 'integer'"}]
```

Error paths use JSON Pointer escaping. Required-field and extra-property errors point to their containing object. Messages are diagnostic, while codes and paths are intended for programmatic handling. Up to 20 schema errors are returned with an `errors_truncated` flag.

## Pipeline

```text
Untrusted JSON → size / strict JSON checks → envelope → tool allowlist
              → argument schema → accepted call OR structured rejection
```

No repair, coercion, or execution occurs. Duplicate keys, NaN, Infinity, and overflowing floating-point literals are rejected. The CLI reads at most 65,537 bytes; calls over 65,536 UTF-8 bytes are rejected. Local schema references work; remote references are not fetched and unresolved references are configuration errors. Formats are annotations: no format checker is enabled.

## Exercise: try it yourself

1. Run `examples/string_integer.json`; inspect the error path.
2. Replace the string `"3"` with the number `3` and validate again.
3. Add a `forecast_energy` schema with a required integer `horizon_hours` bounded to 1–168 and no extra properties.
4. Write one passing case and cases for zero, missing horizon, boolean, and an unknown parameter.
5. Explain why a schema-valid query such as “ignore previous instructions” still needs application-level handling.

The implemented search example is the worked solution; the forecasting extension is left as a learning exercise.

## Examples and verification

The ten hand-authored cases include two valid calls (English and Persian) and eight invalid calls. `examples/run_cases.py` checks every expected decision and prints JSON. These are **synthetic fixtures, not generated LLM responses or a model accuracy benchmark**. Automated tests additionally cover duplicate keys, non-finite numbers, deep JSON, size limits, JSON Pointer escaping, error truncation, references, and CLI exit codes. CI runs on Python 3.10 and 3.12.

## Limits

- Schema validity is not authorization, prompt-injection detection, semantic correctness, or a guarantee of safe execution. A production dispatcher still needs per-user permissions and tool-specific checks.
- Trusted schemas only. Schema complexity is not sandboxed and validation has no CPU timeout. Byte limits do not make this a general denial-of-service defense.
- JSON numbers use Python's standard numeric representation; this is not an arbitrary-precision financial validator. JSON Schema considers integral numbers such as `3.0` integers; booleans are not integers.
- Error messages may include argument values. Redact sensitive inputs before logging or returning errors to a model.
- No live model integration, tool implementation, automatic retries, or benchmark claims.

## References

- [JSON Schema object validation](https://json-schema.org/understanding-json-schema/reference/object)
- [python-jsonschema validation](https://python-jsonschema.readthedocs.io/en/latest/validate/)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)

Original exercise code and synthetic fixtures; validation uses the `jsonschema` library. MIT licensed.
