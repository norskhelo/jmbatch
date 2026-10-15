import hashlib
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from pypdf import PdfReader
from core import Settings, Task, task_cache, atomic_json
from albums import read_album, export_album, MANIFEST, album_index
from unittest.mock import patch
from diagnostics import FixtureClient
from worker import run_download
from engine import Engine
from library import Library


class AlbumTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent / "_tmp"
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name).resolve()
        self.environment = patch.dict(os.environ, JM_BATCH_HOME=str(self.root / "app-state"))
        self.environment.start()
        self.task = Task("123456", Settings(output=str(self.root / "downloads")).__dict__)
        events = []
        run_download(self.task.to_dict(), "", events.append, FixtureClient)
        self.event = events[-1]
        self.folder = Path(self.event["path"])

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def digest(self):
        return {str(p.relative_to(self.folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.folder.rglob("*") if p.is_file()}

    def test_default_download_is_ordered_images_and_restores(self):
        self.assertEqual(Settings().format, "images")
        self.assertTrue(self.folder.is_dir())
        self.assertEqual(sorted(str(p.relative_to(self.folder)).replace("\\", "/") for p in self.folder.rglob("*") if p.is_file()),
                         ["0001/00001.jpg", "0001/00002.jpg", "0001/00003.jpg", "0002/00001.jpg", "0002/00002.jpg"])
        data, images = read_album(self.folder, verify=True)
        self.assertEqual([(e["chapter"], e["page"]) for e in images], [(1,1),(1,2),(1,3),(2,1),(2,2)])
        self.assertEqual(self.event["result_bytes"], sum(Path(e["path"]).stat().st_size for e in images))
        self.assertFalse(list(self.folder.parent.glob("*.pdf")))
        self.assertFalse((task_cache(self.task.to_dict()) / "images").exists())
        restored = []
        run_download(self.task.to_dict(), "", restored.append, FixtureClient)
        self.assertEqual(restored[-1]["path"], str(self.folder))
        self.assertEqual(restored[-1]["result_bytes"], self.event["result_bytes"])

    def test_export_merged_split_and_zip_without_changing_originals(self):
        original = self.digest()
        output = self.root / "exports"
        merged = export_album(self.folder, output, "pdf", numeric=True)
        self.assertEqual(merged[0].name, "123456.pdf")
        self.assertEqual(len(PdfReader(merged[0]).pages), 5)
        split = export_album(self.folder, output, "pdf", numeric=True, split_pdf=True)
        self.assertEqual([p.name for p in split], ["123456-0001.pdf", "123456-0002.pdf"])
        self.assertEqual([len(PdfReader(p).pages) for p in split], [3,2])
        zipped = export_album(self.folder, output, "zip", numeric=True, flat=True)
        with zipfile.ZipFile(zipped[0]) as archive:
            self.assertEqual(archive.namelist(), ["0001/00001.jpg","0001/00002.jpg","0001/00003.jpg","0002/00001.jpg","0002/00002.jpg"])
            self.assertEqual(archive.read("0002/00001.jpg"), (self.folder / "0002/00001.jpg").read_bytes())
        self.assertEqual(self.digest(), original)

    def test_collision_and_cancel_leave_source_and_existing_files(self):
        output = self.root / "exports"
        output.mkdir()
        existing = output / "123456-0002.pdf"
        existing.write_bytes(b"existing user document")
        with self.assertRaises(FileExistsError):
            export_album(self.folder, output, "pdf", numeric=True, split_pdf=True)
        self.assertFalse((output / "123456-0001.pdf").exists())
        self.assertEqual(existing.read_bytes(), b"existing user document")
        with self.assertRaises(InterruptedError):
            export_album(self.folder, output, "zip", cancelled=lambda: True)
        self.assertEqual(list(output.iterdir()), [existing])
        read_album(self.folder, verify=True)

    def test_bad_manifest_is_rejected(self):
        marker = album_index(self.folder)
        data = json.loads(marker.read_text(encoding="utf-8"))
        data["entries"][0]["file"] = "../../outside.jpg"
        atomic_json(marker, data)
        with self.assertRaises(ValueError):
            read_album(self.folder)

    def test_single_chapter_folder_and_both_zip_preferences(self):
        import jmcomic
        class Single(FixtureClient):
            def get_album_detail(self, album_id):
                return jmcomic.JmAlbumDetail(album_id, "220980", "Single chapter", [("800001", "1", "Chapter one")],
                                            3, "2026-01-01", "2026-01-01", "0", "0", 0, [], [], [], [])
        task = Task("123457", Settings(output=str(self.folder.parent)).__dict__)
        events = []
        run_download(task.to_dict(), "", events.append, Single)
        folder = Path(events[-1]["path"])
        expected = ["00001.jpg", "00002.jpg", "00003.jpg"]
        self.assertEqual(sorted(p.name for p in folder.iterdir()), expected)
        for flat in (False, True):
            result = export_album(folder, self.root / f"single-{flat}", "zip", flat=flat)[0]
            with zipfile.ZipFile(result) as archive:
                self.assertEqual(archive.namelist(), expected)
                self.assertEqual(archive.read("00001.jpg"), (folder / "00001.jpg").read_bytes())
        restored = []
        run_download(task.to_dict(), "", restored.append, lambda: self.fail("Unexpected network"))
        self.assertEqual(restored[-1]["path"], str(folder))
        album_index(folder).unlink()
        self.assertEqual(len(read_album(folder, verify=True)[1]), 3)
        library = Library(self.root / "state-single")
        found, _ = library.discover(folder.parent)
        library.import_found(found)
        library.remove(library.key(folder), [], True)
        self.assertFalse(folder.exists())

    def test_portable_scan_and_legacy_manifest_export(self):
        copied = self.root / "copied" / self.folder.name
        shutil.copytree(self.folder, copied)
        data, images = read_album(copied, verify=True)
        self.assertEqual(len(images), 5)
        self.assertEqual(data["id"], "123456")
        found, _ = Library.discover(copied.parent)
        self.assertEqual(len(found), 1)
        legacy = json.loads(album_index(self.folder).read_text(encoding="utf-8"))
        legacy["version"] = 1
        atomic_json(copied / MANIFEST, legacy)
        result = export_album(copied, self.root / "legacy-export", "zip")[0]
        with zipfile.ZipFile(result) as archive:
            self.assertEqual(len(archive.namelist()), 5)
            self.assertTrue(all(name.endswith(".jpg") for name in archive.namelist()))

    def test_internal_index_detects_missing_or_changed_pages(self):
        page = self.folder / "0002/00002.jpg"
        original = page.read_bytes()
        page.unlink()
        with self.assertRaises(ValueError):
            read_album(self.folder)
        page.write_bytes(original + b"changed")
        with self.assertRaises(ValueError):
            read_album(self.folder)

    def test_library_scan_favorite_delete_and_extra_file_guard(self):
        library = Library(self.root / "state")
        found, skipped = library.discover(self.folder.parent)
        self.assertEqual(len(found), 1)
        library.import_found(found)
        key = library.key(self.folder)
        library.favorite(key)
        self.assertTrue(Library(self.root / "state").entries[key]["favorite"])
        extra = self.folder / "personal.txt"
        extra.write_text("keep me", encoding="utf-8")
        with self.assertRaises(OSError):
            library.remove(key, [], True)
        self.assertTrue(extra.exists())
        extra.unlink()
        library.remove(key, [], True)
        self.assertFalse(self.folder.exists())

    def test_old_unfinished_queue_migrates_but_completed_export_stays(self):
        old = Task("123457", Settings(output=str(self.folder.parent), format="pdf").__dict__, status="paused")
        done = Task("123458", Settings(output=str(self.folder.parent), format="zip").__dict__, status="done")
        state = self.root / "legacy"
        atomic_json(state / "queue.json", dict(settings=old.settings, tasks=[old.to_dict(), done.to_dict()]))
        loaded = Engine(state)
        self.assertEqual(loaded.settings.format, "images")
        self.assertEqual(loaded.tasks[0].settings["format"], "images")
        self.assertEqual(loaded.tasks[1].settings["format"], "zip")
