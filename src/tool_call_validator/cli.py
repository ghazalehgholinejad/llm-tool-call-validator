import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .batch import validate_batch
from .report import render_html
from .core import MAX_BYTES, _failure, validate_call


def main():
    parser = argparse.ArgumentParser(description="Validate LLM tool calls (never execute them)")
    parser.add_argument("call", type=Path)
    parser.add_argument("--schemas", type=Path, required=True, help="Trusted tool-name to JSON Schema mapping")
    parser.add_argument("--batch", action="store_true", help="Read JSONL: one call per physical line, at most 1000")
    parser.add_argument("--output", type=Path, help="Save report to a new file (refuses overwrite)")
    parser.add_argument("--format", choices=["json", "html"], default="json", help="Saved report format; stdout stays JSON")
    args = parser.parse_args()
    if args.format == "html" and args.output is None:
        parser.error("--format html requires --output")
    try:
        schemas = json.loads(args.schemas.read_text(encoding="utf-8"))
        if not isinstance(schemas, dict):
            raise ValueError("Schema registry must be an object")
        for schema in schemas.values():
            Draft202012Validator.check_schema(schema)
        with args.call.open("rb") as stream:
            if args.batch:
                result = validate_batch(stream, schemas)
            else:
                data = stream.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    result = _failure("size_limit", "Call exceeds 65536 UTF-8 bytes")
                else:
                    try:
                        result = validate_call(data.decode("utf-8"), schemas)
                    except UnicodeDecodeError:
                        result = _failure("invalid_encoding", "Call must be UTF-8")
        report = json.dumps(result, ensure_ascii=True, indent=2) + "\n"
        saved_report = render_html(result) if args.format == "html" else report
        if args.output:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(saved_report)
    except Exception as exc:
        # Configuration and I/O errors are distinct from rejected model output.
        print(json.dumps({"error": "configuration_or_io", "message": str(exc)}, ensure_ascii=True))
        return 2
    print(report, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
