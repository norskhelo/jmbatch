"""Real button and frozen-runtime coverage for cancellation cleanup."""
import time
from core import Task, Settings, task_cache
from engine import Engine


def check_cancel_ui(app, directory):
    old = app.engine
    engine = Engine(directory / 'cancel-state')
    task = Task('999222', Settings(output=str(directory / 'cancel-output')).__dict__, status='paused')
    engine.tasks = [task]
    cache = task_cache(task.to_dict())
    cache.mkdir(parents=True)
    (cache / 'image.jpg').write_bytes(b'cancelled image')
    try:
        app.engine = engine
        app.render()
        app.tree.selection_set(task.key)
        app.cancel_button.invoke()
        deadline = time.monotonic() + 10
        while engine.tasks and time.monotonic() < deadline:
            engine.tick()
            app.root.update()
            time.sleep(.02)
        app.render()
        assert not engine.tasks and not cache.exists()
        assert not app.tree.exists(task.key)
        assert not Engine(engine.home).tasks
        assert app.cancel_button.winfo_ismapped()
        assert app.cancel_button.winfo_rootx() + app.cancel_button.winfo_width() <= app.root.winfo_rootx() + app.root.winfo_width()
    finally:
        app.engine = old
        app.render()
