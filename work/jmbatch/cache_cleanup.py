"""Conservative cleanup of known task-owned artifacts; never follows links."""
from dataclasses import dataclass
from pathlib import Path
import stat

from core import task_cache
from download_display import format_size


@dataclass
class CleanupResult:
    files: int = 0
    bytes: int = 0
    errors: int = 0

    def add(self, other):
        self.files += other.files
        self.bytes += other.bytes
        self.errors += other.errors
        return self

    def message(self, automatic=False):
        text = ("自动清理" if automatic else "缓存清理") + f"：已删除 {self.files} 个文件，释放 {format_size(self.bytes)}"
        if self.errors:
            text += f"；{self.errors} 项未能清理，可稍后重试"
        return text


def _safe(path, owner):
    path.relative_to(owner)
    current = path
    while current != owner.parent:
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise OSError("拒绝清理链接或重解析路径")
        current = current.parent
    if not path.resolve().is_relative_to(owner.resolve()):
        raise OSError("缓存路径越界")


def clean_task(task, completed=False, progress=lambda result: None):
    result = CleanupResult()
    cache = task_cache(task)
    owner = cache.parent
    if not cache.exists() and not cache.is_symlink():
        return result
    try:
        _safe(cache, owner)
        children = list(cache.iterdir())
    except OSError:
        result.errors += 1
        return result

    def remove(path):
        try:
            _safe(path, owner)
            if path.is_dir():
                for child in path.iterdir():
                    remove(child)
                path.rmdir()
            elif path.is_file():
                size = path.stat().st_size
                path.unlink()
                result.files += 1
                result.bytes += size
                if result.files % 100 == 0:
                    progress(result)
        except OSError:
            result.errors += 1

    def partials(path):
        try:
            _safe(path, owner)
            if path.is_dir():
                for child in path.iterdir():
                    partials(child)
            elif path.name.endswith('.partial.jpg'):
                remove(path)
        except OSError:
            result.errors += 1

    for path in children:
        name = path.name
        if name == 'images':
            if completed and not task['settings'].get('keep_images', False):
                remove(path)
            else:
                partials(path)
        elif (name in ('export.partial.pdf', 'export.partial.zip', 'completed.tmp')
              or name.startswith('album.partial-')
              or (completed and name == 'chapters')):
            remove(path)
    progress(result)
    return result


def clean_tasks(tasks, progress=lambda result: None):
    result = CleanupResult()
    for task in tasks:
        # A missing result may still need its image cache for recovery.
        completed = task.status == 'done' and bool(task.result) and Path(task.result).exists()
        def update(current):
            progress(CleanupResult(result.files + current.files, result.bytes + current.bytes,
                                   result.errors + current.errors))
        result.add(clean_task(task.to_dict(), completed, update))
        progress(result)
    return result
