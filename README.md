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

The `string_integer.json` validation deliberately exits with status **1**. CLI exit codes: **0** accepted, **1** rejected call, **2** configuration or I/O failure.

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

## Batch validation and saved reports (v0.2)

Validate a JSON Lines file with one complete call per physical line:

```bash
validate-tool-call examples/mixed_calls.jsonl --schemas examples/tools.json --batch --output report.json
```

This example deliberately exits **1**: two calls pass and five fail. It covers document search and the new `forecast_energy` schema. The latter requires `site_id` matching `site-001` and `horizon_hours` from 1 to 168; optional `resolution` is `hourly` or `daily`. It validates a proposed request; no forecast is generated.

The report contains numbered per-line results and a summary:

```json
{
  "total": 7,
  "accepted": 2,
  "rejected": 5,
  "records_by_error_code": {
    "schema_additionalProperties": 1,
    "schema_minimum": 1,
    "schema_required": 1,
    "schema_type": 2
  }
}
```

Counts are **records containing a code**, so a record with two type errors counts once under `schema_type`. A record may count under several different codes. Counts cover the returned errors (at most 20 per record), not errors omitted by truncation.

- Blank lines and malformed JSON are rejected records. Invalid UTF-8 is `invalid_encoding` in both single and batch modes.
- LF and CRLF are supported; an ending newline does not add an empty record. The byte limit excludes the line ending.
- Oversized lines are drained in bounded chunks, rejected once, and processing continues with the next line.
- At most 1,000 records are accepted as input. Empty batches, excess records, invalid schemas, unresolved references, and I/O failures abort with exit **2** and no validation report. Schema syntax is checked for every registered tool; references are resolved when encountered during validation.
- `--output` works in either mode and refuses to overwrite existing files. Parent directories must exist. The same JSON is also printed to stdout. Reports contain accepted arguments and diagnostic values; handle them like input data.

```python
from tool_call_validator import validate_batch

with open("examples/mixed_calls.jsonl", "rb") as stream:
    report = validate_batch(stream, schemas)
print(report["summary"])
```

## Interactive HTML report (v0.3)

```bash
validate-tool-call examples/mixed_calls.jsonl --schemas examples/tools.json --batch --format html --output report.html
```

The example exits **1** because five calls are rejected; the report is still saved. Open `report.html` in a browser to see total/accepted/rejected counts, filter by status, and inspect error codes, JSON Pointer paths, and messages. Accepted arguments are expandable. Single-call reports work too: omit `--batch` and supply a JSON file.

The HTML is self-contained: no CDN, server, API key, or internet connection is needed to view it. All results remain readable without JavaScript; filter controls appear when JavaScript is enabled. The CLI still prints JSON to stdout and preserves existing exit codes and overwrite protection. `--format html` requires `--output`; the default saved format remains JSON. File extensions do not determine the format.

Untrusted values are HTML-escaped and never inserted into executable JavaScript. A restrictive content policy blocks external resources. Reports still contain diagnostic values and accepted arguments: do not publish reports containing private inputs. Rejected tool names and raw arguments are not retained by the validator; those cards show “Rejected call” with their available errors. Counts include the whole input even when cards are filtered. Browser printing reflects the current filter.

## Find recurring errors (v0.4)

HTML reports now include an error-frequency table, a text search box, an error-code selector, and a reset button. Use the same HTML export command above.

- **Combine filters:** status, exact error code, and search text must all match. Selecting an error while viewing accepted calls produces no matches; Reset restores all results.
- **Search:** case-insensitive literal substring matching over the card text, including expandable accepted arguments, error messages, paths, and line labels. Unicode NFKC normalization handles compatibility forms; this is not fuzzy or semantic search, and does not normalize Persian letter variants. Accepted argument strings remain JSON-escaped, so non-ASCII values there are searched by their displayed escapes.
- **Frequency:** counts records containing each returned error code, once per record per code. Sorted by descending count, then code. Counts remain for the full report while filtering; omitted errors are not counted.
- **Empty results:** an explicit no-match message and “Showing X of Y” counter clarify the active selection.

Everything still runs offline. Search uses text comparisons, not regular expressions or HTML insertion. With JavaScript disabled, the frequency table and all result cards remain visible; interactive controls stay hidden. Node.js is used only by the development interaction test, not by the Python package or exported report.

## Exercise: try it yourself

1. Run the mixed batch and inspect each rejected line.
2. Fix the five rejected forecasting calls and run again; expect seven accepted records and exit **0**. Use a new output filename.
3. Try horizons `1`, `168`, and `169` to inspect the boundary.
4. Add a blank line and a malformed JSON line; confirm later calls are still checked.
5. Explain why a schema-valid query such as “ignore previous instructions” still needs application-level handling.

Both search and forecasting schemas are implemented as worked examples. Extending a schema and diagnosing the report are the learning activities.

## Examples and verification

The original ten hand-authored single-call cases include two valid calls (English and Persian) and eight invalid calls. `examples/run_cases.py` checks every expected decision and prints JSON. These are **synthetic fixtures, not generated LLM responses or a model accuracy benchmark**. Automated tests additionally cover duplicate keys, non-finite numbers, deep JSON, size limits, JSON Pointer escaping, error truncation, references, and CLI exit codes. The batch fixture adds seven requests (two accepted, five rejected). Tests also cover batch recovery, record and byte boundaries, saved reports, forecast constraints, and overwrite protection. CI runs on Python 3.10 and 3.12.

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
