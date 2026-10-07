"""Release Planner core/controller tests without a Tk display."""
from datetime import date
from pathlib import Path
import csv
import tempfile
import unittest

from config import Settings
from core.release_planner import ReleasePlannerManager
from gui.controller import GUIController
from services.json_release_planner import JsonReleasePlannerStore
from tests.helpers import ROOT


class ReleasePlannerManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.manager = ReleasePlannerManager(JsonReleasePlannerStore(root / "data"), root / "exports")

    def test_channels_slots_releases_and_summary(self):
        channel = self.manager.add_channel(
            name="NiteVault", target_market="US", timezone="America/New_York",
            default_time="20:00", release_days=[0, 2, 4],
        )
        slot = self.manager.suggest_next_slot(channel.channel_id, start_date="2026-10-05")
        self.assertEqual(slot[:2], ("2026-10-05", "20:00"))
        release = self.manager.add_release(
            channel_id=channel.channel_id, song_title="NO SIGNAL",
            publish_date=slot[0], publish_time=slot[1], timezone=slot[2],
        )
        self.assertIn("THUMBNAIL", release.readiness_label)
        next_slot = self.manager.suggest_next_slot(channel.channel_id, start_date="2026-10-05")
        self.assertEqual(next_slot[0], "2026-10-07")

        rows = self.manager.list_release_rows(range_name="All")
        self.assertEqual(rows[0].channel_name, "NiteVault")
        self.assertTrue(rows[0].vietnam_time.startswith("2026-10-06"))

        updated = self.manager.update_release(
            release.release_id, audio_ready=True, thumbnail_ready=True,
            video_ready=True, seo_ready=True, status="READY",
        )
        self.assertEqual(updated.readiness_label, "READY")
        summary = self.manager.summary(today=date(2026, 10, 5))
        self.assertEqual(summary.today, 1)
        self.assertEqual(summary.ready, 1)

    def test_same_channel_same_slot_is_rejected(self):
        channel = self.manager.add_channel(name="VibeScope")
        kwargs = dict(
            channel_id=channel.channel_id, publish_date="2026-10-07",
            publish_time="20:00", timezone="Asia/Ho_Chi_Minh",
        )
        self.manager.add_release(song_title="A", **kwargs)
        with self.assertRaisesRegex(ValueError, "same date/time"):
            self.manager.add_release(song_title="B", **kwargs)

    def test_archive_channel_keeps_existing_release(self):
        channel = self.manager.add_channel(name="Música Brava")
        release = self.manager.add_release(
            channel_id=channel.channel_id, song_title="SONG",
            publish_date="2026-10-07", publish_time="20:00", timezone="Asia/Ho_Chi_Minh",
        )
        archived = self.manager.archive_channel(channel.channel_id)
        self.assertTrue(archived.archived)
        self.assertEqual(self.manager.get_release(release.release_id), release)
        with self.assertRaisesRegex(ValueError, "active planner channel"):
            self.manager.add_release(
                channel_id=channel.channel_id, song_title="NEW",
                publish_date="2026-10-08", publish_time="20:00", timezone="Asia/Ho_Chi_Minh",
            )

    def test_export_csv_utf8_and_no_overwrite(self):
        channel = self.manager.add_channel(name="Marea Urbana", target_market="México")
        self.manager.add_release(
            channel_id=channel.channel_id, song_title="BAJO TU PIEL",
            publish_date="2026-10-07", publish_time="20:00", timezone="Asia/Ho_Chi_Minh",
        )
        first = self.manager.export_csv()
        second = self.manager.export_csv()
        self.assertNotEqual(first, second)
        with first.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows[1][3], "Marea Urbana")
        self.assertEqual(rows[1][5], "México")

    def test_corrupt_store_is_not_repaired(self):
        self.manager.store.path.parent.mkdir(parents=True)
        self.manager.store.path.write_text("broken", encoding="utf-8")
        with self.assertRaises(Exception):
            self.manager.load_plan()
        self.assertEqual(self.manager.store.path.read_text(encoding="utf-8"), "broken")


class ReleasePlannerControllerTests(unittest.TestCase):
    def test_gui_controller_wrappers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            controller = GUIController(Settings(
                prompts_dir=ROOT / "prompts", data_dir=root / "data", exports_dir=root / "exports"
            ))
            channel = controller.add_release_channel(
                name="NiteVault", target_market="US", timezone="Asia/Ho_Chi_Minh",
                default_time="20:00", release_days=[0, 1, 2, 3, 4, 5, 6],
            )
            controller.add_release(
                channel_id=channel.channel_id, song_title="NO PRESSURE",
                publish_date="2026-10-07", publish_time="20:00", timezone="Asia/Ho_Chi_Minh",
            )
            snapshot = controller.release_planner_snapshot()
            self.assertEqual(len(snapshot["channels"]), 1)
            self.assertEqual(len(snapshot["releases"]), 1)
            self.assertEqual(snapshot["releases"][0].song_title, "NO PRESSURE")
