from dataclasses import replace
import json
import unittest
from uuid import UUID
from core.manual import ManualAIBridge, ManualPromptService
from core.prompts import PromptLoader
from models import CompetitorInput, WorkflowSession, WorkflowState
from tests.helpers import ROOT, example


def new_bridge(store=None, display_name=None):
    return ManualAIBridge(CompetitorInput.from_v1_dict(example('competitor_input')),
                          ManualPromptService(PromptLoader(ROOT / 'prompts')), store=store,
                          display_name=display_name)


def advance_to(value, target):
    actions = {
        WorkflowState.INPUT: value.generate_analysis_prompt,
        WorkflowState.WAITING_FOR_ANALYSIS: lambda: value.import_analysis(json.dumps(example('analysis_response'), ensure_ascii=False)),
        WorkflowState.ANALYSIS_READY: value.generate_names_prompt,
        WorkflowState.WAITING_FOR_NAMES: lambda: value.import_names(json.dumps(example('names_response'), ensure_ascii=False)),
        WorkflowState.NAMES_READY: lambda: value.select_name('Mây Âm Nhạc'),
        WorkflowState.NAME_SELECTED: value.generate_package_prompt,
        WorkflowState.WAITING_FOR_PACKAGE: lambda: value.import_package(json.dumps(example('package_v1_response'), ensure_ascii=False)),
    }
    while value.session.state != target:
        actions[value.session.state]()
    return value


class SessionSerializationTests(unittest.TestCase):
    def test_unique_id_and_metadata_for_new_projects(self):
        first, second = new_bridge().session, new_bridge().session
        self.assertNotEqual(first.session_id, second.session_id)
        self.assertEqual(str(UUID(first.session_id)), first.session_id)
        self.assertEqual(first.created_at, first.updated_at)
        self.assertEqual(first.display_name, first.competitor.competitor_url)
        self.assertFalse(first.archived)
        self.assertEqual(first.revision, 0)

    def test_display_name_is_independent_of_uuid_and_selection(self):
        value = new_bridge(display_name='Dự án Việt — Música Española — Musica Italiana')
        identity = value.session.session_id
        advance_to(value, WorkflowState.NAME_SELECTED)
        self.assertEqual(value.session.session_id, identity)
        self.assertEqual(value.session.display_name, 'Dự án Việt — Música Española — Musica Italiana')
        self.assertEqual(value.session.selected_name, 'Mây Âm Nhạc')

    def test_every_state_round_trips_exactly(self):
        for state in WorkflowState:
            value = advance_to(new_bridge(), state)
            with self.subTest(state=state):
                data = json.loads(json.dumps(value.session.to_dict(), ensure_ascii=False))
                restored = WorkflowSession.from_dict(data)
                self.assertEqual(restored, value.session)
                self.assertEqual(restored.pending_prompt, value.session.pending_prompt)
                self.assertEqual(restored.state, state)

    def test_metadata_is_stable_across_transitions(self):
        value = new_bridge()
        identity, created = value.session.session_id, value.session.created_at
        advance_to(value, WorkflowState.COMPLETE)
        self.assertEqual(value.session.session_id, identity)
        self.assertEqual(value.session.created_at, created)
        self.assertEqual(value.session.revision, 7)
        self.assertGreaterEqual(value.session.updated_at, created)

    def test_future_or_invalid_schema_versions_are_rejected(self):
        data = new_bridge().session.to_dict()
        for version in (2, 0, True, '1', None):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'schema_version'):
                WorkflowSession.from_dict({**data, 'schema_version': version})

    def test_missing_and_unexpected_fields_are_not_repaired(self):
        data = new_bridge().session.to_dict()
        for field in data:
            broken = dict(data)
            del broken[field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'missing fields'):
                WorkflowSession.from_dict(broken)
        with self.assertRaisesRegex(ValueError, 'unknown fields'):
            WorkflowSession.from_dict({**data, 'api_key': 'dummy-value'})

    def test_invalid_metadata_and_state(self):
        data = new_bridge().session.to_dict()
        for field, values in {
            'session_id': ['../escape', '', 1, 'NOT-UUID'], 'created_at': [None, '', '2026-01-01'],
            'updated_at': [None, 'invalid', '2000-01-01T00:00:00+00:00'],
            'display_name': [None, '', False], 'revision': [-1, True, '1'],
            'archived': [None, 'false', 1], 'state': ['unknown', 'COMPLETE'],
        }.items():
            for invalid in values:
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    WorkflowSession.from_dict({**data, field: invalid})

    def test_inconsistent_state_or_nested_data_is_rejected(self):
        data = new_bridge().session.to_dict()
        with self.assertRaises(ValueError):
            WorkflowSession.from_dict({**data, 'state': 'WAITING_FOR_ANALYSIS'})
        for field, value in (('analysis', example('analysis_response')), ('names', []), ('package', {})):
            with self.subTest(field=field), self.assertRaises(ValueError):
                WorkflowSession.from_dict({**data, field: value})
        data['competitor']['target']['unexpected'] = 'x'
        with self.assertRaises(ValueError):
            WorkflowSession.from_dict(data)

    def test_nested_mutation_cannot_be_serialized(self):
        session = advance_to(new_bridge(), WorkflowState.COMPLETE).session
        session.package.channel_keywords.clear()
        with self.assertRaises(ValueError):
            session.to_dict()

    def test_profile_export_shape_stays_compatible(self):
        session = advance_to(new_bridge(), WorkflowState.COMPLETE).session
        profile = session.to_profile_dict()
        self.assertEqual(profile['profile_type'], 'manual_text_v1')
        self.assertEqual(profile['selected_name'], 'Mây Âm Nhạc')
        self.assertNotIn('api_key', profile)
