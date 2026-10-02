"""Print a reproducible report for authored synthetic cases, not a model benchmark."""
import json
from pathlib import Path
from tool_call_validator import validate_call

HERE = Path(__file__).resolve().parent
schemas = json.loads((HERE / 'tools.json').read_text())
rows = []
for case in json.loads((HERE / 'cases.json').read_text()):
    result = validate_call((HERE / case['file']).read_text(encoding='utf-8'), schemas)
    rows.append({'case': case['file'], 'expected_valid': case['expected_valid'],
                 'actual_valid': result['valid'], 'codes': [e['code'] for e in result['errors']]})
print(json.dumps({'kind':'authored_synthetic_cases','results':rows},indent=2))
raise SystemExit(0 if all(r['expected_valid']==r['actual_valid'] for r in rows) else 1)
