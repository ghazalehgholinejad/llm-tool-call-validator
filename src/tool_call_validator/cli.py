import argparse
import json
from pathlib import Path

from .core import MAX_BYTES, validate_call


def main():
    parser = argparse.ArgumentParser(description="Validate one normalized LLM tool call (never execute it)")
    parser.add_argument("call", type=Path)
    parser.add_argument("--schemas", type=Path, required=True, help="Trusted tool-name to JSON Schema mapping")
    args = parser.parse_args()
    try:
        schemas = json.loads(args.schemas.read_text(encoding="utf-8"))
        if not isinstance(schemas, dict):
            raise ValueError("Schema registry must be an object")
        with args.call.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            result = {"valid": False, "errors": [{"code": "size_limit", "path": "", "message": "Call exceeds 65536 UTF-8 bytes"}]}
        else:
            result = validate_call(data.decode("utf-8"), schemas)
    except Exception as exc:
        # CLI config/I/O errors are distinct from rejected model output.
        print(json.dumps({"error": "configuration_or_io", "message": str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
