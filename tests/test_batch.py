import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema.exceptions import SchemaError
from tool_call_validator import validate_batch
from tool_call_validator.core import MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = json.loads((ROOT / 'examples/tools.json').read_text())
GOOD = b'{"name":"search_documents","arguments":{"query":"RAG","top_k":3}}'


class BatchTests(unittest.TestCase):
    def test_mixed_fixture(self):
        with (ROOT / 'examples/mixed_calls.jsonl').open('rb') as stream:
            report = validate_batch(stream, SCHEMAS)
        self.assertEqual(report['summary']['total'], 7)
        self.assertEqual(report['summary']['accepted'], 2)
        self.assertEqual(report['summary']['rejected'], 5)
        self.assertEqual(report['summary']['records_by_error_code']['schema_type'], 2)
        self.assertFalse(report['valid'])
        self.assertEqual([r['line'] for r in report['results']], list(range(1, 8)))

    def test_bad_lines_do_not_stop_batch(self):
        report = validate_batch(io.BytesIO(b'not json\n\xff\n\n'+GOOD), SCHEMAS)
        self.assertEqual(report['summary']['accepted'], 1)
        self.assertEqual([r['errors'][0]['code'] for r in report['results'][:3]],
                         ['invalid_json', 'invalid_encoding', 'invalid_json'])

    def test_oversized_line_is_one_record(self):
        for ending in [b'\n', b'\r\n']:
            for size in [MAX_BYTES+1, MAX_BYTES+3, MAX_BYTES*3]:
                with self.subTest(size=size, ending=ending):
                    report = validate_batch(io.BytesIO(b'x'*size+ending+GOOD), SCHEMAS)
                    self.assertEqual(report['summary']['total'], 2)
                    self.assertEqual(report['results'][0]['errors'][0]['code'], 'size_limit')
                    self.assertTrue(report['results'][1]['valid'])

    def test_boundary_payload_and_line_endings(self):
        for ending in [b'', b'\n', b'\r\n']:
            report = validate_batch(io.BytesIO(GOOD+b' '*(MAX_BYTES-len(GOOD))+ending), SCHEMAS)
            self.assertTrue(report['valid'])
            self.assertEqual(report['summary']['total'], 1)

    def test_empty_input(self):
        with self.assertRaisesRegex(ValueError, 'empty'):
            validate_batch(io.BytesIO(), SCHEMAS)

    def test_record_limit(self):
        with patch('tool_call_validator.batch.MAX_CALLS', 2):
            self.assertTrue(validate_batch(io.BytesIO((GOOD+b'\n')*2), SCHEMAS)['valid'])
            with self.assertRaisesRegex(ValueError, 'exceeds 2'):
                validate_batch(io.BytesIO((GOOD+b'\n')*3), SCHEMAS)

    def test_error_counts_are_per_record(self):
        schemas = {'x': {'properties': {'a': {'type':'integer'}, 'b': {'type':'integer'}}}}
        raw = b'{"name":"x","arguments":{"a":"x","b":"x"}}'
        report = validate_batch(io.BytesIO(raw), schemas)
        self.assertEqual(report['summary']['records_by_error_code'], {'schema_type':1})
        self.assertEqual(len(report['results'][0]['errors']), 2)

    def test_unused_bad_schema_is_configuration_error(self):
        with self.assertRaises(SchemaError):
            validate_batch(io.BytesIO(GOOD), {**SCHEMAS, 'broken': {'type':'typo'}})

    def test_cli_report_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'report.json'
            command = [sys.executable, '-m', 'tool_call_validator.cli',
                       str(ROOT/'examples/mixed_calls.jsonl'), '--schemas', str(ROOT/'examples/tools.json'),
                       '--batch', '--output', str(output)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertEqual(json.loads(run.stdout), json.loads(output.read_text()))
            original = output.read_bytes()
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(output.read_bytes(), original)

    def test_cli_accepted_and_configuration_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp)/'calls.jsonl'
            output = Path(tmp)/'report.json'
            command = [sys.executable, '-m', 'tool_call_validator.cli', str(input_path),
                       '--schemas', str(ROOT/'examples/tools.json'), '--batch', '--output', str(output)]
            input_path.write_bytes(b'')
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(output.exists())
            input_path.write_bytes(GOOD)
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(json.loads(output.read_text())['valid'])

    def test_single_invalid_encoding_is_rejected_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bad.json'
            path.write_bytes(b'\xff')
            run = subprocess.run([sys.executable, '-m', 'tool_call_validator.cli', str(path),
                                  '--schemas', str(ROOT/'examples/tools.json')], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(json.loads(run.stdout)['errors'][0]['code'], 'invalid_encoding')

    def test_forecast_constraints(self):
        for horizon, expected in [(1, True),(168, True),(169, False),(0, False),(True, False),('24', False)]:
            with self.subTest(horizon=horizon):
                raw = json.dumps({'name':'forecast_energy','arguments':{'site_id':'site-001','horizon_hours':horizon}}).encode()
                self.assertEqual(validate_batch(io.BytesIO(raw), SCHEMAS)['valid'], expected)
