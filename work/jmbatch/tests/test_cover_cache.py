import concurrent.futures
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

from cover_cache import CoverCache
from covers import load_cover
from core import Settings, Task, task_cache
from diagnostics import FixtureClient
from download_covers import DownloadCoverLoader
from worker import run_download


class PersistentCoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.environment = patch.dict(os.environ, JM_BATCH_HOME=str(self.home))
        self.environment.start()
        self.first = self.root / "first.png"
        Image.new("RGB", (600, 800), "red").save(self.first)
        self.archive = self.root / "comic.zip"
        self.write_zip()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def write_zip(self):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.write(self.first, "00001.png")

    def test_reopen_uses_small_file_without_reopening_archive(self):
        cache = CoverCache(self.home)
        self.assertIsNotNone(cache.load(self.archive, "zip"))
        with patch("cover_cache.load_cover", side_effect=AssertionError("reopened comic")):
            for _ in range(3):
                image = CoverCache(self.home).load(self.archive, "zip")
                self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
        self.assertLess(cache.file(self.archive, "zip").stat().st_size, 16384)

    def test_source_change_rebuilds_and_missing_source_is_not_shown(self):
        cache = CoverCache(self.home)
        cache.load(self.archive, "zip")
        old = self.archive.stat().st_mtime_ns
        Image.new("RGB", (300, 400), "blue").save(self.first)
        self.write_zip()
        os.utime(self.archive, ns=(old + 1000000000, old + 1000000000))
        image = cache.load(self.archive, "zip")
        self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))
        self.archive.unlink()
        self.assertIsNone(cache.load(self.archive, "zip"))

    def test_folder_first_page_change_without_root_change(self):
        folder = self.root / "JM123456-Test-a1b2c3d4"
        first = folder / "0001/00001.jpg"
        first.parent.mkdir(parents=True)
        Image.new("RGB", (600, 800), "red").save(first)
        later = folder / "0002/00001.jpg"
        later.parent.mkdir()
        Image.new("RGB", (600, 800), "green").save(later)
        cache = CoverCache(self.home)
        cache.load(folder, "images")
        root_stamp = folder.stat().st_mtime_ns
        old = first.stat().st_mtime_ns
        Image.new("RGB", (600, 800), "blue").save(first)
        os.utime(first, ns=(old + 1000000000, old + 1000000000))
        self.assertEqual(folder.stat().st_mtime_ns, root_stamp)
        self.assertGreater(cache.load(folder, "images").getpixel((0, 0))[2], 200)
        with patch("albums.read_album", side_effect=AssertionError("rescanned folder")):
            self.assertIsNotNone(CoverCache(self.home).load(folder, "images"))

    def test_corrupt_cache_recovers_and_bad_first_page_is_not_cached(self):
        cache = CoverCache(self.home)
        cache.load(self.archive, "zip")
        cache.file(self.archive, "zip").write_bytes(b"incomplete")
        self.assertIsNotNone(cache.load(self.archive, "zip"))
        self.archive.write_bytes(b"bad zip")
        self.assertIsNone(cache.load(self.archive, "zip"))
        self.write_zip()
        self.assertIsNotNone(cache.load(self.archive, "zip"))

    def test_unwritable_cache_still_returns_preview(self):
        self.home.write_bytes(b"not a directory")
        self.assertIsNotNone(CoverCache(self.home).load(self.archive, "zip"))

    def test_concurrent_screens_extract_once(self):
        with patch("cover_cache.load_cover", wraps=load_cover) as loader:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                images = list(pool.map(lambda _: CoverCache(self.home).load(self.archive, "zip"), range(8)))
            self.assertTrue(all(image is not None for image in images))
            self.assertEqual(loader.call_count, 1)

    def test_budget_and_forget_do_not_touch_originals(self):
        cache = CoverCache(self.home)
        with patch("cover_cache.MAX_ENTRIES", 2):
            for number in range(4):
                source = self.root / f"{number}.png"
                source.write_bytes(self.first.read_bytes())
                cache.load(source, "image")
        self.assertEqual(len(list(cache.root.glob("*.cover"))), 2)
        cache.forget(source, "image")
        self.assertEqual(len(list(cache.root.glob("*.cover"))), 1)
        self.assertTrue(source.is_file())
        self.assertFalse(list(cache.root.glob("*.tmp")))

    def test_completed_downloads_seed_all_formats_before_page_cleanup(self):
        for fmt in ("images", "zip", "pdf"):
            task = Task("123456", Settings(output=str(self.root / fmt), format=fmt,
                        download_all_chapters=True, threads=1).__dict__).to_dict()
            task["_cover_home"] = str(self.home)
            def observe(event):
                if event["type"] == "done":
                    task.update(status="done", result=event["path"])
            run_download(task, "", observe, FixtureClient)
            self.assertFalse((task_cache(task) / "images").exists())
            with patch("cover_cache.load_cover", side_effect=AssertionError("reopened finished comic")):
                self.assertIsNotNone(CoverCache(self.home).load(task["result"], fmt))
                self.assertIsNotNone(DownloadCoverLoader(self.home)(task, "")[1])
