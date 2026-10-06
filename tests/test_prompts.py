from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from core.errors import PromptError
from core.prompts import PromptLoader, PromptRenderer
from tests.helpers import ROOT


class PromptTests(unittest.TestCase):
    def test_utf8_template_loading_with_unicode_path(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory) / 'tiếng Việt'
            folder.mkdir()
            (folder / 'demo.md').write_text('Xin chào ${name} 🎵', encoding='utf-8')
            template = PromptLoader(folder).load('demo.md')
            self.assertEqual(PromptRenderer().render(template, {'name': 'Việt'}), 'Xin chào Việt 🎵')

    def test_missing_template_has_clear_error(self):
        with self.assertRaisesRegex(PromptError, 'not found: missing.md'):
            PromptLoader(ROOT / 'prompts').load('missing.md')

    def test_reject_empty_and_non_utf8_templates(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'demo.md'
            for raw, message in ((b'  \n', 'empty'), (b'\xff\xfe', 'UTF-8')):
                path.write_bytes(raw)
                with self.subTest(raw=raw), self.assertRaisesRegex(PromptError, message):
                    PromptLoader(directory).load('demo.md')

    def test_reject_directory_traversal_and_absolute_paths(self):
        loader = PromptLoader(ROOT / 'prompts')
        for name in ('../README.md', str(ROOT / 'app.py'), ''):
            with self.subTest(name=name), self.assertRaises(PromptError):
                loader.load(name)

    def test_render_multiple_placeholders_and_literal_braces(self):
        rendered = PromptRenderer().render('${a} / $b / {artist} / $$', {'a': 'âm nhạc', 'b': 'Việt'})
        self.assertEqual(rendered, 'âm nhạc / Việt / {artist} / $')

    def test_missing_variables_report_names(self):
        with self.assertRaisesRegex(PromptError, 'Missing prompt variables: a, b'):
            PromptRenderer().render('${b} ${a}', {})

    def test_invalid_syntax_and_nonstring_variable(self):
        for template, variables in (('${unclosed', {}), ('${1bad}', {}), ('$', {}), ('${a}', {'a': 1}), ('', {})):
            with self.subTest(template=template), self.assertRaises(PromptError):
                PromptRenderer().render(template, variables)

    def test_render_is_single_pass_and_preserves_unicode_json(self):
        value = '{"description": "${not_a_variable} — Việt 🎵"}'
        self.assertEqual(PromptRenderer().render('${data}', {'data': value}), value)

    def test_all_production_prompts_render(self):
        loader = PromptLoader(ROOT / 'prompts')
        for name, variables in (
            ('analyze_competitor.md', {'competitor_json': '{}'}),
            ('generate_names.md', {'analysis_json': '{}'}),
            ('generate_package.md', {'analysis_json': '{}', 'selected_name_json': '"Tên kênh"'}),
        ):
            with self.subTest(name=name):
                rendered = PromptRenderer().render(loader.load(name), variables)
                self.assertTrue(rendered.startswith('# Task:'))
                self.assertNotIn('${', rendered)
