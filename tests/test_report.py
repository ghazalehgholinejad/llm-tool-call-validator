import json
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from tool_call_validator.report import render_html
from tool_call_validator import validate_batch

ROOT = Path(__file__).resolve().parents[1]

class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

class ReportTests(unittest.TestCase):
    def test_batch_structure(self):
        schemas = json.loads((ROOT/'examples/tools.json').read_text())
        with (ROOT/'examples/mixed_calls.jsonl').open('rb') as stream:
            page = render_html(validate_batch(stream, schemas))
        tags = Tags(page).tags
        statuses = [attrs['data-status'] for tag, attrs in tags if tag == 'article']
        self.assertEqual(statuses.count('accepted'), 2)
        self.assertEqual(statuses.count('rejected'), 5)
        self.assertIn('Line 7', page)
        self.assertIn('schema_minimum', page)

    def test_untrusted_values_cannot_create_elements(self):
        payload = '</script><img src=x onerror=alert(1)><script>alert(2)</script>'
        result = {'valid':False, 'errors':[{'code':payload,'path':payload,'message':payload}], 'errors_truncated':True}
        page = render_html(result)
        tags = Tags(page).tags
        self.assertEqual(sum(tag == 'script' for tag, _ in tags), 1)
        self.assertFalse(any(tag == 'img' for tag, _ in tags))
        self.assertNotIn(payload, page)
        self.assertIn('More errors were omitted', page)

    def test_accepted_arguments_and_tool_name_escaped(self):
        page = render_html({'valid':True, 'errors':[], 'call':{'name':'<img src=x>', 'arguments':{'x':'</pre><img src=x>', 'unicode':'\ud800'}}})
        page.encode('utf-8')
        self.assertFalse(any(tag == 'img' for tag, _ in Tags(page).tags))
        self.assertIn('&lt;img', page)

    def test_cli_html_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'report.html'
            command = [sys.executable, '-m', 'tool_call_validator.cli', str(ROOT/'examples/mixed_calls.jsonl'), '--schemas', str(ROOT/'examples/tools.json'), '--batch', '--format', 'html', '--output', str(output)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertEqual(json.loads(run.stdout)['summary']['total'], 7)
            original = output.read_bytes()
            self.assertTrue(original.startswith(b'<!doctype html>'))
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(output.read_bytes(), original)

    def test_html_requires_output(self):
        run = subprocess.run([sys.executable, '-m', 'tool_call_validator.cli', 'missing', '--schemas', 'missing', '--format', 'html'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn('--format html requires --output', run.stderr)

    def test_single_accepted_cli_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'one.html'
            run = subprocess.run([sys.executable, '-m', 'tool_call_validator.cli', str(ROOT/'examples/valid_search.json'), '--schemas', str(ROOT/'examples/tools.json'), '--format', 'html', '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('search_documents', output.read_text())
