"""Read portable download formats into ordered, temporary JPEG pages."""
import math
import re
import shutil
import tempfile
import zipfile
from contextlib import closing, contextmanager
from pathlib import Path, PurePosixPath

from core import verify_image

MAX_PAGES = 20000
MAX_IMAGE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 ** 3


def natural_key(value):
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold())
                 for part in re.split(r"([0-9]+)", value))


def zip_pages(archive):
    images, seen = [], set()
    for entry in archive.infolist():
        name = entry.filename
        parts = PurePosixPath(name).parts
        if "\\" in entry.orig_filename or name.startswith("/") or any(part in ("..", ".") or ":" in part for part in name.split("/")):
            raise ValueError("ZIP 包含不安全路径")
        if entry.is_dir() or not parts or any(part.startswith((".", "__MACOSX")) for part in parts):
            continue
        if PurePosixPath(name).suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        if name.casefold() in seen or (entry.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("ZIP 包含重复图片或链接")
        if entry.file_size <= 0 or entry.file_size > MAX_IMAGE_BYTES or entry.flag_bits & 1:
            raise ValueError("ZIP 图片过大、为空或已加密")
        images.append(entry)
        seen.add(name.casefold())
    if not images or len(images) > MAX_PAGES or sum(entry.file_size for entry in images) > MAX_TOTAL_BYTES:
        raise ValueError("ZIP 图片数量或总大小超出支持范围")
    images.sort(key=lambda entry: natural_key(entry.filename))
    return images


@contextmanager
def prepared_source(source, progress):
    from albums import read_album
    from PIL import Image
    source = Path(source)
    if source.is_symlink():
        raise ValueError("不支持链接文件")
    if source.is_dir():
        data, entries = read_album(source)
        for entry in entries:
            progress(dict(type="export_progress", message="校验源图片"))
            verify_image(Path(entry["path"]))
        yield data, entries
        return
    match = re.match(r"^(?:JM)?([0-9]{1,10})(?=$|[\s_.-])", source.stem, re.I)
    data = dict(id=match[1] if match else "0", title=source.stem)
    with tempfile.TemporaryDirectory(prefix="jmbatch-convert-") as temporary:
        folder, entries = Path(temporary), []
        if source.suffix.lower() == ".zip":
            with zipfile.ZipFile(source) as archive:
                images = zip_pages(archive)
                chapters, counts = {}, {}
                for index, entry in enumerate(images, 1):
                    progress(dict(type="export_progress", message=f"读取 ZIP 图片 {index}/{len(images)}"))
                    parent = str(PurePosixPath(entry.filename).parent)
                    chapter = chapters.setdefault(parent, len(chapters) + 1)
                    counts[chapter] = counts.get(chapter, 0) + 1
                    raw, target = folder / "source-image", folder / f"{index:05d}.jpg"
                    with archive.open(entry) as stream, raw.open("wb") as output:
                        copied = 0
                        while block := stream.read(65536):
                            progress(dict(type="export_progress", message=f"读取 ZIP 图片 {index}/{len(images)}"))
                            copied += len(block)
                            if copied > MAX_IMAGE_BYTES:
                                raise ValueError("ZIP 图片解压大小超出限制")
                            output.write(block)
                    verify_image(raw)
                    with Image.open(raw) as image:
                        if image.format == "JPEG":
                            shutil.copyfile(raw, target)
                        else:
                            image.convert("RGB").save(target, "JPEG", quality=95)
                    entries.append(dict(chapter=chapter, page=counts[chapter], path=str(target)))
        elif source.suffix.lower() == ".pdf":
            import pypdfium2 as pdfium
            from covers import _pdf_lock
            with _pdf_lock, pdfium.PdfDocument(source) as document:
                if not 0 < len(document) <= MAX_PAGES:
                    raise ValueError("PDF 页数超出支持范围")
                total_bytes = 0
                for index in range(len(document)):
                    progress(dict(type="export_progress", message=f"渲染 PDF 页面 {index + 1}/{len(document)}"))
                    with closing(document[index]) as page:
                        width, height = page.get_size()
                        if not math.isfinite(width * height) or min(width, height) <= 0:
                            raise ValueError("PDF 页面尺寸无效")
                        scale = min(2.0, 8192 / max(width, height), math.sqrt(16_000_000 / (width * height)))
                        bitmap = page.render(scale=scale)
                        try:
                            image = bitmap.to_pil().convert("RGB")
                            try:
                                target = folder / f"{index + 1:05d}.jpg"
                                image.save(target, "JPEG", quality=95)
                            finally:
                                image.close()
                        finally:
                            bitmap.close()
                    total_bytes += target.stat().st_size
                    if total_bytes > MAX_TOTAL_BYTES:
                        raise ValueError("PDF 转换后的图片总大小超出限制")
                    entries.append(dict(chapter=1, page=index + 1, path=str(target)))
        else:
            raise ValueError("请选择 PDF、ZIP 或图片文件夹")
        progress(dict(type="export_progress", message="源文件读取完成"))
        yield data, entries
