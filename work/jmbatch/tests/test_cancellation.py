import json
import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from cancellation import discard_task, remember_publication
from core import Settings, Task, task_cache
from engine import Engine
from diagnostics import FixtureClient
from worker import run_download


class CancellationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, JM_BATCH_HOME=str(self.root / 'state'))
        self.env.start()
        self.engine = Engine(self.root / 'state')
        self.engine.add(['123456', '654321'], Settings(output=str(self.root / 'out'), download_all_chapters=True))
        self.a, self.b = self.engine.tasks

    def tearDown(self):
        self.wait()
        self.engine.close()
        self.env.stop()
        self.temp.cleanup()

    def wait(self):
        deadline = time.monotonic() + 8
        while self.engine.cancelling and time.monotonic() < deadline:
            self.engine.tick()
            time.sleep(.01)
        self.assertFalse(self.engine.cancelling)

    def put(self, task, name='images/0001/00001.jpg'):
        path = task_cache(task.to_dict()) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
        return path

    def test_cancel_removes_files_record_and_allows_fresh_add(self):
        for status in ('queued', 'paused', 'failed', 'selecting', 'resetting', 'cancelled'):
            with self.subTest(status=status):
                self.a.status = status
                self.a.settings['keep_images'] = True
                self.put(self.a)
                self.put(self.a, 'chapters/data.json')
                self.put(self.a, 'export.partial.pdf')
                other = self.put(self.b)
                self.engine.cancel([self.a.key])
                self.engine.cancel([self.a.key])
                self.wait()
                self.assertNotIn(self.a, self.engine.tasks)
                self.assertFalse(task_cache(self.a.to_dict()).exists())
                self.assertTrue(other.exists())
                saved = json.loads((self.root / 'state/queue.json').read_text(encoding='utf-8'))
                self.assertNotIn(self.a.key, [t['key'] for t in saved['tasks']])
                self.assertEqual(self.engine.add(['123456'], Settings(**self.a.settings)), 1)
                self.a = self.engine.tasks[-1]

    def test_completed_and_paused_are_preserved_until_explicit_cancel(self):
        self.a.status = 'done'
        completed = self.put(self.a)
        self.b.status = 'paused'
        paused = self.put(self.b)
        self.engine.cancel([self.a.key])
        self.engine.pause()
        self.assertTrue(completed.exists() and paused.exists())
        self.assertIn(self.a, self.engine.tasks)

    def test_failure_retains_record_and_retry_only_cleans(self):
        self.put(self.a)
        with patch('cancellation._safe', side_effect=PermissionError('locked')):
            self.engine.cancel([self.a.key])
            self.wait()
        self.assertEqual(self.a.status, 'cancel_failed')
        self.assertEqual(self.engine.retry([self.a.key]), 0)
        self.engine.start()
        self.assertEqual(self.a.status, 'cancel_failed')
        self.engine.running = False
        self.engine.cancel([self.a.key])
        self.wait()
        self.assertNotIn(self.a, self.engine.tasks)

    def test_restart_continues_persisted_cancellation(self):
        self.put(self.a)
        self.a.status = 'cancelling'
        self.engine.save()
        self.engine = Engine(self.root / 'state')
        self.engine.tick()
        self.wait()
        self.assertNotIn(self.a.key, [t.key for t in self.engine.tasks])

    def test_cleanup_waits_for_worker_stop_without_blocking_caller(self):
        ready, release = threading.Event(), threading.Event()
        image = self.put(self.a)
        self.engine.active[self.a.key] = SimpleNamespace(process=None)
        def stop(state):
            ready.set()
            release.wait(5)
        with patch.object(self.engine, '_stop_process', stop):
            self.engine.cancel([self.a.key])
            self.assertTrue(ready.wait(2))
            try:
                self.assertTrue(image.exists())
                self.assertEqual(self.a.status, 'cancelling')
                self.assertEqual(self.engine.retry([self.a.key]), 0)
            finally:
                release.set()
            self.wait()
        self.assertFalse(image.exists())

    def test_three_formats_cancel_after_publication_before_done_event(self):
        for fmt in ('images', 'pdf', 'zip'):
            task = Task('123456', dict(self.a.settings, format=fmt))
            events = []
            run_download(task.to_dict(), '', events.append, FixtureClient)
            output = Path(events[-1]['path'])
            self.assertTrue(output.exists())
            self.assertEqual(discard_task(task.to_dict()).errors, 0)
            self.assertFalse(output.exists())
            self.assertFalse(task_cache(task.to_dict()).exists())

    def test_preexisting_destination_is_never_deleted(self):
        temporary = self.put(self.a, 'export.partial.zip')
        final = self.root / 'out/123456.zip'
        final.write_bytes(b'existing')
        remember_publication(self.a.to_dict(), temporary, final)
        self.assertEqual(discard_task(self.a.to_dict()).errors, 0)
        self.assertEqual(final.read_bytes(), b'existing')

    def test_retry_removes_index_after_output_was_already_deleted(self):
        from albums import album_index
        temporary = self.put(self.a, 'export.partial.zip')
        final = self.root / 'out/final.zip'
        remember_publication(self.a.to_dict(), temporary, final)
        index = album_index(final)
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_bytes(b'index')
        self.assertEqual(discard_task(self.a.to_dict()).errors, 0)
        self.assertFalse(index.exists())

    def test_cancel_rejects_link_without_following_or_removing_record(self):
        outside = self.root / 'outside'
        outside.mkdir()
        important = outside / 'keep.jpg'
        important.write_bytes(b'keep')
        cache = task_cache(self.a.to_dict())
        cache.mkdir(parents=True)
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(outside), str(cache / 'images'))
        else:
            (cache / 'images').symlink_to(outside, target_is_directory=True)
        self.engine.cancel([self.a.key])
        self.wait()
        self.assertEqual(self.a.status, 'cancel_failed')
        self.assertEqual(important.read_bytes(), b'keep')
