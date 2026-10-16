"""Resume real download hooks with generated pages and no site requests."""
import io
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from core import Settings, SpeedWatch, Task, task_cache
from diagnostics import FixtureClient
from engine import Engine, WorkerState
from worker import run_download


class PausableClient(FixtureClient):
    def download_by_image_detail(self, image, path, decode_image=True):
        cache = Path(path).parents[2]
        if (image.from_photo.sort, image.index) == (2, 1):
            (cache / 'ready').touch()
            deadline = time.monotonic() + 30
            while not (cache / 'continue').exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError('offline gate timed out')
                time.sleep(.02)
        super().download_by_image_detail(image, path, decode_image)
        with (cache / 'requests.txt').open('a', encoding='utf-8') as log:
            log.write(f'{image.from_photo.sort}:{image.index}\n')


def pausable_worker(task, cookie, channel):
    try:
        run_download(task, cookie, channel.put, PausableClient)
    except Exception as error:
        channel.put({'type': 'error', 'error': str(error)})


class ResumeTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parents[2] / 'tests' / 'resume'
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.root = Path(self.temp.name)
        stream = io.BytesIO()
        Image.new('RGB', (8, 8), 'white').save(stream, 'JPEG')
        self.jpeg = stream.getvalue()

    def tearDown(self):
        self.temp.cleanup()

    def test_7227_pages_resume_only_missing_or_broken_images(self):
        import jmcomic
        counts = (3000, 3000, 1227)
        requested = []
        jpeg = self.jpeg
        class LargeClient(FixtureClient):
            def get_album_detail(self, album_id):
                return jmcomic.JmAlbumDetail(album_id, '220980', '7227 offline pages',
                    [(str(800001 + i), str(i + 1), 'Chapter') for i in range(3)],
                    7227, '2026-01-01', '2026-01-01', '0', '0', 0, [], [], [], [])

            def check_photo(self, photo):
                photo.page_arr = [f'{i:05d}.jpg' for i in range(1, counts[photo.sort - 1] + 1)]
                photo.data_original_domain = 'offline.invalid'

            def download_by_image_detail(self, image, path, decode_image=True):
                requested.append((image.from_photo.sort, image.index))
                Path(path).write_bytes(jpeg)

        task = Task('123456', Settings(download_all_chapters=True, output=str(self.root / 'out'), keep_images=True).__dict__).to_dict()
        cache = task_cache(task)
        positions = [(chapter, page) for chapter, count in enumerate(counts, 1) for page in range(1, count + 1)]
        saved = set(positions[:4321]) | {(3, 100)}  # also keep out-of-order completed work
        for chapter, page in saved:
            target = cache / 'images' / f'{chapter:04d}' / f'{page:05d}.jpg'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(jpeg)
        broken = cache / 'images/0001/00002.jpg'
        broken.write_bytes(b'broken')
        saved.remove((1, 2))
        (cache / 'images/0002/01322.partial.jpg').write_bytes(b'incomplete')
        events = []
        # This regression concerns download/resume; export is covered separately.
        with patch('albums.save_album', return_value=(self.root / 'album', len(jpeg) * 7227)) as save:
            run_download(task, '', events.append, LargeClient)
        self.assertEqual(Counter(requested), Counter(set(positions) - saved))
        progress = [event for event in events if event['type'] == 'progress']
        self.assertEqual(progress[0]['done'], len(saved))
        self.assertEqual(progress[0]['cached'], len(saved))
        self.assertEqual(progress[0]['bytes'], 0)
        self.assertEqual(progress[-1]['done'], 7227)
        self.assertEqual(progress[-1]['image_bytes'], len(jpeg) * 7227)
        self.assertEqual(progress[-1]['bytes'], len(jpeg) * (7227 - len(saved)))
        self.assertEqual([e['done'] for e in progress], sorted(e['done'] for e in progress))
        self.assertEqual(len(save.call_args.args[2]), 7227)
        self.assertEqual(events[-1]['total'], 7227)
        self.assertIn('cache', [e.get('phase') for e in events])

    def test_launch_keeps_last_progress_until_cache_reconciled(self):
        engine = Engine(self.root / 'state')
        task = Task('123456', Settings(download_all_chapters=True, output=str(self.root / 'out')).__dict__,
                    status='paused', done=4321, total=7227, cached=100, image_bytes=123456)
        engine.tasks = [task]
        try:
            with patch.object(engine, 'context'):
                engine.start()
                engine.tick()
                self.assertEqual((task.done, task.total, task.image_bytes), (4321, 7227, 123456))
        finally:
            engine.close()

    def test_stop_start_and_app_restart_reuse_actual_worker_cache(self):
        for cold_start in (False, True):
            with self.subTest(cold_start=cold_start):
                root = self.root / str(cold_start)
                engine = Engine(root / 'state', worker_target=pausable_worker)
                engine.add(['123456'], Settings(download_all_chapters=True, output=str(root / 'out'), threads=1, auto_reset=False))
                task = engine.tasks[0]
                cache = task_cache(task.to_dict())
                try:
                    engine.start()
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        engine.tick()
                        if task.done == 3 and (cache / 'ready').exists():
                            break
                        time.sleep(.02)
                    self.assertEqual(task.done, 3)
                    engine.pause()
                    snapshot = (task.done, task.total, task.image_bytes)
                    self.assertEqual(task.status, 'paused')
                    if cold_start:
                        engine.close()
                        engine = Engine(root / 'state', worker_target=pausable_worker)
                        task = engine.tasks[0]
                    self.assertEqual((task.done, task.total, task.image_bytes), snapshot)
                    (cache / 'continue').touch()
                    engine.start()
                    engine.tick()
                    self.assertEqual((task.done, task.total, task.image_bytes), snapshot)
                    deadline = time.monotonic() + 20
                    while engine.running and time.monotonic() < deadline:
                        engine.tick()
                        self.assertGreaterEqual(task.done, 3)
                        time.sleep(.02)
                    self.assertEqual(task.status, 'done', task.error)
                    self.assertEqual(task.cached, 3)
                    self.assertEqual((cache / 'requests.txt').read_text().splitlines(),
                                     ['1:1', '1:2', '1:3', '2:1', '2:2'])
                    from albums import read_album
                    self.assertEqual(len(read_album(task.result, verify=True)[1]), 5)
                finally:
                    engine.close()

    def test_cache_scan_never_triggers_network_watchdog(self):
        engine = Engine(self.root / 'state')
        task = Task('123456', Settings(download_all_chapters=True, output=str(self.root / 'out')).__dict__, status='running')
        state = WorkerState(task, watch=SpeedWatch(Settings(**task.settings), 0))
        from unittest.mock import Mock
        state.process = Mock()
        state.process.is_alive.return_value = True
        engine.active[task.key] = state
        try:
            engine._handle(state, {'type': 'phase', 'phase': 'cache', 'message': '校验已有图片'}, 0)
            engine._tick_worker(state, 600)
            self.assertEqual(task.status, 'running')
            self.assertEqual(task.resets, 0)
            self.assertEqual(task.speed, 0)
            engine._handle(state, {'type': 'phase', 'phase': 'download', 'total': 7227, 'message': '继续下载'}, 600)
            engine._tick_worker(state, 601)
            self.assertEqual(task.status, 'running')
            engine._tick_worker(state, 600 + task.settings['stall_seconds'] + 1)
            self.assertEqual(task.status, 'resetting')  # real network stalls still recover
        finally:
            engine.close()
