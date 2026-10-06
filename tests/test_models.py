import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from models import (AvatarConcept, ChannelPackage, ChannelProfile, CompetitorAnalysis,
                    CompetitorInput, NameCandidate, TargetAudience)
from utils.json_io import read_profile, write_profile


def make_profile():
    return ChannelProfile(
        competitor=CompetitorInput('https://www.youtube.com/@music', 'ảnh đại diện.png',
                                   'Âm nhạc Việt Nam', TargetAudience(language='Tiếng Việt')),
        analysis=CompetitorAnalysis('Nhạc nhẹ', 'Thư giãn', 'Người nghe Việt', ['Hình ảnh'], ['Nhạc mới']),
        selected_name='Giai Điệu Việt 🎵',
        package=ChannelPackage(
            positioning='Nhạc Việt thư giãn',
            avatar_concepts=[AvatarConcept(f'Ý tưởng {i}', 'Ánh sáng ấm') for i in range(4)],
            banner_concept='Bầu trời', banner_prompt='Bầu trời đêm', description='Nghe nhạc mỗi ngày',
            channel_keywords=['nhạc Việt'], video_core_keywords=['thư giãn'], video_tags=['âm nhạc'],
            hashtags=['#NhạcViệt'], title_templates=['{artist} — {song}'], thumbnail_visual_guide='Màu ấm'))


class ModelTests(unittest.TestCase):
    def test_optional_target_and_name(self):
        self.assertEqual(TargetAudience(), TargetAudience(None, None, None))
        self.assertEqual(NameCandidate('Tên kênh', 'Phù hợp thị trường').name, 'Tên kênh')

    def test_invalid_inputs(self):
        for url in ('http://youtube.com/@x', 'https://evil.test/@x', 'https://youtube.com.evil.test/@x',
                    'https://youtube.com/', 'https://user@youtube.com/@x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                CompetitorInput(url, 'avatar.png', 'description')
        for field in ('avatar_reference', 'description'):
            data = dict(url='https://youtube.com/@x', avatar_reference='avatar.png', description='description')
            data[field] = '  '
            with self.subTest(field=field), self.assertRaises(ValueError):
                CompetitorInput(**data)
        with self.assertRaises(ValueError):
            TargetAudience(language='')
        with self.assertRaises(ValueError):
            NameCandidate('', 'reason')

    def test_exactly_four_avatars_and_required_package_lists(self):
        data = make_profile().to_dict()['package']
        data['avatar_concepts'] = [AvatarConcept('concept', 'prompt')] * 3
        with self.assertRaises(ValueError):
            ChannelPackage(**data)
        data['avatar_concepts'] = [AvatarConcept('concept', 'prompt')] * 4
        for field in ('channel_keywords', 'video_core_keywords', 'video_tags', 'hashtags', 'title_templates'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                ChannelPackage(**{**data, field: []})

    def test_unicode_export_round_trip(self):
        profile = make_profile()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'kênh nhạc' / 'channel_profile.json'
            write_profile(profile, path)
            raw = path.read_text(encoding='utf-8')
            self.assertIn('Giai Điệu Việt 🎵', raw)
            self.assertEqual(json.loads(raw)['schema_version'], 1)
            self.assertEqual(read_profile(path), profile)

    def test_reject_unsupported_or_invalid_persisted_profile(self):
        data = make_profile().to_dict()
        data['schema_version'] = 2
        with self.assertRaises(ValueError):
            ChannelProfile.from_dict(data)
        data['schema_version'] = True
        with self.assertRaises(ValueError):
            ChannelProfile.from_dict(data)
        data['schema_version'] = 1
        data['package']['avatar_concepts'] = []
        with self.assertRaises(ValueError):
            ChannelProfile.from_dict(data)

    def test_mutable_defaults_are_independent(self):
        first = CompetitorAnalysis('a', 'b', 'c')
        second = CompetitorAnalysis('a', 'b', 'c')
        first.strengths.append('one')
        self.assertEqual(second.strengths, [])
