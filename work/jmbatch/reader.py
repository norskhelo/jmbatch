"""Lazy, read-only manga sources and persistent reader state."""
import io
import json
import math
import threading
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath

from core import atomic_json
from export_sources import MAX_IMAGE_BYTES, MAX_PAGES, zip_pages


class ReaderSource:
    """Owned by one worker. Only the requested page is decoded."""
    def __init__(self, path):
        self.path = Path(path)
        self.pages = []
        self.archive = self.pdf = None
        try:
            if self.path.is_symlink():
                raise ValueError("不支持链接文件")
            if self.path.is_dir():
                from albums import read_album
                _, self.pages = read_album(self.path)
            elif self.path.suffix.lower() == ".zip":
                self.archive = zipfile.ZipFile(self.path)
                chapters, counts = {}, {}
                for entry in zip_pages(self.archive):
                    parent = str(PurePosixPath(entry.filename).parent)
                    chapter = chapters.setdefault(parent, len(chapters) + 1)
                    counts[chapter] = counts.get(chapter, 0) + 1
                    self.pages.append(dict(chapter=chapter, page=counts[chapter], entry=entry))
            elif self.path.suffix.lower() == ".pdf":
                import pypdfium2 as pdfium
                from covers import _pdf_lock
                with _pdf_lock:
                    self.pdf = pdfium.PdfDocument(self.path)
                    self.pages = [dict(chapter=1, page=i + 1) for i in range(len(self.pdf))]
            else:
                raise ValueError("请选择图片文件夹、ZIP 或 PDF")
            if not 0 < len(self.pages) <= MAX_PAGES:
                raise ValueError("漫画为空或页数超过 20000 页")
        except Exception:
            self.close()
            raise

    def render(self, index, width, height=0):
        from PIL import Image, ImageOps
        width = max(100, min(1600, width))
        item = self.pages[index]
        if self.pdf is not None:
            from covers import _pdf_lock
            with _pdf_lock, closing(self.pdf[index]) as page:
                w, h = page.get_size()
                if not math.isfinite(w * h) or min(w, h) <= 0:
                    raise ValueError("PDF 页面尺寸无效")
                scale = min(width / w, 8192 / h, math.sqrt(4_000_000 / (w * h)))
                if height:
                    scale = min(scale, height / h)
                bitmap = page.render(scale=scale)
                try:
                    return bitmap.to_pil().convert("RGB").copy()
                finally:
                    bitmap.close()
        if self.archive:
            with self.archive.open(item["entry"]) as stream:
                data = stream.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError("图片过大")
            stream = io.BytesIO(data)
        else:
            if Path(item["path"]).stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError("图片过大")
            stream = open(item["path"], "rb")
        with stream, Image.open(stream) as original:
            w, h = original.size
            if min(w, h) <= 0 or w * h > 100_000_000:
                raise ValueError("图片尺寸超出支持范围")
            scale = min(1, width / w, 8192 / h, math.sqrt(4_000_000 / (w * h)))
            if height:
                scale = min(scale, height / h)
            original.draft("RGB", (max(1, int(w * scale)), max(1, int(h * scale))))
            image = ImageOps.exif_transpose(original)
            image.thumbnail((width, height or 8192), Image.Resampling.LANCZOS)
            if image.width * image.height > 4_000_000:
                factor = math.sqrt(4_000_000 / (image.width * image.height))
                image.thumbnail((int(image.width * factor), int(image.height * factor)))
            return image.convert("RGB")

    def close(self):
        if self.archive is not None:
            self.archive.close()
            self.archive = None
        if self.pdf is not None:
            from covers import _pdf_lock
            with _pdf_lock:
                self.pdf.close()
                self.pdf = None


class ReaderState:
    def __init__(self, home):
        self.path = Path(home) / "reader.json"
        self.books = {}
        self.error = ""
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("version") != 1 or not isinstance(data["books"], dict):
                    raise ValueError("阅读记录格式无效")
                self.books = data["books"]
        except Exception as exc:
            self.error = "阅读记录无法读取，原文件保留：" + str(exc)

    def get(self, key, total):
        data = self.books.get(key, {})
        try:
            return dict(page=max(0, min(total - 1, int(data.get("page", 0)))),
                        mode=data.get("mode") if data.get("mode") in ("scroll", "paged") else "scroll",
                        bookmarks=sorted({int(i) for i in data.get("bookmarks", []) if 0 <= int(i) < total}))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("本书阅读记录损坏，未覆盖原记录")

    def put(self, key, page, mode, bookmarks):
        if self.error:
            raise OSError(self.error)
        books = dict(self.books)
        books[key] = dict(page=page, mode=mode, bookmarks=sorted(bookmarks))
        atomic_json(self.path, dict(version=1, books=books))
        self.books = books


class ReaderWorker:
    """Latest viewport wins; bounded results and cancellation on window close."""
    def __init__(self, path):
        import queue
        self.results = queue.Queue(maxsize=2)
        self.condition = threading.Condition()
        self.closed = False
        self.requests = []
        self.path = path
        threading.Thread(target=self.run, daemon=True, name="manga-reader").start()

    def request(self, requests):
        with self.condition:
            self.requests = requests[:8]
            self.condition.notify()

    def post(self, value):
        import queue
        while not self.closed:
            try:
                self.results.put(value, timeout=.1)
                return
            except queue.Full:
                pass
        if value[0] == "image":
            value[-1].close()

    def run(self):
        source = None
        try:
            source = ReaderSource(self.path)
            self.post(("ready", [dict(chapter=p["chapter"], page=p["page"]) for p in source.pages]))
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.closed or self.requests)
                    if self.closed:
                        break
                    token, index, width, height = self.requests.pop(0)
                try:
                    self.post(("image", token, index, source.render(index, width, height)))
                except Exception as exc:
                    self.post(("error", token, index, str(exc)))
        except Exception as exc:
            self.post(("fatal", str(exc)))
        finally:
            if source:
                source.close()

    def close(self):
        import queue
        with self.condition:
            self.closed = True
            self.requests.clear()
            self.condition.notify()
        while True:
            try:
                result = self.results.get_nowait()
                if result[0] == "image":
                    result[-1].close()
            except queue.Empty:
                break
