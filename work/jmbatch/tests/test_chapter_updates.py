import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Settings, Task
from chapter_updates import UpdateHistory, fetch_catalog
from engine import Engine, WorkerState
from diagnostics import FixtureClient
from worker import run_download
import threading

CAT = [dict(id=str(800001+i), number=i+1, title=f"Chapter {i+1}") for i in range(4)]


class ChapterUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.settings = Settings(output=str(self.home / "out"))
    def tearDown(self):
        self.temp.cleanup()
    def done(self, catalog, selected=None):
        return Task("123456", self.settings.__dict__, status="done", result=str(self.home / "old"),
                    chapter_options=catalog, selected_chapters=selected or catalog)
    def test_ids_reorder_deleted_and_skipped_chapters(self):
        history = UpdateHistory(self.home)
        history.record([self.done(CAT[:3], CAT[:1])])
        fresh, initialized = history.compare("123456", [CAT[2], CAT[0], CAT[3]])
        self.assertEqual(fresh, CAT[3:])
        self.assertFalse(initialized)
        self.assertEqual(UpdateHistory(self.home).compare("123456", CAT)[0], CAT[3:])
    def test_legacy_all_chapters_and_missing_history(self):
        history = UpdateHistory(self.home)
        history.record([self.done([], CAT[:2])])
        self.assertEqual(history.compare("123456", CAT), (CAT[2:], False))
        self.assertEqual(history.compare("999", CAT), ([], True))
        self.assertEqual(UpdateHistory(self.home).compare("999", CAT), ([], False))
    def test_failure_decline_and_cancellation_do_not_consume_updates(self):
        history = UpdateHistory(self.home)
        history.record([self.done(CAT[:2])])
        for status in ("queued", "paused", "failed", "cancelled"):
            task = self.done(CAT);task.status = status
            history.record([task])
            self.assertEqual(history.compare("123456", CAT)[0], CAT[2:])
        history.record([self.done(CAT)])
        self.assertEqual(UpdateHistory(self.home).compare("123456", CAT)[0], [])
    def test_queue_duplicate_failure_rollback_and_restart(self):
        engine = Engine(self.home)
        engine.tasks.append(self.done(CAT[:1]))
        other = Task("777", self.settings.__dict__, status="paused");engine.tasks.append(other)
        with patch.object(engine, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                engine.add_chapter_update("123456", CAT, CAT[1:], self.settings)
        self.assertEqual(len(engine.tasks), 2)
        task = engine.add_chapter_update("123456", CAT, CAT[1:], self.settings)
        self.assertEqual(other.status, "paused")
        self.assertTrue(engine.running)
        with self.assertRaises(ValueError):
            engine.add_chapter_update("123456", CAT, CAT[1:], self.settings)
        loaded = Engine(self.home).tasks[-1]
        self.assertEqual(loaded.status, "paused")
        self.assertEqual(loaded.selected_chapters, CAT[1:])
        self.assertNotEqual(task.key, engine.tasks[0].key)
    def test_check_only_fetches_album_and_invalid_catalog_keeps_history(self):
        client = FixtureClient()
        with patch("jmcomic.JmOption.new_jm_client", return_value=client), \
                patch.object(client, "check_photo") as details, patch.object(client, "download_by_image_detail") as images:
            catalog = fetch_catalog("123456", self.settings, "", threading.Event())
            self.assertEqual(len(catalog), 2)
            details.assert_not_called();images.assert_not_called()
        history = UpdateHistory(self.home)
        with self.assertRaises(ValueError):
            history.compare("123456", [CAT[0], CAT[0]])
        self.assertFalse(history.path.exists())
    def test_update_uses_normal_worker_and_checked_snapshot(self):
        engine = Engine(self.home)
        task = engine.add_chapter_update("123456", CAT[:2], CAT[1:2], self.settings)
        calls = []
        class Client(FixtureClient):
            def check_photo(self, photo):
                calls.append(str(photo.id));super().check_photo(photo)
        events = []
        run_download(task.to_dict(), "", events.append, Client)
        self.assertEqual(set(calls), {"800002"})
        self.assertEqual(events[-1]["total"], 2)
        self.assertTrue(Path(events[-1]["path"]).exists())
        engine._handle(WorkerState(task), dict(type="chapter_plan", chapters=CAT[1:2], catalog=CAT), 0)
        self.assertEqual(task.chapter_options, CAT[:2])  # Later server additions remain detectable.


if __name__ == "__main__":
    unittest.main()
