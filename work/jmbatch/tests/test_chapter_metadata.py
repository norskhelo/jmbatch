import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from chapter_metadata import MetadataCache, cache_scope, hydrate, TTL_SECONDS
from chapter_metadata_checks import MetadataFixture, check_metadata_resume
from core import Settings, task_cache
from engine import Engine
from worker import run_download


def metadata_pause_worker(task, cookie, channel):
    cache = task_cache(task)
    class Client(MetadataFixture):
        def check_photo(self, photo):
            if photo.page_arr is not None:
                return
            if photo.id == '800001':
                with (cache / 'first-requests.txt').open('a') as out:
                    out.write('request\n')
            else:
                (cache / 'waiting').touch()
                end = time.monotonic() + 30
                while not (cache / 'continue').exists():
                    if time.monotonic() > end:
                        raise TimeoutError('test gate')
                    time.sleep(.02)
            super().check_photo(photo)
    try:
        run_download(task, cookie, channel.put, Client)
    except Exception as error:
        channel.put(dict(type='error', error=str(error)))


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = MetadataFixture()
        self.album = self.client.get_album_detail('123456')
        self.cache = MetadataCache(self.root / 'chapters', cache_scope(self.album, ''))

    def tearDown(self):
        self.temp.cleanup()

    def test_worker_parallel_and_restart_zero_requests(self):
        self.assertEqual(check_metadata_resume(self.root)['requests_after_resume'], 0)

    def test_out_of_order_keeps_order_and_progress(self):
        photos = list(self.album)
        progress = []
        hydrate(photos, self.cache, self.client.check_photo, lambda *p: progress.append(p))
        self.assertEqual([p.id for p in photos], [str(800001+i) for i in range(12)])
        self.assertEqual([p[0] for p in progress], list(range(13)))
        photos = list(self.album)
        with patch.object(self.client, 'check_photo', side_effect=AssertionError('network')):
            self.assertEqual(hydrate(photos, self.cache, self.client.check_photo, lambda *p: None), 12)

    def test_invalid_records_refetch_only_affected_chapters(self):
        hydrate(list(self.album), self.cache, self.client.check_photo, lambda *p: None)
        self.cache.path('800002').write_text('{broken')
        record = json.loads(self.cache.path('800004').read_text())
        record['saved'] -= TTL_SECONDS + 1
        self.cache.path('800004').write_text(json.dumps(record))
        self.cache.path('800006').unlink()
        (self.cache.root / '800006.tmp').write_text('{}')
        calls = []
        def fetch(photo):
            calls.append(photo.id); self.client.check_photo(photo)
        self.assertEqual(hydrate(list(self.album), self.cache, fetch, lambda *p: None), 9)
        self.assertEqual(set(calls), {'800002', '800004', '800006'})

    def test_scope_and_schema_mismatch_future_time_and_bad_data(self):
        photo = self.album[0]; self.client.check_photo(photo); self.cache.write(photo)
        original = json.loads(self.cache.path(photo.id).read_text())
        for key, value in [('scope', 'different'), ('schema', 99), ('id', '800099'), ('saved', time.time()+99), ('data', {'pages': []})]:
            record = dict(original); record[key] = value
            self.cache.path(photo.id).write_text(json.dumps(record))
            self.assertFalse(self.cache.read(self.album[0]), key)
        self.assertNotEqual(cache_scope(self.album, ''), cache_scope(self.album, 'auth=changed'))
        scope = cache_scope(self.album, '')
        self.album.page_count += 1
        self.assertNotEqual(scope, cache_scope(self.album, ''))

    def test_malicious_filename_and_oversized_record_are_rejected(self):
        photo = self.album[0]; self.client.check_photo(photo)
        photo.page_arr = ['../secret.jpg']
        with self.assertRaises(ValueError): self.cache.write(photo)
        with self.assertRaises(ValueError): self.cache.path('../escape')
        self.cache.root.mkdir(exist_ok=True)
        self.cache.path('800001').write_bytes(b'x' * (2*1024*1024+1))
        self.assertFalse(self.cache.read(self.album[0]))

    def test_failure_preserves_success_and_retry_skips_it(self):
        photos = list(self.album)
        def fail(photo):
            if photo.id != '800001': raise IOError('chapter unavailable')
            self.client.check_photo(photo)
        with self.assertRaises(IOError): hydrate(photos, self.cache, fail, lambda *p: None)
        calls = []
        def fetch(photo): calls.append(photo.id); self.client.check_photo(photo)
        hydrate(list(self.album), self.cache, fetch, lambda *p: None)
        self.assertNotIn('800001', calls)
        self.assertEqual(len(calls), 11)

    def test_cache_ttl_does_not_extend_on_read(self):
        photo = self.album[0]; self.client.check_photo(photo)
        self.cache.clock = lambda: 100
        self.cache.write(photo)
        self.cache.clock = lambda: 100+TTL_SECONDS-1
        self.assertTrue(self.cache.read(self.album[0]))
        self.cache.clock = lambda: 100+TTL_SECONDS
        self.assertFalse(self.cache.read(self.album[0]))

    def test_real_process_pause_and_restart_reuses_completed_metadata(self):
        engine = Engine(self.root / 'state', worker_target=metadata_pause_worker)
        engine.add(['123456'], Settings(output=str(self.root / 'output'), download_all_chapters=True, auto_reset=False))
        task = engine.tasks[0]; cache = task_cache(task.to_dict())
        def wait(predicate):
            end = time.monotonic()+30
            while time.monotonic()<end:
                engine.tick()
                if predicate(): return
                time.sleep(.02)
            self.fail([(t.status,t.error) for t in engine.tasks])
        try:
            engine.start(); wait(lambda: (cache/'waiting').exists() and (cache/'chapters/800001.json').exists())
            engine.pause(); engine.close()
            engine = Engine(self.root/'state', worker_target=metadata_pause_worker)
            self.assertEqual(engine.tasks[0].status, 'paused')
            (cache/'continue').touch(); engine.start(); wait(lambda: engine.tasks[0].status=='done')
            self.assertEqual((cache/'first-requests.txt').read_text().splitlines(), ['request'])
            self.assertEqual(engine.tasks[0].total, 12)
        finally:
            engine.close()


if __name__ == '__main__': unittest.main()
