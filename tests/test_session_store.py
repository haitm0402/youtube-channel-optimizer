from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4
from core.channel_library import ChannelLibrary
from core.contracts import SessionStore
from core.errors import (MalformedResponseError, ResponseValidationError, SessionConflictError,
                         SessionStoreError, WorkflowStateError)
from core.manual import ManualAIBridge, ManualPromptService
from core.prompts import PromptLoader
from models import WorkflowState
from models.session_metadata import next_timestamp
from services.json_sessions import JsonSessionStore, _file_lock
from tests.helpers import ROOT, example
from tests.test_session_models import advance_to, new_bridge
from utils.manual_export import export_manual_profile


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'Dữ liệu Música Italiana'
        self.store = JsonSessionStore(self.root)

    def resume(self, session_id):
        return ManualAIBridge.load_session(session_id, ManualPromptService(PromptLoader(ROOT / 'prompts')), self.store)

    def test_protocol_and_creation_save_load(self):
        self.assertIsInstance(self.store, SessionStore)
        value = new_bridge(self.store)
        self.assertEqual(self.store.load_session(value.session.session_id), value.session)
        self.assertEqual(len(list(self.store.directory.glob('*.json'))), 1)
        self.assertEqual(value.session.state, WorkflowState.INPUT)

    def test_every_transition_is_saved_without_explicit_save(self):
        value = new_bridge(self.store)
        for state in WorkflowState:
            advance_to(value, state)
            with self.subTest(state=state):
                self.assertEqual(self.store.load_session(value.session.session_id), value.session)

    def test_resume_every_state_without_regenerating_results(self):
        for state in WorkflowState:
            value = advance_to(new_bridge(self.store), state)
            before = (self.store.directory / f'{value.session.session_id}.json').read_bytes()
            with patch.object(ManualPromptService, 'analysis_prompt', side_effect=AssertionError('Do not regenerate')), patch.object(ManualPromptService, 'names_prompt', side_effect=AssertionError('Do not regenerate')), patch.object(ManualPromptService, 'package_prompt', side_effect=AssertionError('Do not regenerate')):
                restored = self.resume(value.session.session_id)
                self.assertEqual(restored.session, value.session)
                if state == WorkflowState.WAITING_FOR_ANALYSIS:
                    self.assertEqual(restored.generate_analysis_prompt(), value.session.pending_prompt)
                elif state == WorkflowState.WAITING_FOR_NAMES:
                    self.assertEqual(restored.generate_names_prompt(), value.session.pending_prompt)
                elif state == WorkflowState.WAITING_FOR_PACKAGE:
                    self.assertEqual(restored.generate_package_prompt(), value.session.pending_prompt)
                elif state == WorkflowState.NAMES_READY:
                    restored.select_name(restored.session.names.names[0].name)
                elif state == WorkflowState.COMPLETE:
                    folder = export_manual_profile(restored.session, self.root / 'exports')
                    self.assertEqual(len(list(folder.iterdir())), 9)
            if state != WorkflowState.NAMES_READY:
                self.assertEqual(before, (self.store.directory / f'{value.session.session_id}.json').read_bytes())

    def test_invalid_import_does_not_change_disk_or_memory(self):
        value = new_bridge(self.store)
        for state, importer in (
            (WorkflowState.WAITING_FOR_ANALYSIS, value.import_analysis),
            (WorkflowState.WAITING_FOR_NAMES, value.import_names),
            (WorkflowState.WAITING_FOR_PACKAGE, value.import_package),
        ):
            advance_to(value, state)
            path = self.store.directory / f'{value.session.session_id}.json'
            previous = path.read_bytes()
            session = value.session
            for bad in ('bad JSON', '{}'):
                with self.assertRaises((MalformedResponseError, ResponseValidationError)):
                    importer(bad)
                self.assertIs(value.session, session)
                self.assertEqual(path.read_bytes(), previous)

    def test_atomic_replace_failure_preserves_previous_file_and_state(self):
        value = new_bridge(self.store)
        path = self.store.directory / f'{value.session.session_id}.json'
        before = path.read_bytes()
        session = value.session
        with patch('services.json_sessions.os.replace', side_effect=PermissionError('Simulated Windows sharing violation')):
            with self.assertRaises(SessionStoreError):
                value.generate_analysis_prompt()
        self.assertIs(value.session, session)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.store.directory.glob('*.tmp')), [])
        value.generate_analysis_prompt()
        self.assertEqual(self.store.load_session(session.session_id).state, WorkflowState.WAITING_FOR_ANALYSIS)

    def test_fsync_failure_preserves_previous_session(self):
        value = new_bridge(self.store)
        path = self.store.directory / f'{value.session.session_id}.json'
        before = path.read_bytes()
        with patch('services.json_sessions.os.fsync', side_effect=OSError('Simulated disk failure')):
            with self.assertRaises(SessionStoreError):
                value.generate_analysis_prompt()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(value.session.state, WorkflowState.INPUT)
        self.assertEqual(list(self.store.directory.glob('*.tmp')), [])

    def test_temp_file_is_same_directory_and_closed_before_replace(self):
        import os
        value = new_bridge(self.store)
        original = os.replace
        observed = []
        def inspect(source, destination):
            self.assertEqual(Path(source).parent, self.store.directory)
            self.assertEqual(Path(destination).parent, self.store.directory)
            # A separately opened handle can read the complete candidate before replace.
            with Path(source).open('rb') as handle:
                data = json.load(handle)
            self.assertEqual(data['state'], 'WAITING_FOR_ANALYSIS')
            observed.append(source)
            return original(source, destination)
        with patch('services.json_sessions.os.replace', side_effect=inspect):
            value.generate_analysis_prompt()
        self.assertEqual(len(observed), 1)
        self.assertFalse(Path(observed[0]).exists())

    def test_stale_process_cannot_overwrite_newer_data(self):
        value = new_bridge(self.store)
        stale = self.resume(value.session.session_id)
        value.generate_analysis_prompt()
        with self.assertRaises(SessionConflictError):
            stale.generate_analysis_prompt()
        self.assertEqual(stale.session.state, WorkflowState.INPUT)
        self.assertEqual(self.store.load_session(value.session.session_id), value.session)

    def test_busy_file_lock_fails_without_overwriting(self):
        value = new_bridge(self.store)
        path = self.store.directory / f'{value.session.session_id}.json'
        before = path.read_bytes()
        with _file_lock(path.with_suffix('.lock')):
            with self.assertRaises(SessionConflictError):
                value.generate_analysis_prompt()
        self.assertEqual(path.read_bytes(), before)
        value.generate_analysis_prompt()  # Lock released; next write can proceed.

    def test_corrupt_json_and_incompatible_schema_are_not_repaired(self):
        value = new_bridge(self.store)
        path = self.store.directory / f'{value.session.session_id}.json'
        for raw in ('broken JSON', '{"x":1,"x":2}', json.dumps({**value.session.to_dict(), 'schema_version': 99}),
                    json.dumps({**value.session.to_dict(), 'state': 'COMPLETE'})):
            path.write_text(raw, encoding='utf-8')
            before = path.read_bytes()
            with self.assertRaisesRegex(SessionStoreError, 'Corrupt or incompatible'):
                self.store.load_session(value.session.session_id)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_invalid_and_mismatched_session_ids(self):
        with self.assertRaisesRegex(SessionStoreError, 'not found'):
            self.store.load_session(str(uuid4()))
        for identity in ('../escape', 'not-uuid', ''):
            with self.assertRaisesRegex(SessionStoreError, 'UUID'):
                self.store.load_session(identity)
        value = new_bridge(self.store)
        data = value.session.to_dict()
        data['session_id'] = str(uuid4())
        (self.store.directory / f'{value.session.session_id}.json').write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(SessionStoreError, 'does not match'):
            self.store.load_session(value.session.session_id)

    def test_existing_corrupt_session_cannot_be_overwritten(self):
        value = new_bridge(self.store)
        path = self.store.directory / f'{value.session.session_id}.json'
        path.write_text('broken JSON', encoding='utf-8')
        with self.assertRaises(SessionStoreError):
            value.generate_analysis_prompt()
        self.assertEqual(path.read_text(encoding='utf-8'), 'broken JSON')

    def test_unicode_and_spaces_round_trip_without_secrets(self):
        value = new_bridge(self.store, display_name='Mây Âm Nhạc — Canción Española — Canzone Italiana')
        advance_to(value, WorkflowState.COMPLETE)
        restored = self.resume(value.session.session_id)
        self.assertEqual(restored.session, value.session)
        raw = (self.store.directory / f'{value.session.session_id}.json').read_text(encoding='utf-8')
        self.assertIn('Canción Española', raw)
        self.assertIn('Mây Âm Nhạc', raw)
        self.assertNotIn('ai_api_key', raw)

    def test_invalid_revision_or_created_at_updates_are_rejected(self):
        session = new_bridge(self.store).session
        for candidate, expected in ((replace(session, revision=2), 0),
                                    (replace(session, created_at='2000-01-01T00:00:00+00:00', revision=1), 0)):
            with self.assertRaises(SessionStoreError):
                self.store.save_session(candidate, expected_revision=expected)
        with self.assertRaises(SessionConflictError):
            self.store.save_session(session)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = JsonSessionStore(self.temporary.name)
        self.library = ChannelLibrary(self.store)

    def test_empty_library_has_no_side_effects(self):
        self.assertEqual(self.library.list_projects(), [])
        self.assertFalse(self.store.directory.exists())

    def test_library_summaries_include_metadata_without_duplicate_index(self):
        value = advance_to(new_bridge(self.store, 'Dự án Music'), WorkflowState.COMPLETE)
        item = self.library.list_projects()[0]
        self.assertEqual(item.session_id, value.session.session_id)
        self.assertEqual(item.display_name, 'Dự án Music')
        self.assertEqual(item.selected_channel_name, 'Mây Âm Nhạc')
        self.assertEqual(item.status, 'COMPLETE')
        self.assertEqual(item.target_market, 'Việt Nam')
        self.assertEqual(item.target_language, 'Tiếng Việt')
        self.assertEqual(item.created_at, value.session.created_at)
        self.assertEqual(item.updated_at, value.session.updated_at)
        self.assertFalse((Path(self.temporary.name) / 'index.json').exists())

    def test_in_progress_statuses(self):
        value = new_bridge(self.store)
        for state, status in ((WorkflowState.INPUT, 'IN PROGRESS'),
                              (WorkflowState.WAITING_FOR_ANALYSIS, 'WAITING FOR ANALYSIS'),
                              (WorkflowState.WAITING_FOR_NAMES, 'WAITING FOR NAMES'),
                              (WorkflowState.WAITING_FOR_PACKAGE, 'WAITING FOR PACKAGE')):
            advance_to(value, state)
            self.assertEqual(self.library.list_projects()[0].status, status)

    def test_archive_keeps_file_and_excludes_default_list(self):
        first, second = new_bridge(self.store), new_bridge(self.store)
        session = first.session
        archived = self.library.archive_session(session.session_id)
        self.assertTrue(archived.archived)
        self.assertEqual(archived.state, session.state)
        self.assertEqual(archived.created_at, session.created_at)
        self.assertEqual(len(self.library.list_projects()), 1)
        self.assertEqual(self.library.list_projects()[0].session_id, second.session.session_id)
        self.assertEqual(len(self.library.list_projects(archived=True)), 1)
        self.assertTrue((self.store.directory / f'{session.session_id}.json').exists())
        self.assertEqual(self.library.archive_session(session.session_id), archived)

    def test_archived_completed_sessions_can_view_export_but_not_resume(self):
        value = advance_to(new_bridge(self.store), WorkflowState.COMPLETE)
        self.library.archive_session(value.session.session_id)
        loaded = self.library.load_session(value.session.session_id)
        self.assertEqual(loaded.package, value.session.package)
        with self.assertRaisesRegex(WorkflowStateError, 'Archived'):
            ManualAIBridge.load_session(loaded.session_id, ManualPromptService(PromptLoader(ROOT / 'prompts')), self.store)
        folder = export_manual_profile(loaded, Path(self.temporary.name) / 'exports')
        self.assertEqual(len(list(folder.iterdir())), 9)

    def test_corruption_is_reported_instead_of_silently_omitted(self):
        value = new_bridge(self.store)
        (self.store.directory / f'{value.session.session_id}.json').write_text('broken', encoding='utf-8')
        with self.assertRaises(SessionStoreError):
            self.library.list_projects()

    def test_archive_save_failure_leaves_project_active(self):
        value = new_bridge(self.store)
        with patch('services.json_sessions.os.replace', side_effect=OSError('Disk failure')):
            with self.assertRaises(SessionStoreError):
                self.library.archive_session(value.session.session_id)
        self.assertFalse(self.store.load_session(value.session.session_id).archived)
