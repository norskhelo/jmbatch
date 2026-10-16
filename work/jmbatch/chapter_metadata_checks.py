"""Offline worker checks shipped in the source and frozen self-test."""
from pathlib import Path
import threading
import time

from core import Settings, Task, task_cache
from diagnostics import FixtureClient
from worker import run_download


class MetadataFixture(FixtureClient):
    def get_album_detail(self, album_id):
        import jmcomic
        return jmcomic.JmAlbumDetail(album_id, '220980', 'Metadata fixture',
            [(str(800000+i), str(i), 'Chapter') for i in range(1, 13)],
            12, '2026-10-16', '2026-10-16', '0', '0', 0, [], [], [], [])

    def check_photo(self, photo):
        if photo.page_arr is None:
            photo.page_arr = ['00001.jpg']
            photo.data_original_domain = 'offline.invalid'


def check_metadata_resume(directory):
    lock = threading.Lock()
    calls, active, peak = [], 0, 0

    class Client(MetadataFixture):
        def check_photo(self, photo):
            nonlocal active, peak
            if photo.page_arr is not None:
                return
            with lock:
                calls.append(str(photo.id)); active += 1; peak = max(peak, active)
            time.sleep(.025 if int(photo.id) % 2 else .01)
            super().check_photo(photo)
            with lock:
                active -= 1

        def download_by_image_detail(self, *args, **kwargs):
            raise AssertionError('This check must stop before images')

    class BeforeImages(Exception):
        pass

    def emit(event):
        if event.get('type') == 'phase' and event.get('phase') == 'download':
            raise BeforeImages()

    task = Task('123456', Settings(output=str(directory / 'output'), download_all_chapters=True).__dict__).to_dict()
    for attempt in range(2):
        try:
            run_download(task, '', emit, Client)
            raise AssertionError('Expected metadata boundary')
        except BeforeImages:
            pass
        assert len(calls) == 12
    assert 1 < peak <= 4 and active == 0
    assert len(list((task_cache(task) / 'chapters').glob('*.json'))) == 12
    return dict(chapters=12, requests_after_resume=len(calls)-12, peak=peak)
