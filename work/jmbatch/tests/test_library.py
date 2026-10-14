import json
import tempfile
import unittest
import threading
from pathlib import Path
from unittest.mock import patch

from core import Settings, Task
from engine import Engine
from library import Library


class LibraryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent / "_tmp"
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / "exports"
        self.output.mkdir()
        self.file = self.output / "123456_title.zip"
        self.file.write_bytes(b"fixture export")
        self.task = Task("123456", dict(Settings(output=str(self.output), format="zip").__dict__))
        self.task.status, self.task.title, self.task.result = "done", "Test comic", str(self.file)
        self.library = Library(self.root / "state")
        self.library.sync([self.task])
        self.key = self.library.key(self.file)

    def tearDown(self):
        self.temp.cleanup()

    def test_favorites_persist_without_queue_and_filter(self):
        self.library.favorite(self.key)
        restored = Library(self.root / "state")
        restored.sync([])
        self.assertEqual(len(restored.select("123456", True)), 1)
        self.assertEqual(len(restored.select("COMIC", True)), 1)
        self.assertFalse(restored.select("unrelated"))
        restored.sync([self.task, self.task])
        self.assertEqual(len(restored.entries), 1)
        self.assertTrue(restored.entries[self.key]["favorite"])
        restored.favorite(self.key)
        self.assertFalse(restored.select(favorites=True))

    def test_delete_only_target_and_allow_redownload(self):
        sibling = self.output / "another.zip"
        sibling.write_bytes(b"keep")
        cache = self.output / "cache"
        cache.mkdir()
        self.library.remove(self.key, [self.task], True)
        self.assertFalse(self.file.exists())
        self.assertTrue(sibling.is_file())
        self.assertTrue(cache.is_dir())
        self.assertEqual(self.task.status, "cancelled")
        self.assertEqual(self.task.result, "")
        self.library.sync([self.task])
        self.assertFalse(self.library.entries)
        self.assertFalse(Library(self.root / "state").entries)

    def test_forget_preserves_file_and_does_not_reimport(self):
        self.library.remove(self.key, [self.task], False)
        self.assertTrue(self.file.exists())
        self.library.sync([self.task])
        self.assertFalse(self.library.entries)

    def test_missing_file_explicit_and_record_retained(self):
        self.file.unlink()
        with self.assertRaisesRegex(FileNotFoundError, "文件不存在"):
            self.library.remove(self.key, [self.task], True)
        self.assertIn(self.key, self.library.entries)
        self.library.remove(self.key, [self.task], False)

    def test_directory_and_outside_root_never_deleted(self):
        self.file.unlink()
        self.file.mkdir()
        with self.assertRaises(OSError):
            self.library.remove(self.key, [self.task], True)
        self.assertTrue(self.file.is_dir())
        self.file.rmdir()
        self.file.write_bytes(b"keep")
        self.library.entries[self.key]["root"] = str(self.root / "other")
        with self.assertRaisesRegex(OSError, "离开原保存目录"):
            self.library.remove(self.key, [self.task], True)
        self.assertTrue(self.file.is_file())

    def test_active_same_book_protects_export(self):
        active = Task("123456", self.task.settings.copy())
        active.status = "running"
        with self.assertRaisesRegex(OSError, "仍有"):
            self.library.remove(self.key, [self.task, active], True)
        self.assertTrue(self.file.is_file())

    def test_permissions_failure_retains_record(self):
        with patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                self.library.remove(self.key, [self.task], True)
        self.assertEqual(self.task.result, str(self.file))
        self.assertIn(self.key, self.library.entries)

    def test_corrupt_catalog_not_overwritten(self):
        self.library.path.write_text("broken", encoding="utf-8")
        damaged = Library(self.root / "state")
        with self.assertRaises(OSError):
            damaged.sync([self.task])
        self.assertEqual(damaged.path.read_text(), "broken")

    def test_write_failure_rolls_back_favorite_and_import(self):
        with patch("library.atomic_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.library.favorite(self.key)
            self.assertFalse(self.library.entries[self.key]["favorite"])
            self.task.title = "Updated title"
            with self.assertRaises(OSError):
                self.library.sync([self.task])
            self.assertEqual(self.library.entries[self.key]["title"], "Test comic")
        self.library.sync([self.task])
        self.assertEqual(Library(self.root / "state").entries[self.key]["title"], "Updated title")

    def test_old_queue_migrates_and_clearing_queue_keeps_catalog(self):
        home = self.root / "migration"
        engine = Engine(home)
        engine.tasks = [self.task]
        engine.save()
        restored = Engine(home)
        self.assertIn(self.key, restored.library.entries)
        restored.library.favorite(self.key)
        restored.tasks = []
        restored.save()
        again = Engine(home)
        self.assertFalse(again.tasks)
        self.assertTrue(again.library.entries[self.key]["favorite"])

    def test_scan_recovers_cleared_history_and_preserves_favorites(self):
        self.library.favorite(self.key)
        (self.output / "JM999999_old comic.PDF").write_bytes(b"older export")
        (self.output / "book without id.zip").write_bytes(b"archive")
        found, skipped = self.library.discover(self.output)
        self.assertEqual(skipped, 0)
        self.assertEqual(self.library.import_found(found), 2)
        self.assertEqual(self.library.import_found(found), 0)
        restored = Library(self.root / "state")
        self.assertTrue(restored.entries[self.key]["favorite"])
        self.assertEqual(restored.entries[self.key]["title"], "Test comic")
        self.assertEqual(len(restored.select("999999")), 1)
        self.assertEqual(restored.select("without id")[0][1]["id"], "")

    def test_scan_skips_partials_empty_folders_and_subdirectories(self):
        (self.output / "123456.pdf.partial").write_bytes(b"partial")
        (self.output / "empty.pdf").touch()
        (self.output / "folder.zip").mkdir()
        sub = self.output / "sub"
        sub.mkdir()
        (sub / "999999.zip").write_bytes(b"not scanned")
        found, skipped = self.library.discover(self.output)
        self.assertEqual(len(found), 1)
        self.assertEqual(skipped, 2)
        with self.assertRaises(OSError):
            self.library.discover("")
        with self.assertRaises(OSError):
            self.library.discover(self.root / "missing")

    def test_cancelled_scan_does_not_change_catalog(self):
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(InterruptedError):
            self.library.discover(self.output, cancelled)
        self.assertEqual(len(self.library.entries), 1)

    def test_batch_favorites_are_explicit_and_atomic(self):
        other = self.output / "999999.zip"
        other.write_bytes(b"archive")
        self.library.import_found(self.library.discover(self.output)[0])
        keys = list(self.library.entries)
        self.library.set_favorites(keys, True)
        self.library.set_favorites(keys, True)
        self.assertEqual(len(self.library.select(favorites=True)), 2)
        with patch("library.atomic_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.library.set_favorites(keys, False)
        self.assertEqual(len(self.library.select(favorites=True)), 2)
        self.library.set_favorites(keys, False)
        self.assertFalse(Library(self.root / "state").select(favorites=True))

    def test_batch_delete_continues_after_failure(self):
        other = self.output / "999999.zip"
        other.write_bytes(b"archive")
        self.library.import_found(self.library.discover(self.output)[0])
        self.file.unlink()
        done, errors, remaining = self.library.remove_many(list(self.library.entries), [self.task], True)
        self.assertEqual((len(done), len(errors), remaining), (1, 1, 0))
        self.assertFalse(other.exists())
        self.assertIn(self.key, self.library.entries)

    def test_batch_cancel_retains_unprocessed_files(self):
        other = self.output / "999999.zip"
        other.write_bytes(b"archive")
        self.library.import_found(self.library.discover(self.output)[0])
        cancelled = threading.Event()
        done, errors, remaining = self.library.remove_many(list(self.library.entries), [], True, cancelled, lambda *_: cancelled.set())
        self.assertEqual((len(done), len(errors), remaining), (1, 0, 1))
        self.assertTrue(other.exists())

    def test_batch_forget_files_can_be_scanned_again(self):
        done, errors, remaining = self.library.remove_many([self.key, self.key], [self.task], False)
        self.assertEqual((len(done), len(errors), remaining), (1, 0, 0))
        self.assertTrue(self.file.exists())
        self.assertEqual(self.library.import_found(self.library.discover(self.output)[0]), 1)
