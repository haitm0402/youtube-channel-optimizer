import math
import unittest
from models import (AvatarConcept, BannerConcept, ChannelNameResult, ChannelPackage,
                    CompetitorAnalysis, NameCandidate, NameCategory)
from tests.helpers import fixture


class AnalysisSchemaTests(unittest.TestCase):
    def test_complete_analysis(self):
        data = fixture('analysis')
        analysis = CompetitorAnalysis.from_ai_dict(data)
        self.assertEqual(analysis.to_ai_dict(), data)
        self.assertEqual(analysis.target_audience, analysis.audience)
        self.assertIsNone(analysis.reference_artist)
        self.assertEqual(analysis.genre, 'Pop')

    def test_no_missing_or_extra_analysis_fields(self):
        for name in fixture('analysis'):
            data = fixture('analysis')
            del data[name]
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'missing fields'):
                CompetitorAnalysis.from_ai_dict(data)
        with self.assertRaisesRegex(ValueError, 'unknown fields'):
            CompetitorAnalysis.from_ai_dict({**fixture('analysis'), 'extra': 'x'})

    def test_invalid_analysis_types_and_values(self):
        for field, values in {
            'summary': ['', None, 1], 'genre': ['', []], 'reference_artist': ['', 12],
            'target_audience': [None, ' '], 'seo_topics': [[], 'text', [12]],
            'branding_characteristics': [[], [False]],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    CompetitorAnalysis.from_ai_dict({**fixture('analysis'), field: value})

    def test_legacy_audience_alias_and_conflict(self):
        self.assertEqual(CompetitorAnalysis('s', 'p', 'a').target_audience, 'a')
        with self.assertRaises(ValueError):
            CompetitorAnalysis('s', 'p', 'a', target_audience='different')


class NameSchemaTests(unittest.TestCase):
    def test_twelve_names_four_per_category_and_recommendation(self):
        result = ChannelNameResult.from_ai_dict(fixture('names'))
        self.assertEqual(len(result.names), 12)
        for category in NameCategory:
            self.assertEqual(sum(item.category == category for item in result.names), 4)
        self.assertIn(result.best_recommendation, [item.name for item in result.names])
        self.assertEqual(result.names[0].short_reason, result.names[0].rationale)

    def test_reject_wrong_total_count(self):
        for count in (0, 11, 13):
            data = fixture('names')
            data['names'] = (data['names'] + [data['names'][0]])[:count]
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'exactly 12'):
                ChannelNameResult.from_ai_dict(data)

    def test_reject_wrong_category_distribution(self):
        for category in ('positioning', 'brand', 'memorable'):
            data = fixture('names')
            index = next(i for i, item in enumerate(data['names']) if item['category'] == category)
            data['names'][index]['category'] = 'brand' if category != 'brand' else 'memorable'
            with self.subTest(category=category), self.assertRaisesRegex(ValueError, 'exactly 4'):
                ChannelNameResult.from_ai_dict(data)

    def test_reject_invalid_score(self):
        for score in (-1, 10.01, '9', True, None, math.nan, math.inf, -math.inf, 10**400):
            data = fixture('names')
            data['names'][0]['score'] = score
            with self.subTest(score=score), self.assertRaises(ValueError):
                ChannelNameResult.from_ai_dict(data)

    def test_score_boundaries(self):
        for score in (0, 10, 8.25):
            data = fixture('names')['names'][0]
            data['score'] = score
            self.assertEqual(NameCandidate.from_ai_dict(data).score, score)

    def test_invalid_category_recommendation_and_duplicate_names(self):
        data = fixture('names')
        data['names'][0]['category'] = 'other'
        with self.assertRaisesRegex(ValueError, 'category'):
            ChannelNameResult.from_ai_dict(data)
        data = fixture('names')
        data['best_recommendation'] = 'Not suggested'
        with self.assertRaisesRegex(ValueError, 'best_recommendation'):
            ChannelNameResult.from_ai_dict(data)
        data = fixture('names')
        data['names'][1]['name'] = f" {data['names'][0]['name'].upper()} "
        with self.assertRaisesRegex(ValueError, 'unique'):
            ChannelNameResult.from_ai_dict(data)

    def test_missing_name_fields_and_wrong_container(self):
        for field in ('name', 'category', 'short_reason', 'score'):
            data = fixture('names')
            del data['names'][0][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                ChannelNameResult.from_ai_dict(data)
        with self.assertRaises(ValueError):
            ChannelNameResult.from_ai_dict({'names': {}, 'best_recommendation': 'x'})


class PackageSchemaTests(unittest.TestCase):
    def test_complete_nested_package(self):
        data = fixture('package')
        package = ChannelPackage.from_ai_dict(data)
        self.assertEqual(package.to_ai_dict(), data)
        self.assertEqual(len(package.avatar_concepts), 4)
        self.assertIsInstance(package.avatar_concepts[0], AvatarConcept)
        self.assertIsInstance(package.banner, BannerConcept)
        self.assertEqual(package.channel_positioning, package.positioning)
        self.assertEqual(package.channel_description, package.description)
        self.assertEqual(package.avatar_concepts[0].image_prompt, package.avatar_concepts[0].prompt)

    def test_exactly_four_avatars(self):
        for count in (0, 3, 5):
            data = fixture('package')
            data['avatar_concepts'] = (data['avatar_concepts'] + [data['avatar_concepts'][0]])[:count]
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'exactly four'):
                ChannelPackage.from_ai_dict(data)

    def test_missing_avatar_fields_and_colors(self):
        for field in fixture('package')['avatar_concepts'][0]:
            data = fixture('package')
            del data['avatar_concepts'][0][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                ChannelPackage.from_ai_dict(data)
        for value in ([], 'red', [123]):
            data = fixture('package')
            data['avatar_concepts'][0]['colors'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                ChannelPackage.from_ai_dict(data)

    def test_banner_requires_all_fields(self):
        for field in fixture('package')['banner']:
            for invalid in ('missing', 'empty', 'wrong-type'):
                data = fixture('package')
                if invalid == 'missing':
                    del data['banner'][field]
                else:
                    data['banner'][field] = '' if invalid == 'empty' else 12
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    ChannelPackage.from_ai_dict(data)
        with self.assertRaises(ValueError):
            ChannelPackage.from_ai_dict({**fixture('package'), 'banner': None})

    def test_seo_lists_slogan_and_thumbnail_are_required(self):
        for field in ('channel_keywords', 'video_core_keywords', 'video_tags', 'hashtags', 'title_templates'):
            for value in ([], '', [False]):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    ChannelPackage.from_ai_dict({**fixture('package'), field: value})
        for field in ('slogan', 'thumbnail_visual_guide', 'channel_description', 'channel_positioning'):
            for value in ('', None, []):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    ChannelPackage.from_ai_dict({**fixture('package'), field: value})

    def test_missing_and_unknown_package_fields(self):
        for field in fixture('package'):
            data = fixture('package')
            del data[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                ChannelPackage.from_ai_dict(data)
        with self.assertRaises(ValueError):
            ChannelPackage.from_ai_dict({**fixture('package'), 'extra': 'x'})

    def test_avatar_alias_conflict_is_rejected(self):
        with self.assertRaises(ValueError):
            AvatarConcept('concept', 'old prompt', image_prompt='new prompt')


class ProfileCompatibilityTests(unittest.TestCase):
    def test_original_phase1_json_remains_readable(self):
        from models import ChannelProfile
        # Actual Phase 1 JSON shape: no Phase 2 fields or aliases.
        data = {
            'schema_version': 1,
            'competitor': {'url': 'https://youtube.com/@music', 'avatar_reference': 'ảnh.png',
                           'description': 'Nhạc Việt', 'target': {'artist': None, 'market': None, 'language': None}},
            'analysis': {'summary': 'Nhạc nhẹ', 'positioning': 'Thư giãn', 'audience': 'Người nghe Việt',
                         'strengths': [], 'opportunities': []},
            'selected_name': 'Giai Điệu Việt',
            'package': {'positioning': 'Nhạc Việt', 'avatar_concepts': [{'concept': f'Concept {i}', 'prompt': 'Ảnh'} for i in range(4)],
                        'banner_concept': 'Trăng', 'banner_prompt': 'Trăng trên hồ', 'description': 'Nhạc nhẹ',
                        'channel_keywords': ['nhạc'], 'video_core_keywords': ['nhạc'], 'video_tags': ['nhạc'],
                        'hashtags': ['#Nhạc'], 'title_templates': ['{artist}'], 'thumbnail_visual_guide': 'Màu ấm'},
        }
        profile = ChannelProfile.from_dict(data)
        self.assertEqual(profile.analysis.target_audience, 'Người nghe Việt')
        self.assertEqual(profile.package.avatar_concepts[0].image_prompt, 'Ảnh')
        self.assertIsNone(profile.package.banner)
        self.assertIsNone(profile.package.slogan)
        self.assertEqual(ChannelProfile.from_dict(profile.to_dict()), profile)

    def test_banner_alias_conflicts_are_rejected(self):
        from dataclasses import replace
        package = ChannelPackage.from_ai_dict(fixture('package'))
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            replace(package, banner_prompt='different prompt')
