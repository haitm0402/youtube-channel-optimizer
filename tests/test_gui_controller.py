"""Desktop actions exercise the existing persistent bridge without a display."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from config import Settings
from core.errors import MalformedResponseError, ResponseValidationError, WorkflowStateError
from gui.controller import GUIController, EditorScreen, ProjectFilter, package_sections, screen_for_state
from gui.platform import open_export_folder
from tests.helpers import ROOT, example
from tests.test_session_models import new_bridge, advance_to
from models import WorkflowState


class GUIControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / 'Dự án Música'
        self.settings = Settings(prompts_dir=ROOT / 'prompts', data_dir=root / 'data', exports_dir=root / 'exports')
        self.controller = GUIController(self.settings)

    def create(self):
        return self.controller.create_project(project_name='Música Việt', competitor_url='https://www.youtube.com/@music',
                                              competitor_description='Nhạc Việt và España', target_market='Việt Nam')

    def response(self, name):
        return json.dumps(example(name), ensure_ascii=False)

    def saved_at(self, state):
        return advance_to(new_bridge(self.controller.store, 'Dự án Việt'), state).session

    def test_create_uses_existing_settings_models_and_persistence(self):
        session = self.create()
        self.assertEqual(session.state, WorkflowState.WAITING_FOR_ANALYSIS)
        self.assertEqual(session.display_name, 'Música Việt')
        self.assertEqual(self.controller.store.load_session(session.session_id), session)
        self.assertIn('Nhạc Việt', session.pending_prompt)
        self.assertTrue((self.settings.data_dir / 'sessions').is_dir())

    def test_blank_project_is_rejected_before_persistence(self):
        with self.assertRaisesRegex(ValueError, 'Project Name'):
            self.controller.create_project(project_name=' ', competitor_url='https://youtube.com/@music', competitor_description='music')
        self.assertEqual(self.controller.list_projects(), [])

    def test_mapping_covers_all_states(self):
        expected = [EditorScreen.ANALYSIS, EditorScreen.ANALYSIS, EditorScreen.NAMES_PROMPT,
                    EditorScreen.NAMES_PROMPT, EditorScreen.NAME_SELECTION, EditorScreen.PACKAGE_PROMPT,
                    EditorScreen.PACKAGE_PROMPT, EditorScreen.PACKAGE]
        self.assertEqual([screen_for_state(state) for state in WorkflowState], expected)

    def test_resume_every_stage_and_preserve_completed_results(self):
        transitions = {WorkflowState.INPUT: WorkflowState.WAITING_FOR_ANALYSIS,
                       WorkflowState.ANALYSIS_READY: WorkflowState.WAITING_FOR_NAMES,
                       WorkflowState.NAME_SELECTED: WorkflowState.WAITING_FOR_PACKAGE}
        for state in WorkflowState:
            with self.subTest(state=state):
                saved = self.saved_at(state)
                controller = GUIController(self.settings)
                resumed = controller.open_project(saved.session_id)
                self.assertEqual(resumed.state, transitions.get(state, state))
                self.assertEqual(resumed.analysis, saved.analysis)
                self.assertEqual(resumed.names, saved.names)
                self.assertEqual(resumed.package, saved.package)
                self.assertEqual(resumed.selected_name, saved.selected_name)
                if state not in transitions:
                    self.assertEqual(resumed, saved)

    def test_regenerate_display_is_exact_read_without_revision_change(self):
        self.create()
        before = self.controller.session.to_dict()
        with patch.object(self.controller.prompts, 'analysis_prompt', side_effect=AssertionError('Must not render')):
            for _ in range(3):
                self.assertEqual(self.controller.pending_prompt(), before['pending_prompt'])
        self.assertEqual(self.controller.session.to_dict(), before)
        self.assertEqual(self.controller.store.load_session(self.controller.session.session_id).to_dict(), before)

    def test_invalid_json_does_not_advance_any_waiting_stage(self):
        for state in (WorkflowState.WAITING_FOR_ANALYSIS, WorkflowState.WAITING_FOR_NAMES, WorkflowState.WAITING_FOR_PACKAGE):
            with self.subTest(state=state):
                saved = self.saved_at(state)
                self.controller.open_project(saved.session_id)
                for invalid in ('not JSON é', '{}', '```json\n{}\n```'):
                    with self.assertRaises((MalformedResponseError, ResponseValidationError)):
                        self.controller.submit_json(invalid)
                    self.assertEqual(self.controller.session, saved)
                    self.assertEqual(self.controller.store.load_session(saved.session_id), saved)

    def test_valid_workflow_requires_explicit_selection_and_renders_all_sections(self):
        self.create()
        self.controller.submit_json(self.response('analysis_response'))
        self.assertEqual(self.controller.session.state, WorkflowState.WAITING_FOR_NAMES)
        self.controller.submit_json(self.response('names_response'))
        session = self.controller.session
        self.assertEqual(len(session.names.names), 12)
        self.assertIsNone(session.selected_name)
        for invalid in (None, '', 'Not a suggestion'):
            with self.assertRaises((ValueError, WorkflowStateError)):
                self.controller.select_name(invalid)
            self.assertEqual(self.controller.session, session)
        self.controller.select_name('Mây Âm Nhạc')
        self.assertEqual(self.controller.session.state, WorkflowState.WAITING_FOR_PACKAGE)
        self.controller.submit_json(self.response('package_v1_response'))
        sections = package_sections(self.controller.session)
        self.assertEqual(len(sections), 10)
        self.assertEqual({item.field for item in sections}, set(self.controller.session.package.to_dict()))
        for section in sections:
            value = getattr(self.controller.session.package, section.field)
            self.assertEqual(section.text, '\n'.join(value) if isinstance(value, list) else value)

    def test_incomplete_package_cannot_render_or_export(self):
        self.create()
        with self.assertRaises(WorkflowStateError):
            package_sections(self.controller.session)
        with self.assertRaises((ValueError, WorkflowStateError)):
            self.controller.export_project()

    def test_archive_confirmation_and_read_only_resume(self):
        session = self.create()
        self.assertFalse(self.controller.archive_project(session.session_id, confirmed=False))
        self.assertEqual(self.controller.store.load_session(session.session_id), session)
        self.assertTrue(self.controller.archive_project(session.session_id, confirmed=True))
        archived = self.controller.open_project(session.session_id)
        self.assertTrue(archived.archived)
        self.assertEqual(archived.pending_prompt, session.pending_prompt)
        for action in (lambda: self.controller.submit_json('{}'), lambda: self.controller.select_name('Mây Âm Nhạc')):
            with self.assertRaisesRegex(WorkflowStateError, 'read-only'):
                action()
        self.assertEqual(self.controller.prepare_screen(), archived)
        self.assertEqual(self.controller.store.load_session(session.session_id), archived)

    def test_filters_separate_active_completed_archived(self):
        active = self.saved_at(WorkflowState.NAMES_READY)
        complete = self.saved_at(WorkflowState.COMPLETE)
        archived = self.saved_at(WorkflowState.WAITING_FOR_ANALYSIS)
        self.controller.archive_project(archived.session_id, confirmed=True)
        for filter_name, identity in ((ProjectFilter.ACTIVE, active.session_id), (ProjectFilter.COMPLETED, complete.session_id),
                                      (ProjectFilter.ARCHIVED, archived.session_id)):
            self.assertEqual([item.session_id for item in self.controller.list_projects(filter_name)], [identity])

    def test_export_uses_settings_preserves_unicode_and_never_overwrites(self):
        session = self.saved_at(WorkflowState.COMPLETE)
        self.controller.open_project(session.session_id)
        first = self.controller.export_project()
        contents = {p.name: p.read_bytes() for p in first.iterdir()}
        second = self.controller.export_project()
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, self.settings.exports_dir)
        self.assertEqual(len(contents), 9)
        self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()}, contents)
        self.assertIn('Mây Âm Nhạc', (first / 'channel_profile.json').read_text(encoding='utf-8'))
        self.assertEqual(self.controller.store.load_session(session.session_id), session)

    def test_safe_windows_folder_open(self):
        folder = Path(self.temp.name)
        with patch('gui.platform.sys.platform', 'win32'), patch('gui.platform.os.startfile', create=True) as startfile:
            open_export_folder(folder)
            startfile.assert_called_once_with(str(folder.resolve()))

    def test_folder_must_exist_and_be_directory(self):
        with self.assertRaises(FileNotFoundError):
            open_export_folder(Path(self.temp.name) / 'missing')
        file = Path(self.temp.name) / 'file'
        file.write_text('test')
        with self.assertRaises(ValueError):
            open_export_folder(file)
