import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tool_call_validator import validate_call

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = json.loads((ROOT / 'examples/tools.json').read_text())

class ValidationTests(unittest.TestCase):
    def test_all_fixture_expectations(self):
        for case in json.loads((ROOT / 'examples/cases.json').read_text()):
            with self.subTest(case=case['file']):
                result = validate_call((ROOT / 'examples' / case['file']).read_text(), SCHEMAS)
                self.assertEqual(result['valid'], case['expected_valid'])

    def test_duplicate_nested_key(self):
        result = validate_call('{"name":"search_documents","arguments":{"query":"x","query":"y","top_k":2}}', SCHEMAS)
        self.assertEqual(result['errors'][0]['code'], 'invalid_json')

    def test_nonfinite(self):
        for number in ['NaN', 'Infinity', '-Infinity', '1e999']:
            with self.subTest(number=number):
                self.assertEqual(validate_call('{"x":'+number+'}', SCHEMAS)['errors'][0]['code'], 'invalid_json')

    def test_envelopes(self):
        for call in [[], None, {}, {'name':[], 'arguments':{}}, {'name':'search_documents','arguments':'{}'}, {'name':'search_documents','arguments':{},'extra':1}]:
            self.assertEqual(validate_call(json.dumps(call), SCHEMAS)['errors'][0]['code'], 'invalid_envelope')

    def test_no_markdown_repair(self):
        self.assertEqual(validate_call('```json\n{}\n```',SCHEMAS)['errors'][0]['code'], 'invalid_json')

    def test_byte_limit(self):
        self.assertEqual(validate_call('ی'*40000, SCHEMAS)['errors'][0]['code'], 'size_limit')

    def test_deep_json(self):
        self.assertFalse(validate_call('['*2000+']'*2000, SCHEMAS)['valid'])

    def test_pointer_escaping(self):
        schema={'test':{'type':'object','properties':{'a/b~c':{'type':'integer'}}}}
        result=validate_call('{"name":"test","arguments":{"a/b~c":"wrong"}}',schema)
        self.assertEqual(result['errors'][0]['path'],'/arguments/a~1b~0c')

    def test_error_cap(self):
        result=validate_call(json.dumps({'name':'test','arguments':{str(i):'x' for i in range(30)}}),{'test':{'additionalProperties':{'type':'integer'}}})
        self.assertEqual(len(result['errors']),20)
        self.assertTrue(result['errors_truncated'])

    def test_config_failure_is_not_model_failure(self):
        with self.assertRaises(Exception):
            validate_call('{"name":"bad","arguments":{}}',{'bad':{'type':'typo'}})

    def test_remote_reference_never_fetches(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('network requested')) as fetch:
            with self.assertRaises(Exception):
                validate_call('{"name":"test","arguments":{}}',{'test':{'$ref':'https://example.com/schema.json'}})
            fetch.assert_not_called()

    def test_local_reference(self):
        schema={'test':{'$defs':{'args':{'type':'object'}},'$ref':'#/$defs/args'}}
        self.assertTrue(validate_call('{"name":"test","arguments":{}}',schema)['valid'])

    def test_cli_exit_codes(self):
        for file,code in [('valid_search.json',0),('unknown_tool.json',1),('missing.json',2)]:
            with self.subTest(file=file):
                run=subprocess.run([sys.executable,'-m','tool_call_validator.cli',str(ROOT/'examples'/file),'--schemas',str(ROOT/'examples/tools.json')],capture_output=True,text=True)
                self.assertEqual(run.returncode,code,run.stderr)
                json.loads(run.stdout)

    def test_oversized_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'big.json'
            path.write_bytes(b' '*70000)
            run=subprocess.run([sys.executable,'-m','tool_call_validator.cli',str(path),'--schemas',str(ROOT/'examples/tools.json')],capture_output=True,text=True)
            self.assertEqual(run.returncode,1)
            self.assertEqual(json.loads(run.stdout)['errors'][0]['code'],'size_limit')

if __name__=='__main__':
    unittest.main()
