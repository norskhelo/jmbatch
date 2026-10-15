"""Read-only first-page thumbnails for the library, with bounded image decoding."""
import io
import re
import threading
import zipfile
from pathlib import Path

from PIL import Image, ImageOps

SIZE = (72, 96)
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 40_000_000
_pdf_lock = threading.Lock()  # PDFium calls must not overlap, even across windows.


def page_key(name):
    return [int(part) if part.isascii() and part.isdigit() else part.casefold()
            for part in re.split(r"([0-9]+)", name.replace("\\", "/"))]


def image_entry(name):
    parts = name.replace("\\", "/").split("/")
    return (not any(p in ("", ".", "..", "__MACOSX") or p.startswith(".") for p in parts)
            and Path(parts[-1]).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))


def decode_image(stream):
    with Image.open(stream) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError("封面图片过大")
        source.draft("RGB", SIZE)
        result = ImageOps.exif_transpose(source)
        result.thumbnail(SIZE, Image.Resampling.LANCZOS)
        return result.convert("RGB")


def load_cover(path, fmt):
    """Return a detached thumbnail or None. Never skip a broken first page."""
    try:
        path = Path(path)
        if path.is_symlink():
            return None
        if fmt == "images":
            from albums import read_album
            _, entries = read_album(path)
            first = Path(entries[0]["path"])
            if first.stat().st_size > MAX_IMAGE_BYTES:
                return None
            with first.open("rb") as stream:
                return decode_image(stream)
        if fmt == "zip":
            with zipfile.ZipFile(path) as archive:
                entries = [entry for entry in archive.infolist() if not entry.is_dir() and image_entry(entry.filename)]
                first = min(entries, key=lambda e: page_key(e.filename))
                if first.file_size > MAX_IMAGE_BYTES:
                    return None
                with archive.open(first) as stream:
                    data = stream.read(MAX_IMAGE_BYTES + 1)
                if len(data) > MAX_IMAGE_BYTES:
                    return None
                return decode_image(io.BytesIO(data))
        if fmt == "pdf":
            import pypdfium2 as pdfium
            with _pdf_lock, pdfium.PdfDocument(path) as document:
                page = document[0]
                width, height = page.get_size()
                scale = min(SIZE[0] / width, SIZE[1] / height)
                bitmap = page.render(scale=scale)
                try:
                    return bitmap.to_pil().convert("RGB").copy()
                finally:
                    bitmap.close()
    except Exception:
        # Missing files, expired permissions, encrypted/corrupt media stay manageable.
        return None
    return None


class CoverWorker:
    """One daemon, bounded queues; obsolete searches never build up behind a load."""
    def __init__(self):
        import queue
        self.jobs = queue.Queue(maxsize=24)
        self.results = queue.Queue(maxsize=24)
        self.closed = threading.Event()
        threading.Thread(target=self._run, daemon=True, name="library-covers").start()

    def _run(self):
        import queue
        while not self.closed.is_set():
            try:
                generation, key, path, fmt = self.jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            result = (generation, key, load_cover(path, fmt))
            while not self.closed.is_set():
                try:
                    self.results.put(result, timeout=0.2)
                    break
                except queue.Full:
                    pass

    def clear(self):
        import queue
        while True:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                return

    def close(self):
        self.closed.set()
        self.clear()
