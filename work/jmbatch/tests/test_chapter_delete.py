import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from albums import read_album, album_index, MANIFEST
from chapter_delete import inspect, delete_chapters
from core import Task, Settings
from engine import Engine
from reader import ReaderSource, ReaderState
from library import Library


class ChapterDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "state"
        self.home.mkdir()
        self.environment = patch.dict(os.environ, JM_BATCH_HOME=str(self.home))
        self.environment.start()
        self.output = self.root / "books"
        self.output.mkdir()
        self.engine = Engine(self.home)
        self.engine.settings.output = str(self.output)

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def fixture(self, fmt="images", legacy=False):
        path = self.output / ("JM123-test-12345678" + (".zip" if fmt == "zip" else ""))
        self.payloads = {}
        for c in range(1, 4):
            for p in range(1, 3):
                import io
                from PIL import Image
                out = io.BytesIO()
                Image.new("RGB", (5, 8), (c * 70, p * 70, 10)).save(out, "JPEG")
                self.payloads[f"{c:04d}/{p:05d}.jpg"] = out.getvalue()
        if fmt == "images":
            path.mkdir()
            for name, data in self.payloads.items():
                target = path / name
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(data)
            if legacy:
                (path / MANIFEST).write_text(json.dumps(dict(version=1, id="123", title="test", entries=[dict(chapter=int(n[:4]), page=int(Path(n).stem), file=n, size=len(d)) for n,d in self.payloads.items()])))
        else:
            with zipfile.ZipFile(path, "w") as archive:
                for name, data in self.payloads.items():
                    archive.writestr(name, data)
                archive.writestr("notes.txt", b"keep metadata")
        task = Task("123", Settings(output=str(self.output), format=fmt).__dict__)
        task.status, task.title, task.result = "done", "test", str(path)
        self.engine.tasks.append(task)
        self.engine.library.sync([task])
        self.engine.save()
        key = self.engine.library.key(path)
        self.engine.library.favorite(key)
        ReaderState(self.home).put(key, 4, "paged", [0, 2, 4, 5])
        return path, key

    def delete(self, key, chosen, **kw):
        return delete_chapters(self.engine, key, chosen, inspect(self.engine.library, key), **kw)

    def test_folder_middle_and_repeated_delete_preserve_bytes_history_and_queue(self):
        source, key = self.fixture()
        new_key, _ = self.delete(key, [2])
        target = Path(self.engine.library.entries[new_key]["path"])
        self.assertFalse(source.exists())
        self.assertEqual((target / "0002/00001.jpg").read_bytes(), self.payloads["0003/00001.jpg"])
        self.assertTrue(self.engine.library.entries[new_key]["favorite"])
        self.assertEqual(ReaderState(self.home).get(new_key, 4), dict(page=2, mode="paged", bookmarks=[0, 2, 3]))
        self.assertEqual(Engine(self.home).tasks[0].result, str(target))
        self.assertEqual(len(Library(self.home).entries), 1)
        next_key, _ = self.delete(new_key, [1])
        last = Path(self.engine.library.entries[next_key]["path"])
        self.assertEqual(sorted(p.name for p in last.iterdir()), ["00001.jpg", "00002.jpg"])
        album_index(last).unlink()
        self.assertEqual(len(read_album(last)[1]), 2)  # portable recovery after losing private index
        self.assertEqual(ReaderState(self.home).get(next_key, 2)["bookmarks"], [0, 1])

    def test_legacy_folder_multi_select_and_deleted_reading_page(self):
        source, key = self.fixture(legacy=True)
        ReaderState(self.home).put(key, 2, "scroll", [0, 2, 4])
        new_key, _ = self.delete(key, [1, 2])
        self.assertFalse(source.exists())
        state = ReaderState(self.home).get(new_key, 2)
        self.assertEqual(state, dict(page=0, mode="scroll", bookmarks=[0]))

    def test_zip_preserves_raw_images_and_non_page_entries(self):
        source, key = self.fixture("zip")
        new_key, _ = self.delete(key, [1, 3])
        with zipfile.ZipFile(self.engine.library.entries[new_key]["path"]) as archive:
            self.assertEqual(set(archive.namelist()), {"0002/00001.jpg", "0002/00002.jpg", "notes.txt"})
            self.assertEqual(archive.read("0002/00002.jpg"), self.payloads["0002/00002.jpg"])
            self.assertEqual(archive.read("notes.txt"), b"keep metadata")
        with_source = ReaderSource(self.engine.library.entries[new_key]["path"])
        self.assertEqual([p["chapter"] for p in with_source.pages], [1, 1])
        with_source.close()
        self.assertFalse(source.exists())

    def test_cancel_during_copy_keeps_original_and_cleans_staging(self):
        source, key = self.fixture()
        cancel = [False]
        with self.assertRaises(InterruptedError):
            self.delete(key, [2], cancelled=lambda: cancel[0], progress=lambda text: cancel.__setitem__(0, True) if "1/4" in text else None)
        self.assertEqual(len(read_album(source)[1]), 6)
        self.assertEqual(list(self.output.iterdir()), [source])
        self.assertIn(key, self.engine.library.entries)
        self.assertFalse(self.engine.cleaning)

    def test_record_save_failure_rolls_back_without_deleting_original(self):
        source, key = self.fixture()
        original = self.engine.save
        calls = [0]
        def fail_once():
            calls[0] += 1
            if calls[0] == 1:
                raise OSError("disk full")
            original()
        with patch.object(self.engine, "save", side_effect=fail_once), self.assertRaisesRegex(OSError, "disk full"):
            self.delete(key, [2])
        self.assertEqual(list(self.output.iterdir()), [source])
        self.assertEqual(Engine(self.home).tasks[0].result, str(source))
        self.assertEqual(set(Library(self.home).entries), {key})

    def test_cleanup_failure_keeps_valid_new_book_and_reports_original(self):
        source, key = self.fixture("zip")
        original = Path.unlink
        def fail_old(path, *args, **kw):
            if path == source:
                raise PermissionError("busy")
            return original(path, *args, **kw)
        with patch.object(Path, "unlink", fail_old):
            new_key, text = self.delete(key, [2])
        self.assertIn("清理未完成", text)
        self.assertTrue(source.exists())
        self.assertNotEqual(key, new_key)
        self.assertEqual(len(inspect(self.engine.library, new_key)["pages"]), 4)

    def test_invalid_all_stale_extra_file_and_running_are_rejected(self):
        source, key = self.fixture()
        for selected in ([], [9], [1, 2, 3]):
            with self.assertRaises(ValueError):
                self.delete(key, selected)
        plan = inspect(self.engine.library, key)
        page = source / "0002/00001.jpg"
        page.write_bytes(page.read_bytes()+b"changed")
        with self.assertRaisesRegex(OSError, "变化"):
            delete_chapters(self.engine, key, [2], plan)
        (source / "personal.txt").write_text("keep")
        with self.assertRaisesRegex(OSError, "额外"):
            inspect(self.engine.library, key)
        (source / "personal.txt").unlink()
        self.engine.running = True
        with self.assertRaisesRegex(OSError, "暂停"):
            self.delete(key, [2])
        self.assertTrue(source.exists())
        self.engine.running = False
        self.engine.library.entries[key]["id"] = "../../outside"
        with self.assertRaisesRegex(ValueError, "编号无效"):
            self.delete(key, [2])

    def test_library_button_selection_confirmation_and_refresh(self):
        import time
        import tkinter as tk
        from types import SimpleNamespace
        from unittest.mock import Mock
        from library_ui import LibraryWindow
        source, key = self.fixture()
        root = tk.Tk()
        app = SimpleNamespace(root=root, home=self.home, engine=self.engine, render=Mock(), readers={})
        ui = LibraryWindow(app)
        def wait(predicate):
            end = time.monotonic() + 8
            while not predicate() and time.monotonic() < end:
                root.update()
                time.sleep(.01)
            root.update()
            self.assertTrue(predicate())
        try:
            ui.enter_batch()
            ui.tree.selection_set(key)
            root.update()
            ui.details()
            self.assertEqual(str(ui.action_buttons["chapters"]["state"]), "normal")
            ui.action_buttons["chapters"].invoke()
            wait(lambda: not ui.busy)
            dialog = next(child for child in ui.window.winfo_children() if isinstance(child, tk.Toplevel))
            box = next(child for child in dialog.winfo_children() if isinstance(child, tk.Listbox))
            self.assertEqual(box.size(), 3)
            box.selection_set(1)
            button = next(button for child in dialog.winfo_children() for button in child.winfo_children() if button.winfo_class() == "TButton" and button.cget("text") == "删除所选章节")
            with patch.object(ui.messagebox, "askyesno", return_value=True), patch.object(ui.messagebox, "showerror") as error:
                button.invoke()
                wait(lambda: not ui.busy)
                error.assert_not_called()
            self.assertFalse(source.exists())
            self.assertIn("删除 1 章", ui.status.get())
            self.assertEqual(len(ui.tree.get_children()), 1)
            self.assertEqual(len(ui.tree.selection()), 1)
        finally:
            root.destroy()
