from dataclasses import asdict
import unittest
from models import (ChannelPackageV1, CompetitorInput, TargetAudience, WorkflowSession, WorkflowState)
from tests.helpers import example
import json


class ManualInputTests(unittest.TestCase):
    def test_primary_input_without_avatar(self):
        value = CompetitorInput.from_v1_dict(example('competitor_input'))
        self.assertIsNone(value.avatar_reference)
        self.assertEqual(value.competitor_url, 'https://www.youtube.com/@example-music')
        self.assertEqual(value.target_market, 'Việt Nam')
        self.assertEqual(value.target_language, 'Tiếng Việt')
        self.assertNotIn('avatar_reference', value.to_prompt_dict())
        self.assertEqual(value.target, TargetAudience(market='Việt Nam', language='Tiếng Việt'))

    def test_legacy_positional_input_and_json_shape(self):
        value = CompetitorInput('https://youtube.com/@x', 'ảnh.png', 'Nhạc Việt', TargetAudience(artist='A'))
        self.assertEqual(value.url, value.competitor_url)
        self.assertEqual(value.description, value.competitor_description)
        self.assertEqual(value.avatar_reference, 'ảnh.png')
        self.assertEqual(value.target_artist, 'A')
        legacy = asdict(value)
        legacy['target'] = TargetAudience(**legacy['target'])
        self.assertEqual(CompetitorInput(**legacy), value)

    def test_optional_target_fields_and_required_description(self):
        value = CompetitorInput(competitor_url='https://youtube.com/@x', competitor_description='Nhạc')
        self.assertIsNone(value.target_artist)
        for field in ('competitor_url', 'competitor_description', 'target_artist', 'target_market', 'target_language'):
            data = dict(competitor_url='https://youtube.com/@x', competitor_description='Nhạc')
            for invalid in (' ', 1, False):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    CompetitorInput(**{**data, field: invalid})
        for field in ('competitor_url', 'competitor_description'):
            del_data = dict(competitor_url='https://youtube.com/@x', competitor_description='Nhạc')
            del del_data[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                CompetitorInput.from_v1_dict(del_data)

    def test_alias_conflicts_are_rejected(self):
        for data in (
            {'url': 'https://youtube.com/@x', 'competitor_url': 'https://youtube.com/@y', 'description': 'Nhạc'},
            {'url': 'https://youtube.com/@x', 'description': 'Old', 'competitor_description': 'New'},
            {'url': 'https://youtube.com/@x', 'description': 'Nhạc', 'target': TargetAudience(artist='A'), 'target_artist': 'B'},
        ):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'conflict'):
                CompetitorInput(**data)

    def test_valid_channel_urls(self):
        for path in ('@music', '@âmnhạc/videos', 'channel/UC123', 'c/Music', 'user/Music/playlists'):
            with self.subTest(path=path):
                value = CompetitorInput(competitor_url='https://www.youtube.com/' + path, competitor_description='Music')
                self.assertTrue(value.url.endswith(path))

    def test_invalid_video_urls_ports_and_embedded_credentials(self):
        for url in ('https://youtube.com/watch?v=123', 'https://youtube.com/shorts/123', 'https://youtube.com/@',
                    'https://youtube.com:80/@music', 'https://youtube.com:wrong/@music',
                    'https://@youtube.com/@music', 'https://youtube.com/@music\n',
                    'https://evil.test/@music', 'http://youtube.com/@music'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                CompetitorInput(competitor_url=url, competitor_description='Music')

    def test_primary_input_rejects_unknown_fields(self):
        with self.assertRaisesRegex(ValueError, 'unknown fields'):
            CompetitorInput.from_v1_dict({**example('competitor_input'), 'avatar_reference': 'unused.png'})
        with self.assertRaises(ValueError):
            CompetitorInput.from_v1_dict([])


class TextPackageTests(unittest.TestCase):
    def test_text_only_schema_round_trip(self):
        data = example('package_v1_response')
        package = ChannelPackageV1.from_dict(data)
        self.assertEqual(package.to_dict(), data)
        self.assertNotIn('avatar_concepts', package.to_dict())
        self.assertNotIn('image_prompt', json.dumps(package.to_dict()))
        self.assertTrue(package.banner_direction)
        self.assertTrue(package.thumbnail_direction)

    def test_every_field_is_required(self):
        for field in example('package_v1_response'):
            data = example('package_v1_response')
            del data[field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'missing fields'):
                ChannelPackageV1.from_dict(data)

    def test_wrong_text_types_or_empty_values(self):
        for field in ('channel_positioning', 'channel_description', 'thumbnail_direction', 'banner_direction', 'slogan'):
            for invalid in (None, False, [], '', ' '):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    ChannelPackageV1.from_dict({**example('package_v1_response'), field: invalid})

    def test_wrong_list_types_or_empty_values(self):
        for field in ('channel_keywords', 'video_core_keywords', 'video_tags', 'hashtags', 'title_templates'):
            for invalid in (None, 'text', [], [''], [False]):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    ChannelPackageV1.from_dict({**example('package_v1_response'), field: invalid})

    def test_legacy_image_fields_are_rejected_in_active_schema(self):
        for field in ('avatar_concepts', 'banner', 'image_prompt', 'thumbnail_visual_guide'):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'unknown fields'):
                ChannelPackageV1.from_dict({**example('package_v1_response'), field: 'unexpected'})


class SessionModelTests(unittest.TestCase):
    def test_initial_session(self):
        session = WorkflowSession(CompetitorInput.from_v1_dict(example('competitor_input')))
        self.assertEqual(session.state, WorkflowState.INPUT)
        self.assertIsNone(session.pending_prompt)
        with self.assertRaisesRegex(ValueError, 'COMPLETE'):
            session.to_profile_dict()

    def test_reject_unknown_state_or_inconsistent_session(self):
        competitor = CompetitorInput.from_v1_dict(example('competitor_input'))
        for state in ('unknown', 'ANALYSIS_READY', 'NAMES_READY', 'NAME_SELECTED', 'COMPLETE'):
            with self.subTest(state=state), self.assertRaises(ValueError):
                WorkflowSession(competitor, state=state)
        with self.assertRaises(ValueError):
            WorkflowSession(competitor, pending_prompt='unexpected')
        with self.assertRaises(ValueError):
            WorkflowSession(competitor, state='WAITING_FOR_ANALYSIS', pending_prompt='')
