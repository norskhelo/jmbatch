"""Coordinate library operations with downloads without pausing other books."""
from contextlib import contextmanager
from functools import wraps
from threading import get_ident


def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.state_lock:
            return method(self, *args, **kwargs)
    return call


def conflicts(library, task, item):
    return (bool(task.result) and library.key(task.result) == library.key(item["path"])) or (
        str(task.album_id) == item["id"] and
        library.key(task.settings["output"]) == library.key(item["root"]))


@contextmanager
def reserve(engine, keys):
    keys = list(dict.fromkeys(keys))
    with engine.state_lock:
        if (engine.file_targets is not None and engine.file_owner == get_ident() and
                set(keys) <= {engine.library.key(item["path"]) for item in engine.file_targets}):
            nested = True
        else:
            nested = False
    if nested:
        yield
        return
    with engine.state_lock:
        if engine.cleaning or engine.file_targets is not None:
            raise OSError("正在进行其他文件操作，请稍后重试")
        items = [dict(engine.library.entries[key]) for key in keys]
        for task in engine.tasks:
            busy = (task.status in ("queued", "running", "resetting", "cancelling", "cancel_failed") or
                    task.key in engine.active or task.key in engine.cancelling or task.key in engine.cancel_workers)
            if busy and any(conflicts(engine.library, task, item) for item in items):
                raise OSError("所选漫画仍有待下载或进行中的任务，请先暂停或取消该漫画的任务")
        engine.file_targets = items
        engine.file_owner = get_ident()
    try:
        yield
    finally:
        with engine.state_lock:
            engine.file_targets = None
            engine.file_owner = None
