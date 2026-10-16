import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cache_cleanup import clean_task, clean_tasks
from core import Settings, Task, task_cache
from diagnostics import FixtureClient
from engine import Engine
from worker import run_download


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.task = Task('123456', Settings(output=str(self.root / 'out'), download_all_chapters=True).__dict__)
        self.cache = task_cache(self.task.to_dict())

    def tearDown(self):
        self.temp.cleanup()

    def put(self, name, data=b'fixture'):
        path = self.cache / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_completed_cleans_known_artifacts_and_counts_actual_bytes(self):
        removed = ['images/0001/00001.jpg', 'chapters/1.json', 'export.partial.zip', 'album.partial-fixture/00001.jpg']
        for name in removed:
            self.put(name)
        marker = self.put('completed.json')
        unknown = self.put('personal.txt')
        self.task.result = str(self.root / 'out/final.zip')
        Path(self.task.result).write_bytes(b'output')
        self.task.status = 'done'
        result = clean_tasks([self.task])
        self.assertEqual((result.files, result.bytes, result.errors), (4, 28, 0))
        self.assertTrue(marker.exists() and unknown.exists())
        self.assertEqual(Path(self.task.result).read_bytes(), b'output')
        self.assertEqual(clean_tasks([self.task]).files, 0)

    def test_unfinished_keeps_resume_images_and_chapters(self):
        for status in ('paused', 'failed', 'cancelled', 'queued', 'selecting'):
            self.task.status = status
            image = self.put('images/0001/00001.jpg')
            metadata = self.put('chapters/1.json')
            self.put('images/0001/00002.partial.jpg')
            self.put('export.partial.pdf')
            result = clean_tasks([self.task])
            self.assertEqual(result.files, 2)
            self.assertTrue(image.exists() and metadata.exists())

    def test_keep_images_setting_respected(self):
        self.task.settings['keep_images'] = True
        image = self.put('images/0001/00001.jpg')
        self.put('chapters/1.json')
        self.put('images/0001/00002.partial.jpg')
        result = clean_task(self.task.to_dict(), completed=True)
        self.assertEqual(result.files, 2)
        self.assertTrue(image.exists())

    def test_missing_output_preserves_recovery_cache(self):
        self.task.status, self.task.result = 'done', str(self.root / 'missing.zip')
        image = self.put('images/0001/00001.jpg')
        self.assertEqual(clean_tasks([self.task]).files, 0)
        self.assertTrue(image.exists())

    def test_missing_cache_is_not_created(self):
        self.assertEqual(clean_tasks([self.task]).files, 0)
        self.assertFalse(self.cache.exists())

    def test_delete_failure_reports_only_successful_deletions_and_can_retry(self):
        locked = self.put('images/0001/00001.jpg')
        self.put('images/0001/00002.jpg')
        original = Path.unlink
        def unlink(path, *args, **kwargs):
            if path == locked:
                raise PermissionError('in use')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', unlink):
            result = clean_task(self.task.to_dict(), completed=True)
        self.assertEqual((result.files, result.bytes), (1, 7))
        self.assertGreater(result.errors, 0)
        self.assertIn('未能清理', result.message(True))
        self.assertEqual(clean_task(self.task.to_dict(), completed=True).files, 1)

    def test_junctions_cannot_delete_external_files(self):
        import os
        external = self.root / 'external'
        external.mkdir()
        important = external / 'keep.jpg'
        important.write_bytes(b'keep')
        self.cache.mkdir(parents=True)
        for link in (self.cache / 'images', self.cache / 'album.partial-link'):
            if os.name == 'nt':
                import _winapi
                _winapi.CreateJunction(str(external), str(link))
            else:
                link.symlink_to(external, target_is_directory=True)
        result = clean_task(self.task.to_dict(), completed=True)
        self.assertGreaterEqual(result.errors, 2)
        self.assertEqual(result.files, 0)
        self.assertEqual(important.read_bytes(), b'keep')

    def test_cache_owner_junction_is_rejected(self):
        import os
        external = self.root / 'external'
        external.mkdir()
        self.cache.parent.parent.mkdir(parents=True)
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(external), str(self.cache.parent))
        else:
            self.cache.parent.symlink_to(external, target_is_directory=True)
        image = self.put('images/0001/00001.jpg')
        result = clean_task(self.task.to_dict(), completed=True)
        self.assertGreater(result.errors, 0)
        self.assertTrue(image.exists())

    def test_automatic_cleanup_and_recovery_marker_for_three_formats(self):
        for fmt in ('pdf', 'zip', 'images'):
            self.task.settings['format'] = fmt
            self.task.key = {'pdf': '1', 'zip': '2', 'images': '3'}[fmt] * 32
            events = []
            run_download(self.task.to_dict(), '', events.append, FixtureClient)
            done = events[-1]
            self.assertIn('自动清理', done['cleanup'])
            self.assertIn('释放', done['message'])
            cache = task_cache(self.task.to_dict())
            self.assertFalse((cache / 'images').exists())
            self.assertTrue((cache / 'completed.json').is_file())
            # Simulate a crash after committing output but before cache cleanup.
            page = cache / 'images/0001/00001.jpg'
            page.parent.mkdir(parents=True)
            page.write_bytes(b'redundant')
            retry = []
            with patch.object(FixtureClient, 'get_album_detail', side_effect=AssertionError('network')):
                run_download(self.task.to_dict(), '', retry.append, FixtureClient)
            self.assertEqual(retry[-1]['path'], done['path'])
            self.assertIn('1 个文件', retry[-1]['cleanup'])
            self.assertFalse(page.exists())

    def test_maintenance_blocks_worker_start_and_retry(self):
        engine = Engine(self.root / 'state')
        engine.tasks = [self.task]
        engine.cleaning = True
        engine.start()
        engine.tick()
        self.assertFalse(engine.running or engine.active)
        with self.assertRaises(ValueError):
            engine.retry([self.task.key])
