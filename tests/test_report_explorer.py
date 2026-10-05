import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from html.parser import HTMLParser
from tool_call_validator.report import render_html

class Parser(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.tags=[]
        self.feed(page)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag,dict(attrs)))

class ExplorerTests(unittest.TestCase):
    def test_frequency_counts_records_and_sorts(self):
        error=lambda code: {'code':code,'path':'','message':'bad'}
        page=render_html({'results':[
            {'line':1,'valid':False,'errors':[error('z'),error('z'),error('a')]},
            {'line':2,'valid':False,'errors':[error('z')]}]})
        self.assertIn('<code>z</code></th><td>2</td>',page)
        self.assertIn('<code>a</code></th><td>1</td>',page)
        options=[attrs['value'] for tag,attrs in Parser(page).tags if tag=='option']
        self.assertEqual(options,['','z','a'])

    def test_hostile_code_is_safe_in_attributes_and_options(self):
        code='\"><img src=x onerror=alert(1)>'
        page=render_html({'valid':False,'errors':[{'code':code,'path':'','message':'bad'}]})
        tags=Parser(page).tags
        self.assertFalse(any(tag=='img' for tag,_ in tags))
        article=next(attrs for tag,attrs in tags if tag=='article')
        self.assertEqual(json.loads(article['data-errors']),[code])
        self.assertEqual(next(attrs['value'] for tag,attrs in tags if tag=='option' and attrs['value']),code)

    def test_no_error_report(self):
        page=render_html({'valid':True,'errors':[],'call':{'name':'test','arguments':{}}})
        self.assertIn('No validation errors.',page)
        self.assertEqual([attrs['value'] for tag,attrs in Parser(page).tags if tag=='option'],[''])

    @unittest.skipUnless(shutil.which('node'), 'Node.js required for report interaction test')
    def test_actual_filter_script(self):
        page=render_html({'valid':False,'errors':[]})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.html';path.write_text(page)
            run=subprocess.run(['node',str(Path(__file__).with_name('report_filters.cjs')),str(path)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
