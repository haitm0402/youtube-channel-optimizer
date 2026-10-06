"""Functional Tk smoke checks; optional when the host has no display server."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from config import Settings
from gui.controller import GUIController
from tests.helpers import ROOT, example


class DesktopSmokeTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
            from gui.main_window import MainWindow
        except ImportError as exc:
            self.skipTest(f'Tk unavailable: {exc}')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(prompts_dir=ROOT / 'prompts', data_dir=Path(self.temp.name) / 'data',
                                 exports_dir=Path(self.temp.name) / 'exports')
        try:
            self.window = MainWindow(GUIController(self.settings))
        except tk.TclError as exc:
            self.skipTest(f'Display unavailable: {exc}')
        self.addCleanup(lambda: self.window.close() if not self.window.closed else None)
        self.wait()

    def wait(self):
        deadline = time.monotonic() + 5
        while self.window.busy and time.monotonic() < deadline:
            self.window.update()
            time.sleep(.01)
        self.window.update()
        self.assertFalse(self.window.busy, 'Local operation did not finish')

    def create(self):
        self.window.show_new()
        form = self.window.view
        form.entries['project_name'].insert(0, 'Música — Dự án Việt')
        form.entries['competitor_url'].insert(0, 'https://youtube.com/@music')
        form.description.set('Nhạc Việt\nEspaña e Italia')
        form.create()
        self.wait()
        self.assertEqual(self.window.error.get(), '')

    def submit(self, fixture):
        self.window.view.response.set(json.dumps(example(fixture), ensure_ascii=False))
        self.window.view.submit()
        self.wait()
        self.assertEqual(self.window.error.get(), '')

    def test_full_desktop_workflow_copy_paste_resume_export_archive(self):
        from gui.widgets import CopyButton
        self.create()
        editor = self.window.view
        saved = self.window.controller.session
        prompt = editor.prompt.get()
        self.assertEqual(editor.prompt.text.cget('state'), 'disabled')
        button = CopyButton(editor, self.window, lambda: prompt)
        button.invoke()
        self.assertEqual(self.window.clipboard_get(), prompt)
        self.assertEqual(button.cget('text'), 'Copied')
        self.window.clipboard_clear()
        self.window.clipboard_append('Invalid JSON — Việt\nEspaña')
        editor.response.text.event_generate('<<Paste>>')
        self.window.update()
        text = editor.response.get()
        self.assertIn('Việt', text)
        editor.response.select_all()
        self.assertTrue(editor.response.text.tag_ranges('sel'))
        editor.submit()
        self.wait()
        self.assertIs(self.window.view, editor)
        self.assertEqual(editor.response.get(), text)
        self.assertIn('Invalid JSON', self.window.error.get())
        self.assertEqual(self.window.controller.session, saved)
        editor.refresh_prompt()
        self.wait()
        self.assertEqual(editor.prompt.get(), prompt)
        self.assertEqual(editor.response.get(), text)
        self.submit('analysis_response')
        self.submit('names_response')
        editor = self.window.view
        self.assertEqual(len(editor.names_tree.get_children()), 12)
        self.assertEqual(editor.names_tree.selection(), ())
        editor.select_name()
        self.wait()
        self.assertIn('Please select', self.window.error.get())
        identity = self.window.controller.session.session_id
        self.window.close()
        from gui.main_window import MainWindow
        self.window = MainWindow(GUIController(self.settings))
        self.wait()
        self.window.open_project(identity)
        self.wait()
        editor = self.window.view
        self.assertEqual(editor.names_tree.selection(), ())
        selected = next(key for key, value in editor.candidates.items() if value.name == 'Mây Âm Nhạc')
        editor.names_tree.selection_set(selected)
        editor.select_name()
        self.wait()
        self.submit('package_v1_response')
        editor = self.window.view
        self.assertIn('Mây', self.window.controller.session.selected_name)
        editor.export()
        self.wait()
        self.assertTrue(editor.destination.is_dir())
        with patch('gui.project_editor.open_export_folder') as opener:
            editor.open_folder()
            self.wait()
            opener.assert_called_once_with(editor.destination)
        self.window.show_library()
        self.wait()
        library = self.window.view
        library.filter.set('Completed')
        library.refresh()
        self.wait()
        library.tree.selection_set(identity)
        with patch('gui.project_list.messagebox.askyesno', return_value=False):
            library.archive()
        self.assertFalse(self.window.controller.store.load_session(identity).archived)
        with patch('gui.project_list.messagebox.askyesno', return_value=True):
            library.archive()
            self.wait()
        library.filter.set('Archived')
        library.refresh()
        self.wait()
        self.assertEqual(library.tree.get_children(), (identity,))
        library.tree.selection_set(identity)
        library.open_selected()
        self.wait()
        self.assertTrue(self.window.view.session.archived)
        self.window.geometry('900x660')
        self.window.update()
        self.assertEqual(self.window.error.get(), '')
