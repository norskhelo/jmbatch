"""Delete only a cancelled task's cache and its recorded publication."""
import json
from pathlib import Path

from cache_cleanup import CleanupResult, _safe
from core import atomic_json, task_cache


def remember_publication(task, temporary, final):
    # Rename preserves file identity. A pre-existing/replaced destination never
    # belongs to us merely because its name matches.
    info = Path(temporary).stat()
    atomic_json(task_cache(task) / 'publication.json', {
        'path': str(Path(final).parent.resolve() / Path(final).name), 'device': info.st_dev, 'inode': info.st_ino})


def discard_task(task):
    result = CleanupResult()
    cache = task_cache(task)
    owner = cache.parent
    if not cache.exists() and not cache.is_symlink():
        return result

    def remove(path, root):
        _safe(path, root)
        if path.is_dir():
            for child in path.iterdir():
                remove(child, root)
            path.rmdir()
        else:
            size = path.stat().st_size
            path.unlink()
            result.files += 1
            result.bytes += size

    try:
        _safe(cache, owner)
        journal = cache / 'publication.json'
        if journal.exists():
            _safe(journal, owner)
            data = json.loads(journal.read_text(encoding='utf-8'))
            final = Path(data['path'])
            output = Path(task['settings']['output']).resolve()
            if final.parent != output:
                raise ValueError('输出路径不属于此任务保存目录')
            owned = not final.exists() and not final.is_symlink()
            if final.exists() or final.is_symlink():
                _safe(final, output)
                info = final.stat()
                if (info.st_dev, info.st_ino) == (data['device'], data['inode']):
                    remove(final, output)
                    owned = True
            if owned:
                from albums import album_index
                index = album_index(final)
                if index.exists():
                    _safe(index, index.parent)
                    index.unlink()
        remove(cache, owner)
    except (OSError, ValueError, KeyError, TypeError):
        result.errors += 1
    return result
