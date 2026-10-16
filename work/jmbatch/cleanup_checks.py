"""Exercise the shipped cleanup button and worker exclusion in a real Tk window."""
import threading
import time
from unittest.mock import patch

from core import Task, Settings, task_cache
from engine import Engine


def check_cleanup_ui(app, directory):
    from cache_cleanup import clean_tasks
    old = app.engine
    engine = Engine(directory / 'cleanup-state')
    task = Task('999111', Settings(output=str(directory / 'cleanup-output')).__dict__, status='paused')
    engine.tasks = [task]
    cache = task_cache(task.to_dict())
    (cache / 'images/0001').mkdir(parents=True)
    image = cache / 'images/0001/00001.jpg'
    partial = cache / 'images/0001/00002.partial.jpg'
    image.write_bytes(b'resume-image')
    partial.write_bytes(b'junk')
    gate, entered = threading.Event(), threading.Event()
    app.engine = engine
    app.root.update_idletasks()
    assert app.cleanup_button.winfo_width() > 80
    assert app.cleanup_button.winfo_rootx() + app.cleanup_button.winfo_width() <= app.root.winfo_rootx() + app.root.winfo_width()
    def blocked(*args, **kwargs):
        entered.set()
        if not gate.wait(10):
            raise TimeoutError('cleanup fixture gate')
        return clean_tasks(*args, **kwargs)
    try:
        with patch('cleanup_ui.clean_tasks', blocked):
            app.cleanup_button.invoke()
            assert entered.wait(3) and engine.cleaning
            engine.start()
            engine.tick()
            assert not engine.running and not engine.active
            gate.set()
            deadline = time.monotonic() + 10
            while engine.cleaning and time.monotonic() < deadline:
                app.root.update()
                time.sleep(.02)
            assert not engine.cleaning
        assert image.read_bytes() == b'resume-image' and not partial.exists()
        dialogs = [w for w in app.root.winfo_children() if w.winfo_class() == 'Toplevel' and w.title() == '清理下载缓存']
        assert len(dialogs) == 1
        text = '\n'.join(str(w.cget('text')) for w in dialogs[0].winfo_children() if 'text' in w.keys())
        assert '1 个文件' in text and '4 B' in text
        dialogs[0].destroy()
    finally:
        gate.set()
        app.engine = old
