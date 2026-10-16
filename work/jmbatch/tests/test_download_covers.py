import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from core import Settings, Task, task_cache
from covers import load_cover
from download_covers import cover_source, DownloadCoverLoader
from diagnostics import FixtureClient
from worker import run_download


class DownloadCoverTests(unittest.TestCase):
    def setUp(self):
        folder = Path(__file__).parent / "_tmp"
        folder.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder)
        self.root = Path(self.temp.name).resolve()
        self.task = Task("123456", Settings(output=str(self.root), threads=1).__dict__, status="running").to_dict()
        self.first = task_cache(self.task) / "images/0001/00001.jpg"
        self.first.parent.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def page(self, path, color="red"):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (200, 300), color).save(path)

    def test_later_and_partial_pages_do_not_become_cover(self):
        self.page(self.first.with_name("00002.jpg"))
        self.page(self.first.with_name("00001.partial.jpg"))
        self.page(self.first.parent.parent / "0002/00001.jpg")
        self.assertIsNone(cover_source(self.task))
        self.page(self.first)
        self.assertEqual(cover_source(self.task)[:2], (str(self.first), "image"))

    def test_waiting_cover_refreshes_and_corrupt_first_is_repaired(self):
        loader = DownloadCoverLoader()
        self.assertIsNone(loader(self.task, "")[1])
        self.first.write_bytes(b"broken")
        self.assertIsNone(loader(self.task, "")[1])
        self.page(self.first)
        self.assertIsNotNone(loader(self.task, "")[1])
        self.first.unlink()
        self.assertIsNone(loader(self.task, "")[1])

    def test_pause_restart_and_retry_use_same_first_page(self):
        self.page(self.first)
        for state in ("running", "paused", "resetting", "failed", "cancelled", "queued"):
            self.task["status"] = state
            self.assertIsNotNone(DownloadCoverLoader()(self.task, "")[1])

    def test_unchanged_page_is_decoded_once_and_cache_is_bounded(self):
        self.page(self.first)
        loader = DownloadCoverLoader()
        with patch("download_covers.load_cover", wraps=load_cover) as decode:
            for _ in range(3):
                loader(self.task, "")
            self.assertEqual(decode.call_count, 1)
        for n in range(70):
            other = dict(self.task, key=f"{n:032x}")
            loader(other, "")
        self.assertLessEqual(len(loader.cache), 64)

    def test_running_cover_precedes_completion_for_every_format(self):
        for fmt in ("images", "zip", "pdf"):
            task = Task("123456", Settings(output=str(self.root / fmt), format=fmt, threads=1).__dict__, status="running").to_dict()
            loader = DownloadCoverLoader()
            seen = []
            def observe(event):
                if event["type"] == "progress" and event["done"] == 1:
                    self.assertLess(event["done"], event["total"])
                    self.assertIsNotNone(loader(task, "")[1])
                    seen.append(True)
                if event["type"] == "done":
                    task.update(status="done", result=event["path"])
            run_download(task, "", observe, FixtureClient)
            self.assertTrue(seen)
            self.assertFalse((task_cache(task) / "images").exists())
            self.assertEqual(cover_source(task)[1], fmt)
            self.assertIsNotNone(loader(task, "")[1])

    def test_bad_key_and_missing_finished_file_stay_placeholder(self):
        loader = DownloadCoverLoader()
        self.assertIsNone(loader(dict(self.task, key="../escape"), "")[1])
        self.task.update(status="done", result=str(self.root / "missing.zip"))
        self.assertIsNone(loader(self.task, "")[1])

    def test_concurrent_tasks_do_not_share_covers(self):
        self.page(self.first, "red")
        other = Task("123457", self.task["settings"], status="running").to_dict()
        self.page(task_cache(other) / "images/0001/00001.jpg", "blue")
        loader = DownloadCoverLoader()
        red, blue = loader(self.task, "")[1], loader(other, "")[1]
        self.assertGreater(red.getpixel((0, 0))[0], 200)
        self.assertGreater(blue.getpixel((0, 0))[2], 200)
