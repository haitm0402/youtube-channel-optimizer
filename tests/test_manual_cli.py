import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from config import Settings
from models import CompetitorInput
from services.manual_cli import run_manual
from tests.helpers import ROOT, example


def pasted(name):
    return json.dumps(example(name), ensure_ascii=False) + '\nEND_JSON\n'


def successful_input():
    return pasted('analysis_response') + pasted('names_response') + 'Mây Âm Nhạc\n' + pasted('package_v1_response')


class ManualCLITests(unittest.TestCase):
    def command(self, directory):
        config = Path(directory) / 'settings.toml'
        config.write_text('prompts_dir = ' + json.dumps(str(ROOT / 'prompts')) + '\nexports_dir = "exports"\n', encoding='utf-8')
        return [sys.executable, str(ROOT / 'app.py'), '--manual', '--config', str(config),
                '--input-json', str(ROOT / 'examples' / 'competitor_input.json')]

    def run_cli(self, command, directory, text):
        environment = dict(os.environ)
        # Manual mode must not depend on legacy provider variables or an API key.
        for name in ('YCO_AI_PROVIDER', 'YCO_AI_MODEL', 'YCO_AI_API_KEY'):
            environment.pop(name, None)
        environment['PYTHONIOENCODING'] = 'utf-8'
        return subprocess.run(command, input=text, capture_output=True, encoding='utf-8',
                              cwd=directory, env=environment, timeout=20)

    def test_manual_cli_full_paste_workflow(self):
        with TemporaryDirectory() as directory:
            result = self.run_cli(self.command(directory), directory, successful_input())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('# Task: generate_package_v1', result.stdout)
            self.assertIn('Text channel package exported:', result.stdout)
            folder = Path(directory) / 'exports' / 'Mây Âm Nhạc'
            self.assertEqual(len(list(folder.iterdir())), 9)
            profile = json.loads((folder / 'channel_profile.json').read_text(encoding='utf-8'))
            self.assertEqual(profile['profile_type'], 'manual_text_v1')
            self.assertNotIn('avatar_reference', profile['competitor'])

    def test_manual_cli_retries_invalid_json_and_invalid_selection(self):
        text = 'bad json\nEND_JSON\n{}\nEND_JSON\n' + pasted('analysis_response') + pasted('names_response')
        text += 'Not suggested\nMây Âm Nhạc\n' + pasted('package_v1_response')
        with TemporaryDirectory() as directory:
            result = self.run_cli(self.command(directory), directory, text)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Response rejected:', result.stdout)
            self.assertIn('Selection rejected:', result.stdout)
            self.assertTrue((Path(directory) / 'exports' / 'Mây Âm Nhạc' / 'channel_profile.json').exists())

    def test_cancelled_manual_session_does_not_export(self):
        with TemporaryDirectory() as directory:
            result = self.run_cli(self.command(directory), directory, '')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('cancelled', result.stderr)
            self.assertFalse((Path(directory) / 'exports').exists())

    def test_input_file_rejects_invalid_json_or_missing_field(self):
        with TemporaryDirectory() as directory:
            command = self.command(directory)
            input_path = Path(directory) / 'input.json'
            command[-1] = str(input_path)
            for content in ('not JSON', '{}', '[]', '{"competitor_url": "https://youtube.com/@x"}'):
                input_path.write_text(content, encoding='utf-8')
                result = self.run_cli(command, directory, '')
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((Path(directory) / 'exports').exists())

    def test_cli_interactive_competitor_input_without_avatar(self):
        with TemporaryDirectory() as directory:
            command = self.command(directory)[:-2]
            text = 'https://youtube.com/@music\nNhạc Việt acoustic\n\nViệt Nam\nTiếng Việt\n' + successful_input()
            result = self.run_cli(command, directory, text)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Competitor description', result.stdout)
            self.assertNotIn('Competitor avatar:', result.stdout)

    def test_manual_cli_never_calls_a_provider(self):
        competitor = CompetitorInput.from_v1_dict(example('competitor_input'))
        lines = successful_input().splitlines()
        with TemporaryDirectory() as directory, patch('builtins.input', side_effect=lines), patch('builtins.print'), patch('services.providers.create_text_generator', side_effect=AssertionError('Provider forbidden')), patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            result = run_manual(Settings(exports_dir=Path(directory)), competitor=competitor)
            self.assertTrue((result / 'channel_profile.json').is_file())

    def test_incompatible_cli_modes_are_rejected(self):
        for args in (['--manual', '--mock-demo'], ['--manual', '--select-name', 'name'],
                     ['--input-json', 'unused.json']):
            with TemporaryDirectory() as directory:
                result = self.run_cli([sys.executable, str(ROOT / 'app.py'), *args], directory, '')
                self.assertNotEqual(result.returncode, 0)
