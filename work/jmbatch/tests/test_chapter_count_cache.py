import tempfile
import unittest
import zipfile
import threading
import time
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from core import Settings, Task
from library import Library


class ChapterCountCacheTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.library=Library(self.root/'state')

    def tearDown(self):
        self.temp.cleanup()

    def task(self, fmt='zip'):
        task=Task('123',Settings(output=str(self.root),format=fmt).__dict__)
        task.status='done';task.title='saved';task.result=str(self.root/('123.'+fmt))
        task.selected_chapters=[dict(id='101',number=1,title='one'),dict(id='109',number=9,title='nine')]
        return task

    def test_completion_persists_selected_count_without_opening_output(self):
        for fmt in ('images','zip','pdf'):
            task=self.task(fmt);key=self.library.key(task.result)
            with patch('reader.ReaderSource',side_effect=AssertionError('unnecessary file read')):
                self.library.sync([task])
            self.assertEqual(self.library.entries[key]['chapter_count'],2)
            folder=self.library.create_collection(fmt)
            self.library.move_to_collection([key],folder);self.library.favorite(key)
            restored=Library(self.root/'state');restored.sync([])
            self.assertEqual(restored.entries[key]['chapter_count'],2)
            self.assertTrue(restored.entries[key]['favorite'])
            self.assertEqual(restored.entries[key]['collection'],folder)

    def test_legacy_import_backfill_survives_restart_and_missing_file(self):
        source=self.root/'123-old.zip'
        with zipfile.ZipFile(source,'w') as archive:
            for chapter in (1,4,9):archive.writestr(f'{chapter:04d}/00001.jpg',b'page')
        found,_=Library.discover(self.root);self.library.import_found(found)
        key=self.library.key(source)
        counts=self.library.read_chapter_counts(list(self.library.entries.items()))
        self.assertEqual(counts,{key:3});self.assertTrue(self.library.save_chapter_counts(counts))
        source.unlink();restored=Library(self.root/'state')
        self.assertEqual(restored.entries[key]['chapter_count'],3)
        self.assertFalse(restored.save_chapter_counts(counts))

    def test_failure_keeps_unknown_and_save_failure_rolls_back(self):
        task=self.task();task.selected_chapters=[];self.library.sync([task])
        key=self.library.key(task.result)
        self.assertEqual(self.library.read_chapter_counts(list(self.library.entries.items())),{})
        with patch.object(self.library,'save',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.library.save_chapter_counts({key:3})
        self.assertNotIn('chapter_count',self.library.entries[key])
        self.assertTrue(self.library.save_chapter_counts({key:3}))

    def test_late_scan_does_not_restore_removed_entry_or_override_new_count(self):
        task=self.task();self.library.sync([task]);key=self.library.key(task.result)
        self.assertFalse(self.library.save_chapter_counts({key:99,'removed':3}))
        self.assertEqual(self.library.entries[key]['chapter_count'],2)
        self.assertNotIn('removed',self.library.entries)

    def test_legacy_scan_does_not_block_menu_and_refreshes_when_ready(self):
        import tkinter as tk
        from library_ui import LibraryWindow
        from ui_library import sort_menu
        for name,chapters in [('123-Z one',1),('124-A many',3)]:
            with zipfile.ZipFile(self.root/(name+'.zip'),'w') as archive:
                for chapter in range(1,chapters+1):archive.writestr(f'{chapter:04d}/00001.jpg',b'page')
        found,_=Library.discover(self.root);self.library.import_found(found)
        gate=threading.Event();entered=threading.Event();original=self.library.read_chapter_counts
        def scan(items):entered.set();gate.wait(5);return original(items)
        root=tk.Tk();errors=[];root.report_callback_exception=lambda *args:errors.append(args)
        app=SimpleNamespace(root=root,engine=SimpleNamespace(library=self.library,tasks=[]),read_comic=Mock())
        try:
            with patch.object(self.library,'read_chapter_counts',side_effect=scan), patch('cover_cache.CoverCache.load',return_value=None):
                view=LibraryWindow(app);root.update();self.assertTrue(entered.wait(2))
                with patch('ui_library.tk.Menu') as menu:
                    sort_menu(view);menu.return_value.add_command.call_args_list[3].kwargs['command']()
                self.assertFalse(view.busy);self.assertTrue(view.chapter_scan_running)
                gate.set();deadline=time.monotonic()+5
                while view.chapter_scan_running and time.monotonic()<deadline:root.update();time.sleep(.01)
                self.assertFalse(view.chapter_scan_running)
                self.assertEqual([self.library.entries[k]['chapter_count'] for k in view.tree.get_children()],[1,3])
                self.assertEqual(sorted(e['chapter_count'] for e in Library(self.root/'state').entries.values()),[1,3])
                with patch('reader.ReaderSource',side_effect=AssertionError('sort rescanned')):view.render()
                self.assertFalse(errors,errors)
        finally:gate.set();root.destroy()
