import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from config import load_settings
from services.json_sessions import JsonSessionStore
from tests.helpers import ROOT, example


def paste(name):
    return json.dumps(example(name), ensure_ascii=False) + '\nEND_JSON\n'


class PersistentCLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'Música e Canzoni'
        self.root.mkdir()
        self.config = self.root / 'settings.toml'
        self.config.write_text('prompts_dir = ' + json.dumps(str(ROOT / 'prompts')) +
                               '\ndata_dir = "dữ liệu"\nexports_dir = "exports"\n', encoding='utf-8')
        self.store = JsonSessionStore(self.root / 'dữ liệu')

    def invoke(self, *arguments, text=''):
        environment = dict(os.environ)
        for name in ('YCO_AI_PROVIDER', 'YCO_AI_MODEL', 'YCO_AI_API_KEY'):
            environment.pop(name, None)
        environment['PYTHONIOENCODING'] = 'utf-8'
        return subprocess.run([sys.executable, str(ROOT / 'app.py'), '--config', str(self.config), *arguments],
                              input=text, capture_output=True, encoding='utf-8', cwd=self.root,
                              env=environment, timeout=20)

    def start(self, text=''):
        result = self.invoke('--manual', '--new', '--input-json', str(ROOT / 'examples' / 'competitor_input.json'),
                             '--display-name', 'Nhạc Việt — Canción — Canzone', text=text)
        identity = self.store.list_sessions()[0].session_id
        return result, identity

    def test_restart_resume_from_names_ready_completes_without_reanalysis(self):
        first, identity = self.start(paste('analysis_response') + paste('names_response'))
        self.assertNotEqual(first.returncode, 0)  # EOF stops the first process intentionally.
        self.assertIn('cancelled', first.stderr)
        self.assertEqual(self.store.load_session(identity).state.value, 'NAMES_READY')
        second = self.invoke('--manual', '--resume', identity,
                             text='Mây Âm Nhạc\n' + paste('package_v1_response'))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotIn('# Task: analyze_competitor', second.stdout)
        self.assertNotIn('# Task: generate_names', second.stdout)
        self.assertIn('Mây Âm Nhạc', second.stdout)
        completed = self.store.load_session(identity)
        self.assertEqual(completed.state.value, 'COMPLETE')
        self.assertEqual(completed.revision, 7)
        folder = self.root / 'exports' / 'Mây Âm Nhạc'
        self.assertEqual(len(list(folder.iterdir())), 9)
        third = self.invoke('--manual', '--resume', identity)
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertNotIn('# Task:', third.stdout)
        self.assertEqual(self.store.load_session(identity), completed)
        self.assertTrue((self.root / 'exports' / 'Mây Âm Nhạc-1').is_dir())

    def test_waiting_for_analysis_restores_exact_prompt(self):
        first, identity = self.start()
        session = self.store.load_session(identity)
        self.assertEqual(session.state.value, 'WAITING_FOR_ANALYSIS')
        second = self.invoke('--manual', '--resume', identity)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn(session.pending_prompt, first.stdout)
        self.assertIn(session.pending_prompt, second.stdout)
        self.assertEqual(self.store.load_session(identity), session)

    def test_waiting_for_names_restores_prompt_and_analysis(self):
        first, identity = self.start(paste('analysis_response'))
        session = self.store.load_session(identity)
        self.assertEqual(session.state.value, 'WAITING_FOR_NAMES')
        second = self.invoke('--manual', '--resume', identity)
        self.assertIn(session.pending_prompt, second.stdout)
        self.assertNotIn('# Task: analyze_competitor', second.stdout)
        self.assertEqual(self.store.load_session(identity), session)

    def test_waiting_for_package_restores_exact_prompt(self):
        first, identity = self.start(paste('analysis_response') + paste('names_response') + 'Mây Âm Nhạc\n')
        session = self.store.load_session(identity)
        self.assertEqual(session.state.value, 'WAITING_FOR_PACKAGE')
        second = self.invoke('--manual', '--resume', identity, text=paste('package_v1_response'))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn(session.pending_prompt, second.stdout)
        self.assertEqual(self.store.load_session(identity).selected_name, 'Mây Âm Nhạc')

    def test_invalid_pasted_json_in_reopened_process_preserves_disk(self):
        _, identity = self.start()
        path = self.store.directory / f'{identity}.json'
        before = path.read_bytes()
        failed = self.invoke('--manual', '--resume', identity, text='broken\nEND_JSON\n{}\nEND_JSON\n')
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('Response rejected:', failed.stdout)
        self.assertEqual(path.read_bytes(), before)

    def test_list_archive_and_view_without_deletion(self):
        _, identity = self.start()
        listing = self.invoke('--sessions')
        self.assertEqual(listing.returncode, 0, listing.stderr)
        metadata = json.loads(listing.stdout)[0]
        self.assertEqual(metadata['session_id'], identity)
        self.assertEqual(metadata['display_name'], 'Nhạc Việt — Canción — Canzone')
        self.assertEqual(metadata['status'], 'WAITING FOR ANALYSIS')
        self.assertIn('reference_artist', metadata)
        self.assertIn('selected_channel_name', metadata)
        archived = self.invoke('--archive', identity)
        self.assertEqual(archived.returncode, 0, archived.stderr)
        self.assertEqual(json.loads(self.invoke('--sessions').stdout), [])
        self.assertEqual(len(json.loads(self.invoke('--sessions', '--archived').stdout)), 1)
        view = self.invoke('--view-session', identity)
        self.assertEqual(json.loads(view.stdout)['state'], 'WAITING_FOR_ANALYSIS')
        self.assertTrue(json.loads(view.stdout)['archived'])
        self.assertTrue((self.store.directory / f'{identity}.json').is_file())
        self.assertNotEqual(self.invoke('--manual', '--resume', identity).returncode, 0)

    def test_complete_archive_can_export_safely_and_view_package(self):
        first, identity = self.start(paste('analysis_response') + paste('names_response') + 'Mây Âm Nhạc\n' + paste('package_v1_response'))
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self.invoke('--archive', identity).returncode, 0)
        result = self.invoke('--export-session', identity)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'exports' / 'Mây Âm Nhạc-1' / 'channel_profile.json').is_file())
        view = self.invoke('--view-session', identity)
        self.assertEqual(json.loads(view.stdout)['package'], example('package_v1_response'))

    def test_in_progress_export_is_rejected(self):
        _, identity = self.start()
        result = self.invoke('--export-session', identity)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('COMPLETE', result.stderr)
        self.assertFalse((self.root / 'exports').exists())

    def test_conflicting_cli_options_are_rejected(self):
        for arguments in (('--resume', 'unused'), ('--new',), ('--archived',),
                          ('--sessions', '--manual'), ('--manual', '--resume', 'unused', '--input-json', 'unused.json'),
                          ('--manual', '--resume', 'unused', '--display-name', 'name')):
            with self.subTest(arguments=arguments):
                self.assertNotEqual(self.invoke(*arguments).returncode, 0)
        self.assertFalse(self.store.directory.exists())

    def test_library_commands_do_not_need_prompt_files(self):
        _, identity = self.start()
        self.config.write_text('data_dir = "dữ liệu"\nprompts_dir = "missing"\n', encoding='utf-8')
        self.assertEqual(self.invoke('--sessions').returncode, 0)
        self.assertEqual(self.invoke('--view-session', identity).returncode, 0)


class DataDirectoryConfigTests(unittest.TestCase):
    def test_default_data_directory(self):
        self.assertEqual(load_settings(environ={}).data_dir, ROOT / 'data')

    def test_unicode_relative_data_directory(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.toml'
            path.write_text('data_dir = "Dữ liệu Música con spazi"', encoding='utf-8')
            self.assertEqual(load_settings(path, environ={}).data_dir, Path(directory) / 'Dữ liệu Música con spazi')

    def test_invalid_data_directory_setting(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.toml'
            for invalid in ('123', '""', 'false'):
                path.write_text('data_dir = ' + invalid, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_settings(path, environ={})
