import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from core import Settings
from diagnostics import fixture_worker
from engine import Engine


def gated_worker(task, cookie, channel):
    root = Path(task['settings']['output'])
    root.mkdir(parents=True, exist_ok=True)
    key = task['key']
    channel.put({'type': 'phase', 'phase': 'download', 'total': 5, 'message': 'offline gate'})
    (root / ('ready-' + key)).touch()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if (root / ('crash-' + key)).exists():
            os._exit(7)
        if (root / ('fail-' + key)).exists():
            channel.put({'type': 'error', 'error': 'offline task failure'})
            return
        if (root / ('release-' + key)).exists():
            fixture_worker(task, cookie, channel)
            return
        time.sleep(.02)
    channel.put({'type': 'error', 'error': 'offline gate timed out'})


class ConcurrentQueueTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parent / '_tmp'
        directory.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root / 'state', worker_target=gated_worker)
        self.settings = Settings(output=str(self.root / 'out'), concurrent_tasks=2, auto_reset=False, download_all_chapters=True)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def until(self, predicate, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.engine.tick()
            if predicate():
                return
            time.sleep(.03)
        self.fail([t.to_dict() for t in self.engine.tasks])

    def marker(self, kind, task):
        path = self.root / 'out' / (kind + '-' + task.key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def start(self, count=3):
        self.engine.add([str(123456 + i) for i in range(count)], self.settings)
        self.engine.start()
        self.engine.tick()
        return self.engine.tasks

    def ready(self, *tasks):
        self.until(lambda: all(self.marker('ready', t).exists() and self.engine.active[t.key].phase == 'download' for t in tasks))

    def test_default_limits_and_old_queue_migration(self):
        self.assertEqual(Settings().concurrent_tasks, 2)
        for value in (0, 5, 1.5, '2'):
            with self.assertRaises(ValueError):
                Settings(concurrent_tasks=value).validate()
        self.start(2)
        self.engine.pause()
        path = self.root / 'state' / 'queue.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['settings'].pop('concurrent_tasks')
        for task in data['tasks']:
            task['settings'].pop('concurrent_tasks')
            task['status'] = 'running'
        path.write_text(json.dumps(data), encoding='utf-8')
        restored = Engine(path.parent)
        self.assertEqual(restored.settings.concurrent_tasks, 2)
        self.assertEqual([t.status for t in restored.tasks], ['paused', 'paused'])

    def test_overlap_capacity_dynamic_limits_and_cancel_isolation(self):
        a, b, c = self.start()
        self.ready(a, b)
        self.assertEqual(c.status, 'queued')
        processes = {k: s.process.pid for k, s in self.engine.active.items()}
        self.engine.settings.concurrent_tasks = 1
        self.engine.tick()
        self.assertEqual(processes, {k: s.process.pid for k, s in self.engine.active.items()})
        self.engine.cancel([a.key])
        self.engine.tick()
        self.assertEqual(a.status, 'cancelled')
        self.assertEqual(c.status, 'queued')
        self.assertEqual(self.engine.active[b.key].process.pid, processes[b.key])
        self.engine.settings.concurrent_tasks = 3
        self.engine.add(['123459'], self.engine.settings)
        d = self.engine.tasks[-1]
        self.ready(b, c, d)
        self.assertEqual(len(self.engine.active), 3)
        self.engine.pause()
        self.assertFalse(self.engine.active)
        self.assertEqual([t.status for t in (b, c, d)], ['paused'] * 3)

    def test_completions_backfill_independent_artifacts_and_restore(self):
        a, b, c = self.start()
        self.ready(a, b)
        self.marker('release', b).touch()
        self.until(lambda: b.status == 'done' and c.key in self.engine.active)
        self.assertEqual(a.status, 'running')
        self.marker('release', a).touch()
        self.marker('release', c).touch()
        self.until(lambda: not self.engine.running)
        self.assertEqual([t.status for t in (a, b, c)], ['done'] * 3)
        self.assertEqual(len({t.result for t in (a, b, c)}), 3)
        for task in (a, b, c):
            from albums import read_album
            self.assertFalse((Path(task.result) / '.jmbatch-album.json').exists())
            self.assertEqual(len(read_album(task.result)[1]), 5)
            self.assertEqual(task.done, 5)
        recovered = Engine(self.root / 'state')
        self.assertEqual([t.result for t in recovered.tasks], [t.result for t in self.engine.tasks])

    def test_task_failure_and_process_crash_do_not_stop_others(self):
        a, b, c, d = self.start(4)
        self.ready(a, b)
        pid = self.engine.active[b.key].process.pid
        self.marker('fail', a).touch()
        self.until(lambda: a.status == 'failed' and c.key in self.engine.active)
        self.ready(c)
        self.marker('crash', c).touch()
        self.until(lambda: c.status == 'failed' and d.key in self.engine.active)
        self.assertIn('退出码 7', c.error)
        self.assertEqual(self.engine.active[b.key].process.pid, pid)
        self.assertTrue(self.engine.running)

    def test_reset_budget_and_cancel_during_backoff_are_per_task(self):
        self.settings.auto_reset = True
        self.settings.slow_kbps = 0
        self.settings.stall_seconds = 30
        self.settings.max_resets = 1
        a, b, c = self.start()
        self.ready(a, b)
        other = self.engine.active[b.key]
        self.engine.active[a.key].watch.last_progress = time.monotonic() - 31
        self.engine.tick()
        self.assertEqual(a.status, 'resetting')
        self.assertIs(self.engine.active[b.key], other)
        self.assertEqual(b.resets, 0)
        self.assertEqual(c.status, 'queued')
        self.engine.active[a.key].next_start = 0
        self.engine.tick()
        self.ready(a)
        self.engine.active[a.key].watch.last_progress = time.monotonic() - 31
        self.engine.tick()
        self.assertEqual(a.status, 'failed')
        self.assertIn('上限 1 次', a.error)
        self.engine.active[b.key].watch.last_progress = time.monotonic() - 31
        self.engine.tick()
        self.assertEqual(b.status, 'resetting')
        self.engine.cancel([b.key])
        self.assertNotIn(b.key, self.engine.active)
        self.assertEqual(b.status, 'cancelled')

    def test_progress_events_and_resume_remain_separate(self):
        a, b = self.start(2)
        self.ready(a, b)
        state = self.engine.active[a.key]
        self.engine._handle(state, {'type': 'progress', 'done': 2, 'total': 5, 'cached': 1, 'bytes': 300, 'image_bytes': 600, 'message': 'a only'}, time.monotonic())
        self.assertEqual((a.done, a.image_bytes), (2, 600))
        self.assertEqual((b.done, b.image_bytes), (0, 0))
        self.assertEqual(self.engine.active[b.key].bytes, 0)
        self.engine.pause()
        self.engine.start()
        self.engine.tick()
        self.assertEqual(len(self.engine.active), 2)
        self.assertIsNot(self.engine.active[a.key], state)
