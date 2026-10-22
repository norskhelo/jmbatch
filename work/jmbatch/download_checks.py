"""Offline download and realtime-speed smoke checks for source/frozen builds."""
import json
import time
import tkinter as tk
import zipfile

from core import VERSION, Settings, SpeedWatch, Task
from diagnostics import fixture_worker
from engine import Engine, WorkerState


def run(directory):
    directory.mkdir(parents=True, exist_ok=True)
    checks = []
    engine = Engine(directory / 'state', worker_target=fixture_worker)
    root = None
    application = None
    try:
        engine.add(['123456'], Settings(download_all_chapters=True,
                   output=str(directory / 'artifacts'), format='zip'))
        engine.start()
        deadline = time.monotonic() + 90
        while engine.running and time.monotonic() < deadline:
            engine.tick()
            time.sleep(.05)
        assert not engine.running
        task = engine.tasks[0]
        assert task.status == 'done', task.to_dict()
        with zipfile.ZipFile(task.result) as archive:
            assert archive.testzip() is None
            assert archive.namelist() == ['0001/00001.jpg', '0001/00002.jpg',
                '0001/00003.jpg', '0002/00001.jpg', '0002/00002.jpg']
        checks.append('Frozen worker downloads five synthetic pages and commits a valid ZIP')

        watch = SpeedWatch(Settings(auto_reset=False), 0, 8192)
        assert watch.sample(1, 12288)[0] == 4096
        assert watch.sample(2, 12288)[0] == 0
        assert watch.sample(3, 16384)[0] == 4096
        checks.append('Completed-byte speed excludes prior progress and becomes zero when idle')

        from app import App
        root = tk.Tk()
        application = App(root, directory / 'gui-state')
        application.updates.automatic = False
        application.updates.seen_path.parent.mkdir(parents=True, exist_ok=True)
        application.updates.seen_path.write_text(VERSION, encoding='utf-8')
        display = Task('123456', dict(task.settings), status='running', done=2,
                       total=5, image_bytes=8192, speed=4096, phase='正在下载图片')
        state = WorkerState(display, phase='download', download_started=time.monotonic())
        application.engine.tasks = [display]
        application.engine.active[display.key] = state
        for phase in ('download', 'page_retry'):
            state.phase = phase
            application.render()
            root.update()
            assert '实时速度' in application.speed_text.get()
            assert '4.0 KB/s' in application.speed_text.get(), application.speed_text.get()
        display.speed = 0
        application.render()
        assert '0 B/s' in application.speed_text.get()
        checks.append('Actual download/retry UI displays realtime speed and clears stale throughput')
    finally:
        if application:
            application.engine.active.clear()
            application.engine.close()
        if root:
            root.destroy()
        engine.close()
    report = dict(ok=True, version=VERSION, network_used=False, checks=checks)
    (directory / 'self-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
