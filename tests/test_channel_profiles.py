"""Channel Profile Manager persistence and integration tests."""
import json
from pathlib import Path
import tempfile
import unittest

from config import Settings
from core.channel_profiles import ChannelProfileManager
from gui.controller import GUIController
from models.channel_dna import ChannelDNAProfile
from models.manual import WorkflowState
from services.json_channel_profiles import JsonChannelProfileStore
from tests.helpers import ROOT
from tests.test_session_models import advance_to, new_bridge


class ChannelDNAProfileTests(unittest.TestCase):
    def test_round_trip_unicode_and_prompt_payload(self):
        profile = ChannelDNAProfile(
            channel_name="Música Brava — Đêm",
            target_artist="Future",
            target_market="United States",
            target_language="English",
            genre="Hip-Hop / Rap",
            lyric_rules="Direct, concise, real-life writing.",
            channel_keywords=["rap music", "night drive"],
            default_hashtags=["#RapMusic"],
            competitor_urls=["https://youtube.com/@example"],
        )
        restored = ChannelDNAProfile.from_dict(json.loads(json.dumps(profile.to_dict(), ensure_ascii=False)))
        self.assertEqual(restored, profile)
        payload = profile.to_prompt_dict()
        self.assertEqual(payload["profile_type"], "channel_dna_v1")
        self.assertEqual(payload["channel_name"], "Música Brava — Đêm")
        self.assertNotIn("revision", payload)
        self.assertNotIn("profile_id", payload)

    def test_completed_session_maps_to_reusable_dna(self):
        session = advance_to(new_bridge(), WorkflowState.COMPLETE).session
        profile = ChannelDNAProfile.from_completed_session(session)
        self.assertEqual(profile.channel_name, session.selected_name)
        self.assertEqual(profile.source_session_id, session.session_id)
        self.assertEqual(profile.channel_description, session.package.channel_description)
        self.assertEqual(profile.thumbnail_rules, session.package.thumbnail_direction)
        self.assertEqual(profile.channel_keywords, session.package.channel_keywords)
        self.assertEqual(profile.seo_topics, session.analysis.seo_topics)


class ChannelProfileManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / "Dữ liệu Música"
        self.store = JsonChannelProfileStore(root / "data")
        self.manager = ChannelProfileManager(self.store, root / "exports")

    def test_create_update_list_archive_restore(self):
        profile = self.manager.create_profile(
            channel_name="NiteVault", target_artist="Future", target_market="United States",
            target_language="English", genre="Trap",
        )
        self.assertEqual(self.store.load_profile(profile.profile_id), profile)
        self.assertEqual(self.manager.list_profiles()[0].channel_name, "NiteVault")

        updated = self.manager.update_profile(profile.profile_id, genre="Hip-Hop / Trap", upload_time="20:00 VN")
        self.assertEqual(updated.revision, 1)
        self.assertEqual(updated.genre, "Hip-Hop / Trap")

        archived = self.manager.archive_profile(profile.profile_id)
        self.assertTrue(archived.archived)
        self.assertEqual(self.manager.list_profiles(), [])
        self.assertEqual(self.manager.list_profiles(archived=True)[0].profile_id, profile.profile_id)

        restored = self.manager.restore_profile(profile.profile_id)
        self.assertFalse(restored.archived)
        self.assertEqual(restored.revision, 3)

    def test_create_from_session_is_idempotent(self):
        session = advance_to(new_bridge(), WorkflowState.COMPLETE).session
        first = self.manager.create_from_session(session)
        second = self.manager.create_from_session(session)
        self.assertEqual(first.profile_id, second.profile_id)
        self.assertEqual(len(self.store.list_profiles()), 1)

    def test_export_is_portable_and_never_overwrites(self):
        profile = self.manager.create_profile(
            channel_name="NiteVault", target_artist="Future",
            channel_keywords=["Future style rap", "dark trap"],
        )
        first = self.manager.export_profile(profile.profile_id)
        second = self.manager.export_profile(profile.profile_id)
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file())
        payload = json.loads(first.read_text(encoding="utf-8"))
        self.assertEqual(payload["profile_type"], "channel_dna_v1")
        self.assertEqual(payload["channel_name"], "NiteVault")

    def test_corrupt_profile_is_rejected_not_repaired(self):
        profile = self.manager.create_profile(channel_name="NiteVault")
        path = self.store.directory / f"{profile.profile_id}.json"
        path.write_text("broken JSON", encoding="utf-8")
        with self.assertRaises(Exception):
            self.store.load_profile(profile.profile_id)
        self.assertEqual(path.read_text(encoding="utf-8"), "broken JSON")


class GUIChannelProfileIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        settings = Settings(prompts_dir=ROOT / "prompts", data_dir=root / "data", exports_dir=root / "exports")
        self.controller = GUIController(settings)

    def test_controller_profile_crud(self):
        created = self.controller.create_channel_profile(
            channel_name="VibeScope", target_artist="Wiz Khalifa", target_market="United States",
        )
        loaded = self.controller.load_channel_profile(created.profile_id)
        self.assertEqual(loaded, created)
        updated = self.controller.update_channel_profile(created.profile_id, notes="Adult after-work audience")
        self.assertEqual(updated.notes, "Adult after-work audience")
        self.assertEqual(len(self.controller.list_channel_profiles()), 1)

    def test_complete_project_can_be_saved_as_profile_once(self):
        bridge = new_bridge(self.controller.store, "Project")
        advance_to(bridge, WorkflowState.COMPLETE)
        self.controller.open_project(bridge.session.session_id)
        first = self.controller.create_profile_from_current_project()
        second = self.controller.create_profile_from_current_project()
        self.assertEqual(first.profile_id, second.profile_id)
        self.assertEqual(first.channel_name, bridge.session.selected_name)
