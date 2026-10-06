from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from config import Settings, load_settings
from tests.helpers import ROOT


class EnvironmentSettingsTests(unittest.TestCase):
    def test_environment_overrides_toml_provider_and_model(self):
        settings = load_settings(environ={'YCO_AI_PROVIDER': 'mock', 'YCO_AI_MODEL': 'future-model'})
        self.assertEqual(settings.ai_provider, 'mock')
        self.assertEqual(settings.ai_model, 'future-model')
        self.assertEqual(settings.prompts_dir, ROOT / 'prompts')

    def test_api_key_is_not_in_repr(self):
        settings = load_settings(environ={'YCO_AI_API_KEY': 'dummy-test-value'})
        self.assertEqual(settings.ai_api_key, 'dummy-test-value')
        self.assertNotIn('dummy-test-value', repr(settings))
        self.assertNotIn('ai_api_key', repr(settings))

    def test_empty_environment_values_fail(self):
        for variable in ('YCO_AI_PROVIDER', 'YCO_AI_MODEL', 'YCO_AI_API_KEY'):
            with self.subTest(variable=variable), self.assertRaises(ValueError):
                load_settings(environ={variable: ''})

    def test_no_key_needed_for_mock_and_no_dotenv_loading(self):
        settings = load_settings(environ={'YCO_AI_PROVIDER': 'mock'})
        self.assertIsNone(settings.ai_api_key)
        self.assertEqual(load_settings(environ={}).ai_provider, 'unconfigured')

    def test_secrets_not_accepted_from_toml(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('ai_api_key = "dummy-test-value"', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unknown settings: ai_api_key'):
                load_settings(path, environ={})

    def test_phase1_positional_settings_remain_compatible(self):
        settings = Settings('Project', 'mock', None, ROOT / 'prompts', ROOT / 'exports')
        self.assertEqual(settings.prompts_dir, ROOT / 'prompts')
        self.assertEqual(settings.exports_dir, ROOT / 'exports')
        self.assertIsNone(settings.ai_api_key)
