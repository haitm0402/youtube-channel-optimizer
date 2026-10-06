import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from config import Settings
from core.ai_services import CompetitorAnalysisService, ChannelNameService, ChannelPackageService
from core.contracts import TextGenerator
from core.errors import (MalformedResponseError, PromptError, ProviderError, ResponseValidationError)
from core.prompts import PromptLoader
from core.responses import parse_response
from models import ChannelNameResult, ChannelPackage, ChannelProfile, CompetitorAnalysis, CompetitorInput
from services.mock import MockTextGenerator
from services.providers import create_text_generator
from tests.helpers import ROOT, fixture
from utils.json_io import read_profile, write_profile


class StubGenerator:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, *, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class ResponseTests(unittest.TestCase):
    def test_malformed_json_has_application_error(self):
        for text in ('not json', '', '{', '```json\n{}\n```', '{} trailing',
                     '{"x": 1, "x": 2}', '{"score": NaN}', '{"score": Infinity}', None):
            with self.subTest(text=text), self.assertRaises(MalformedResponseError):
                parse_response(text, CompetitorAnalysis.from_ai_dict)

    def test_valid_json_with_invalid_schema_is_validation_error(self):
        for data in ({}, [], None, 'prose', {'summary': 'incomplete'}):
            with self.subTest(data=data), self.assertRaises(ResponseValidationError):
                parse_response(json.dumps(data), CompetitorAnalysis.from_ai_dict)

    def test_invalid_fields_are_not_repaired(self):
        data = fixture('analysis')
        del data['genre']
        with self.assertRaisesRegex(ResponseValidationError, 'missing fields: genre'):
            parse_response(json.dumps(data), CompetitorAnalysis.from_ai_dict)
        self.assertNotIn('genre', data)

    def test_valid_json_returns_typed_models(self):
        for filename, model in (('analysis', CompetitorAnalysis), ('names', ChannelNameResult), ('package', ChannelPackage)):
            with self.subTest(filename=filename):
                self.assertIsInstance(parse_response(json.dumps(fixture(filename)), model.from_ai_dict), model)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.loader = PromptLoader(ROOT / 'prompts')
        self.competitor = CompetitorInput('https://youtube.com/@music', 'avatar.png', 'Nhạc Việt ${untouched}')
        self.analysis = CompetitorAnalysis.from_ai_dict(fixture('analysis'))
        self.names = ChannelNameResult.from_ai_dict(fixture('names'))

    def test_protocol_accepts_mock_and_independent_provider(self):
        stub = StubGenerator(json.dumps(fixture('analysis')))
        self.assertIsInstance(stub, TextGenerator)
        self.assertIsInstance(MockTextGenerator(), TextGenerator)
        result = CompetitorAnalysisService(stub, self.loader).analyze(self.competitor)
        self.assertEqual(result.genre, 'Pop')
        self.assertEqual(len(stub.prompts), 1)
        self.assertIn('Nhạc Việt ${untouched}', stub.prompts[0])
        self.assertIn('"avatar_reference": "avatar.png"', stub.prompts[0])

    def test_services_use_matching_prompts_and_factories(self):
        stub = StubGenerator(json.dumps(fixture('names')))
        result = ChannelNameService(stub, self.loader).generate(self.analysis)
        self.assertEqual(len(result.names), 12)
        self.assertTrue(stub.prompts[-1].startswith('# Task: generate_names\n'))
        stub.response = json.dumps(fixture('package'))
        package = ChannelPackageService(stub, self.loader).generate(self.analysis, result, result.names[0].name)
        self.assertIsInstance(package.banner, type(ChannelPackage.from_ai_dict(fixture('package')).banner))
        self.assertIn('Selected name JSON: "Acoustic Việt Mỗi Tối"', stub.prompts[-1])

    def test_services_propagate_malformed_and_schema_errors(self):
        for method, valid_data in (
            (lambda g: CompetitorAnalysisService(g, self.loader).analyze(self.competitor), fixture('analysis')),
            (lambda g: ChannelNameService(g, self.loader).generate(self.analysis), fixture('names')),
            (lambda g: ChannelPackageService(g, self.loader).generate(self.analysis, self.names, self.names.best_recommendation), fixture('package')),
        ):
            with self.assertRaises(MalformedResponseError):
                method(StubGenerator('bad json'))
            with self.assertRaises(ResponseValidationError):
                method(StubGenerator('{}'))
            valid_data['unexpected'] = 'value'
            with self.assertRaises(ResponseValidationError):
                method(StubGenerator(json.dumps(valid_data)))

    def test_prompt_failure_does_not_call_provider(self):
        with TemporaryDirectory() as directory:
            stub = StubGenerator('{}')
            with self.assertRaises(PromptError):
                CompetitorAnalysisService(stub, PromptLoader(directory)).analyze(self.competitor)
            self.assertEqual(stub.prompts, [])

    def test_provider_failure_is_clear_without_exposing_details(self):
        class BrokenProvider:
            def generate(self, *, prompt):
                raise RuntimeError('sensitive SDK detail')
        with self.assertRaisesRegex(ProviderError, 'Text provider failed') as context:
            CompetitorAnalysisService(BrokenProvider(), self.loader).analyze(self.competitor)
        self.assertNotIn('sensitive', str(context.exception))

    def test_package_rejects_name_outside_suggestions_before_provider_call(self):
        stub = StubGenerator('{}')
        with self.assertRaisesRegex(ValueError, 'selected_name'):
            ChannelPackageService(stub, self.loader).generate(self.analysis, self.names, 'unknown name')
        self.assertEqual(stub.prompts, [])

    def test_legacy_incomplete_analysis_cannot_bypass_ai_schema(self):
        with self.assertRaisesRegex(ValueError, 'genre'):
            ChannelNameService(MockTextGenerator(), self.loader).generate(CompetitorAnalysis('s', 'p', 'a'))

    def test_mutated_name_collection_is_revalidated(self):
        self.names.names.pop()
        with self.assertRaisesRegex(ValueError, 'exactly 12'):
            ChannelPackageService(MockTextGenerator(), self.loader).generate(self.analysis, self.names, 'Mây Âm Nhạc')

    def test_provider_factory_and_unimplemented_providers(self):
        self.assertIsInstance(create_text_generator(Settings(ai_provider='mock')), MockTextGenerator)
        for provider in ('unconfigured', 'openai', 'alternative'):
            with self.subTest(provider=provider), self.assertRaisesRegex(ProviderError, 'no implemented adapter'):
                create_text_generator(Settings(ai_provider=provider))


class MockPipelineTests(unittest.TestCase):
    def test_full_pipeline_offline_and_profile_round_trip(self):
        with patch.dict('os.environ', {}, clear=True), patch('socket.create_connection', side_effect=AssertionError('Network forbidden')), patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden')):
            generator = MockTextGenerator()
            loader = PromptLoader(ROOT / 'prompts')
            competitor = CompetitorInput('https://youtube.com/@music', 'ảnh.png', 'Nhạc Việt')
            analysis = CompetitorAnalysisService(generator, loader).analyze(competitor)
            names = ChannelNameService(generator, loader).generate(analysis)
            selected_name = names.names[2].name  # User choice need not equal best recommendation.
            package = ChannelPackageService(generator, loader).generate(analysis, names, selected_name)
            self.assertIn(selected_name, package.channel_description)
            profile = ChannelProfile(competitor, analysis, selected_name, package)
            with TemporaryDirectory() as directory:
                path = Path(directory) / 'kênh' / 'channel_profile.json'
                write_profile(profile, path)
                restored = read_profile(path)
                self.assertEqual(restored, profile)
                self.assertEqual(restored.package.banner.layout, package.banner.layout)
                self.assertEqual(restored.package.slogan, package.slogan)

    def test_mock_is_deterministic_and_unknown_tasks_fail(self):
        generator = MockTextGenerator()
        prompt = '# Task: analyze_competitor\nDescription mentions # Task: generate_package'
        self.assertEqual(generator.generate(prompt=prompt), generator.generate(prompt=prompt))
        self.assertIn('summary', json.loads(generator.generate(prompt=prompt)))
        for prompt in ('', 'unknown', '# Task: generate_package\nSelected name JSON: null'):
            with self.subTest(prompt=prompt), self.assertRaises(ProviderError):
                generator.generate(prompt=prompt)

    def test_cli_demo_requires_selection_and_exports_utf8(self):
        with TemporaryDirectory() as directory:
            config = Path(directory) / 'config.toml'
            # json.dumps also produces valid TOML double-quoted strings on Windows.
            config.write_text('prompts_dir = ' + json.dumps(str(ROOT / 'prompts')) + '\n'
                              'exports_dir = "exports"\n', encoding='utf-8')
            command = [sys.executable, str(ROOT / 'app.py'), '--config', str(config), '--mock-demo']
            result = subprocess.run(command, cwd=directory, capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Choose a suggested name', result.stdout)
            destination = Path(directory) / 'exports' / 'channel_profile.json'
            self.assertFalse(destination.exists())
            result = subprocess.run(command + ['--select-name', 'Mây Âm Nhạc'], cwd=directory,
                                    capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(read_profile(destination).selected_name, 'Mây Âm Nhạc')
            result = subprocess.run(command + ['--select-name', 'unknown'], cwd=directory,
                                    capture_output=True, encoding='utf-8')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('selected_name', result.stderr)
