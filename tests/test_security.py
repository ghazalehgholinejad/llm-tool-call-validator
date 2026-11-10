import json
import subprocess
import sys
import unittest
from tool_call_validator.security import check_call, validate_policy, load_json

SCHEMAS = {'forecast': {'type':'object', 'properties': {'site': {'type':'string'}, 'hours': {'type':'integer'}}, 'additionalProperties':False}}
POLICY = {'tools': {'forecast': {'allowed_values': {'site':['site-001']}, 'max_values': {'hours':24}}}}

class SecurityTests(unittest.TestCase):
    def check(self, **args):
        return check_call(json.dumps({'name':'forecast','arguments':args}), SCHEMAS, POLICY)

    def test_allowed(self):
        self.assertTrue(self.check(site='site-001', hours=24)['allowed'])

    def test_cross_resource_denied(self):
        r = self.check(site='site-002', hours=1)
        self.assertTrue(r['schema_valid'])
        self.assertEqual(r['reason_codes'], ['argument_not_allowed'])

    def test_case_sensitive_no_coercion(self):
        self.assertFalse(self.check(site='SITE-001', hours=1)['allowed'])
        self.assertFalse(self.check(site='site-001', hours='1')['allowed'])

    def test_missing_optional_schema_fields_denied(self):
        self.assertFalse(self.check()['allowed'])

    def test_limits_and_boolean(self):
        for value in (-1, 25, True):
            self.assertFalse(self.check(site='site-001', hours=value)['allowed'])

    def test_model_cannot_add_permissions(self):
        self.assertFalse(self.check(site='site-002', hours=1, approved=True)['allowed'])

    def test_registered_but_ungranted(self):
        r = check_call('{"name":"forecast","arguments":{}}', SCHEMAS, {'tools':{}})
        self.assertEqual(r['reason_codes'], ['tool_denied'])

    def test_rejected_reports_omit_values(self):
        for args in ({'site':'SECRET', 'hours':1}, {'site':'SECRET','extra':'PRIVATE'}):
            serialized = json.dumps(self.check(**args))
            self.assertNotIn('SECRET', serialized)
            self.assertNotIn('PRIVATE', serialized)

    def test_policy_typos_fail_closed(self):
        for policy in ({}, {'tools':[],}, {'tools':{'x':{'allowed_values':{}, 'max_values':{}, 'allow':True}}}, {'tools':{'x':{'allowed_values':{},'max_values':{'x':True}}}}):
            with self.assertRaises(ValueError): validate_policy(policy)

    def test_duplicate_policy_keys_rejected(self):
        with self.assertRaises(ValueError): load_json('{"tools":{},"tools":{}}')

    def test_cli(self):
        command = [sys.executable, '-m', 'tool_call_validator.security', 'examples/valid_persian.json', '--schemas', 'examples/tools.json', '--policy', 'examples/security_policy.json']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('allowed', json.loads(result.stdout))
