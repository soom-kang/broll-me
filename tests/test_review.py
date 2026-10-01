"""HTML output must remain inert JSON inside the supplied review viewer."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/create_review.py'
spec=importlib.util.spec_from_file_location('create_review',SCRIPT)
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)


class ReviewTests(unittest.TestCase):
    def test_html_source_roundtrips_without_closing_script(self):
        data={'output':'<script>let title="hello";</script><img src=x onerror=alert(1)> &'}
        page='<script>const EMBEDDED_DATA = '+json.dumps(data)+';\nconsole.log(EMBEDDED_DATA);</script>'
        protected=review.protect_embedded_json(page)
        self.assertEqual(protected.count('</script>'),1)
        self.assertEqual(json.loads(re.search(r'const EMBEDDED_DATA = (.+?);\n',protected)[1]),data)

    def test_unknown_viewer_format_fails(self):
        with self.assertRaisesRegex(ValueError,'marker not found'):
            review.protect_embedded_json('Changed viewer template')
