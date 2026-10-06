import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from config import Settings, load_settings
from config.settings import PROJECT_ROOT


class ConfigTests(unittest.TestCase):
    def test_default_settings_and_prompt_assets(self):
        settings = load_settings()
        self.assertEqual(settings.ai_provider, 'unconfigured')
        self.assertIsNone(settings.ai_model)
        self.assertEqual(settings.exports_dir, PROJECT_ROOT / 'exports')
        for name in ('analyze_competitor.md', 'generate_names.md', 'generate_package.md'):
            self.assertIn('# Task:', (settings.prompts_dir / name).read_text(encoding='utf-8'))

    def test_config_relative_paths_and_unicode(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.toml'
            path.write_text('project_name = "Kênh nhạc Việt"\nai_provider = "future-adapter"\n'
                            'ai_model = "model-a"\nprompts_dir = "tài nguyên/prompts"\n'
                            'exports_dir = "kết quả"\n', encoding='utf-8')
            settings = load_settings(path)
            self.assertEqual(settings.project_name, 'Kênh nhạc Việt')
            self.assertEqual(settings.prompts_dir, Path(directory) / 'tài nguyên' / 'prompts')
            self.assertEqual(settings.exports_dir, Path(directory) / 'kết quả')
            self.assertEqual(settings.ai_model, 'model-a')

    def test_defaults_independent_of_current_directory(self):
        original = Path.cwd()
        with TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(load_settings().prompts_dir, PROJECT_ROOT / 'prompts')
            finally:
                os.chdir(original)

    def test_invalid_config_fails_early(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.toml'
            for content in ('unknown = "x"', 'ai_provider = ""', 'exports_dir = 123',
                            'prompts_dir = ""', 'ai_model = 12'):
                path.write_text(content, encoding='utf-8')
                with self.subTest(content=content), self.assertRaises(ValueError):
                    load_settings(path)
            with self.assertRaises(FileNotFoundError):
                load_settings(Path(directory) / 'missing.toml')
        with self.assertRaises(ValueError):
            Settings(prompts_dir='not a Path')
