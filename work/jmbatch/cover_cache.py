"""Disposable, persistent first-page thumbnails shared by library and downloads."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading

from PIL import Image
from covers import load_cover

MAX_ENTRY = 256 * 1024
MAX_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 4096
_locks = [threading.Lock() for _ in range(32)]


def stamp(path):
    path = Path(path)
    if path.is_symlink():
        raise OSError("拒绝读取链接封面")
    value = path.stat()
    return [value.st_mtime_ns, value.st_size]


class CoverCache:
    def __init__(self, home):
        self.root = Path(home) / "covers"

    def file(self, path, fmt):
        key = fmt + "\n" + os.path.normcase(os.path.abspath(path))
        return self.root / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".cover")

    def _read(self, target, version):
        try:
            if target.stat().st_size > MAX_ENTRY:
                return None
            with target.open("rb") as stream:
                metadata = json.loads(stream.readline(16384))
                if metadata["version"] != 1 or metadata["source"] != version:
                    return None
                if any(stamp(path) != value for path, value in metadata["dependencies"]):
                    return None
                with Image.open(io.BytesIO(stream.read(MAX_ENTRY))) as image:
                    if image.width > 72 or image.height > 96:
                        return None
                    result = image.convert("RGB").copy()
            target.touch()  # Least recently used, including across application restarts.
            return result
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write(self, target, version, dependencies, image):
        temporary = None
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            data = io.BytesIO()
            image.save(data, format="PNG")
            header = dict(version=1, source=version, dependencies=dependencies)
            payload = json.dumps(header, ensure_ascii=True).encode("utf-8") + b"\n" + data.getvalue()
            if len(payload) > MAX_ENTRY:
                return
            with tempfile.NamedTemporaryFile(dir=self.root, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            os.replace(temporary, target)
            files = sorted(self.root.glob("*.cover"), key=lambda p: p.stat().st_mtime_ns)
            total = sum(p.stat().st_size for p in files)
            count = len(files)
            for old in files:
                if count <= MAX_ENTRIES and total <= MAX_BYTES:
                    break
                total -= old.stat().st_size
                old.unlink(missing_ok=True)
                count -= 1
        except OSError:
            pass  # A full/unwritable cache must never break downloads or previews.
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def load(self, path, fmt, *, first_page=None, relative=None):
        """Seed from a committed download page, or lazily extract an existing comic."""
        try:
            path = Path(path)
            target = self.file(path, fmt)
            with _locks[int(target.stem[:2], 16) % len(_locks)]:
                version = stamp(path)
                cached = self._read(target, version)
                if cached is not None:
                    return cached
                dependencies = []
                source, source_format = path, fmt
                if fmt == "images":
                    if relative is None:
                        from albums import read_album
                        _, entries = read_album(path)
                        source = Path(entries[0]["path"])
                    else:
                        source = path / relative
                    source_format = "image"
                    for dependency in dict.fromkeys((source, source.parent)):
                        dependencies.append((str(dependency), stamp(dependency)))
                    manifest = path / ".jmbatch-album.json"
                    if manifest.exists():
                        dependencies.append((str(manifest), stamp(manifest)))
                image = load_cover(first_page, "image") if first_page is not None else load_cover(source, source_format)
                if image is not None and stamp(path) == version and all(stamp(p) == s for p, s in dependencies):
                    self._write(target, version, dependencies, image)
                return image
        except Exception:
            return None

    def forget(self, path, fmt):
        try:
            self.file(path, fmt).unlink(missing_ok=True)
        except OSError:
            pass
