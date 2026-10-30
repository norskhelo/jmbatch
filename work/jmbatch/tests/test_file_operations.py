import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from core import Settings, Task
from engine import WorkerState
from library import Library
from batch_export import export_many
from test_chapter_delete import ChapterDeletionTests


class FileOperationTests(unittest.TestCase):
    setUp = ChapterDeletionTests.setUp
    tearDown = ChapterDeletionTests.tearDown
    fixture = ChapterDeletionTests.fixture
    delete = ChapterDeletionTests.delete

    def other_task(self, identifier="999", status="running"):
        task = Task(identifier, Settings(output=str(self.output), format="zip").__dict__)
        task.status = status
        self.engine.tasks.append(task)
        self.engine.running = True
        return task

    def test_delete_and_export_while_other_download_finishes(self):
        source, key = self.fixture("zip")
        other = self.other_task()
        finished = self.output / "JM999-complete.zip"
        finished.write_bytes(b"completed download")
        def complete():
            with self.engine.state_lock:
                other.result, other.status = str(finished), "done"
                self.engine.library.sync(self.engine.tasks)
                self.engine.save()
        with self.engine.file_operation([key]):
            thread = threading.Thread(target=complete)
            thread.start(); thread.join(5)
            self.assertFalse(thread.is_alive(), "a file operation must not hold the queue lock")
            exported = export_many(self.engine.library, [key], self.output, "zip", False, False)
            self.assertFalse(exported.errors)
            self.engine.library.remove(key, self.engine.tasks, True)
            self.engine.save()
        self.assertFalse(source.exists())
        saved = Library(self.home).entries
        self.assertNotIn(key, saved)
        self.assertIn(self.engine.library.key(finished), saved)
        self.assertTrue(self.engine.running)

    def test_chapter_delete_does_not_stop_unrelated_queue(self):
        source, key = self.fixture("zip")
        other = self.other_task()
        new_key, _ = self.delete(key, [2])
        self.assertFalse(source.exists())
        self.assertIn(new_key, Library(self.home).entries)
        self.assertEqual(other.status, "running")
        self.assertTrue(self.engine.running)
        self.assertIsNone(self.engine.file_targets)

    def test_only_target_downloads_are_blocked_until_operation_exits(self):
        _, key = self.fixture("zip")
        target = self.other_task("123", "paused")
        other = self.other_task("999", "queued")
        launched = []
        def launch(task, now):
            launched.append(task.key); task.status = "running"
        with self.engine.file_operation([key]):
            self.engine.start()
            with patch.object(self.engine, "_launch", side_effect=launch):
                self.engine.tick()
            self.assertEqual(launched, [other.key])
            self.assertEqual(target.status, "queued")
            self.engine.cancel([target.key])
            self.assertEqual(target.status, "queued")
        with patch.object(self.engine, "_launch", side_effect=launch):
            self.engine.tick()
        self.assertEqual(launched, [other.key, target.key])

    def test_conflicts_include_stopping_workers_and_cancel_cleanup(self):
        _, key = self.fixture("zip")
        task = self.other_task("123")
        for status in ("queued", "running", "resetting", "cancelling", "cancel_failed"):
            task.status = status
            with self.assertRaisesRegex(OSError, "所选漫画"):
                with self.engine.file_operation([key]): pass
        task.status = "paused"
        self.engine.active[task.key] = WorkerState(task)
        with self.assertRaises(OSError):
            with self.engine.file_operation([key]): pass
        self.engine.active.clear()
        task.settings["output"] = str(self.root / "other-folder")
        task.status = "running"
        with self.engine.file_operation([key]): pass
        task.result = self.engine.library.entries[key]["path"]
        with self.assertRaises(OSError):
            with self.engine.file_operation([key]): pass

    def test_failure_releases_reservation_and_keeps_source(self):
        source, key = self.fixture("zip")
        with self.assertRaisesRegex(RuntimeError, "failed"):
            with self.engine.file_operation([key]):
                raise RuntimeError("failed")
        self.assertIsNone(self.engine.file_targets)
        self.assertTrue(source.exists())
        with self.engine.file_operation([key]):
            with self.engine.file_operation([key]): pass
            self.assertIsNotNone(self.engine.file_targets)
        self.assertIsNone(self.engine.file_targets)

    def test_remove_record_during_download_keeps_files(self):
        source, key = self.fixture("zip")
        other = self.other_task()
        with self.engine.file_operation([key]):
            self.engine.library.remove(key, self.engine.tasks)
            self.engine.save()
        self.engine.library.sync(self.engine.tasks)
        self.assertTrue(source.exists())
        self.assertNotIn(key, Library(self.home).entries)
        self.assertEqual(other.status, "running")

    def test_library_export_and_delete_buttons_during_download(self):
        import time
        import tkinter as tk
        from types import SimpleNamespace
        from unittest.mock import Mock
        from library_ui import LibraryWindow
        from export_ui import show_export
        from ui_library import delete_selection
        source, key = self.fixture("zip")
        other = self.other_task()
        root = tk.Tk()
        ui = LibraryWindow(SimpleNamespace(root=root, home=self.home, engine=self.engine,
                                          render=Mock(), readers={}))
        def wait():
            end = time.monotonic() + 10
            while ui.busy and time.monotonic() < end:
                root.update(); time.sleep(.01)
            root.update()
            self.assertFalse(ui.busy)
        def widgets(widget):
            yield widget
            for child in widget.winfo_children(): yield from widgets(child)
        def confirm(dialog):
            next(w for w in widgets(dialog) if w.winfo_class() == "TButton" and w.cget("text") == "确认").invoke()
            wait()
        try:
            with patch.object(ui.messagebox, "showerror") as errors, patch.object(ui.messagebox, "showwarning") as warnings:
                dialog = show_export(ui, [key]); root.update(); confirm(dialog)
                errors.assert_not_called(); warnings.assert_not_called()
                self.assertEqual(len(self.engine.library.entries), 2)
                ui.enter_batch(); ui.tree.selection_set(key); root.update()
                delete_selection(ui); wait()
                dialog = next(w for w in ui.window.winfo_children() if isinstance(w, tk.Toplevel))
                confirm(dialog)
                errors.assert_not_called()
            self.assertFalse(source.exists())
            self.assertEqual(other.status, "running")
            self.assertTrue(self.engine.running)
            queue = __import__('json').loads((self.home / 'queue.json').read_text('utf-8'))
            self.assertFalse(queue['tasks'][0]['result'])
        finally:
            root.destroy()

