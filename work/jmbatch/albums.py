"""Ordered image albums and offline folder, PDF and ZIP conversion."""
import json
import hashlib
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from core import atomic_json, export_images, safe_name, task_cache, verify_image, Settings

MANIFEST = ".jmbatch-album.json"
LAYOUT_VERSION = 2


def album_index(folder):
    """Keep recovery metadata in application state, never in the delivered album."""
    home = Path(os.environ.get("JM_BATCH_HOME") or (Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JMBatch"))
    identity = os.path.normcase(str(Path(folder).resolve())).encode("utf-8")
    return home / "albums" / (hashlib.sha256(identity).hexdigest() + ".json")


def image_name(chapter, page, chapter_count):
    return f"{page:05d}.jpg" if chapter_count == 1 else f"{chapter:04d}/{page:05d}.jpg"


def scan_album(folder):
    """Recover portable image-only albums after moving them or clearing app state."""
    match = re.fullmatch(r"JM([0-9]{1,10})-(.*)-[0-9a-f]{8}|([0-9]{1,10})", folder.name)
    if not match:
        raise ValueError("无法识别图片目录名称")
    records = []
    for path in folder.iterdir():
        if path.is_symlink():
            raise ValueError("图片目录含链接")
        if path.is_file() and re.fullmatch(r"[0-9]{5,}\.jpg", path.name):
            records.append(dict(chapter=1, page=int(path.stem), file=path.name, size=path.stat().st_size))
        elif path.is_dir() and re.fullmatch(r"[0-9]{4,}", path.name):
            for image in path.iterdir():
                if image.is_symlink():
                    raise ValueError("图片目录含链接")
                if image.is_file() and re.fullmatch(r"[0-9]{5,}\.jpg", image.name):
                    records.append(dict(chapter=int(path.name), page=int(image.stem), file=path.name + "/" + image.name, size=image.stat().st_size))
    groups = {}
    for item in records:
        groups.setdefault(item["chapter"], []).append(item["page"])
    if sorted(groups) != list(range(1, len(groups) + 1)) or any(sorted(pages) != list(range(1, len(pages) + 1)) for pages in groups.values()):
        raise ValueError("图片章节或页码不连续")
    return dict(version=LAYOUT_VERSION, id=match[1] or match[3], title=match[2] or folder.name, entries=records)


def read_album(folder, verify=False):
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("图片目录不存在或为链接")
    marker = folder / MANIFEST
    if not marker.exists() and not marker.is_symlink():
        marker = album_index(folder)
    if marker.exists() or marker.is_symlink():
        if marker.is_symlink() or marker.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("图片目录信息无效")
        data = json.loads(marker.read_text(encoding="utf-8"))
    else:
        data = scan_album(folder)
    if data.get("version") not in (1, LAYOUT_VERSION) or not re.fullmatch(r"[0-9]{1,10}", str(data.get("id", ""))):
        raise ValueError("图片目录信息无效")
    entries, seen = [], set()
    chapter_count = len({int(item["chapter"]) for item in data["entries"]})
    for item in data["entries"]:
        chapter, page = int(item["chapter"]), int(item["page"])
        relative = f"{chapter:04d}/{page:05d}.jpg" if data["version"] == 1 else image_name(chapter, page, chapter_count)
        if chapter <= 0 or page <= 0 or item["file"] != relative or relative in seen:
            raise ValueError("图片顺序或路径无效")
        path = folder / relative
        if path.parent.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size != item["size"]:
            raise ValueError("图片缺失、大小变化或路径异常：" + relative)
        if verify:
            verify_image(path)
        entries.append(dict(chapter=chapter, page=page, path=str(path)))
        seen.add(relative)
    if not entries:
        raise ValueError("没有可用图片")
    entries.sort(key=lambda e: (e["chapter"], e["page"]))
    return data, entries


def save_album(task, title, entries, emit):
    output, cache = Path(task["settings"]["output"]), task_cache(task)
    final = output / f"JM{task['album_id']}-{safe_name(title)}-{uuid.uuid4().hex[:8]}"
    # A unique staging directory allows retry without removing an earlier partial.
    staging = Path(tempfile.mkdtemp(prefix="album.partial-", dir=cache))
    records = []
    chapter_count = len({entry["chapter"] for entry in entries})
    try:
        emit(dict(type="phase", phase="verify", message="校验并保存排序图片"))
        for entry in sorted(entries, key=lambda e: (e["chapter"], e["page"])):
            source = Path(entry["path"])
            verify_image(source)
            relative = image_name(entry["chapter"], entry["page"], chapter_count)
            target = staging / relative
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
            if target.stat().st_size != source.stat().st_size:
                raise OSError("图片保存不完整")
            records.append(dict(chapter=entry["chapter"], page=entry["page"], file=relative, size=target.stat().st_size))
            emit(dict(type="export_progress", message=f"保存图片 {len(records)}/{len(entries)}"))
        if not records:
            raise ValueError("没有可用图片")
        os.rename(staging, final)
        atomic_json(album_index(final), dict(version=LAYOUT_VERSION, id=task["album_id"], title=title, entries=records))
        read_album(final)
        atomic_json(cache / "completed.json", dict(path=str(final), images=len(entries), format="images", album_layout_version=LAYOUT_VERSION))
        return final, sum(item["size"] for item in records)
    finally:
        # Only the newly created staging directory is owned by this operation.
        if staging.exists():
            shutil.rmtree(staging)


def export_album(folder, destination, fmt, numeric=False, flat=False, split_pdf=False, emit=lambda e: None, cancelled=lambda: False):
    from export_sources import prepared_source
    if fmt not in ("images", "pdf", "zip"):
        raise ValueError("请选择 PDF、ZIP 或文件夹")
    def progress(event):
        if cancelled():
            raise InterruptedError("导出已取消，源文件保留")
        emit(event)
    source = Path(folder).resolve()
    destination = Path(destination).resolve()
    if source.is_dir() and destination.is_relative_to(source):
        raise ValueError("请选择源文件夹以外的导出目录")
    progress(dict(type="export_progress", message="读取源文件"))
    with prepared_source(folder, progress) as (data, entries):
        return export_entries(data, entries, destination, fmt, numeric, flat, split_pdf, progress)


def export_entries(data, entries, destination, fmt, numeric, flat, split_pdf, progress):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    groups = {}
    for entry in entries:
        groups.setdefault(entry["chapter"] if fmt == "pdf" and split_pdf else 0, []).append(entry)
    stem = str(data["id"]) if numeric else f"JM{data['id']}-{safe_name(data['title'])}-{uuid.uuid4().hex[:8]}"
    targets = [destination / (stem + (f"-{chapter:04d}" if chapter else "") + ("" if fmt == "images" else "." + fmt)) for chapter in groups]
    if any(target.exists() for target in targets):
        raise FileExistsError("同名导出文件已存在，请更换目录或关闭纯编号命名；未覆盖")
    committed = []
    records = []
    try:
        with tempfile.TemporaryDirectory(prefix=".jmbatch-export-", dir=destination) as temporary:
            staging = Path(temporary)
            ready = []
            for (chapter, pages), target in zip(groups.items(), targets):
                progress(dict(type="export_progress", message=f"导出第 {chapter} 章" if chapter else "正在导出"))
                if fmt == "images":
                    output = staging / target.name
                    output.mkdir()
                    chapter_count = len({entry["chapter"] for entry in pages})
                    for entry in pages:
                        progress(dict(type="export_progress", message=f"保存图片 {len(records) + 1}/{len(pages)}"))
                        relative = image_name(entry["chapter"], entry["page"], chapter_count)
                        image = output / relative
                        image.parent.mkdir(exist_ok=True)
                        shutil.copyfile(entry["path"], image)
                        records.append(dict(chapter=entry["chapter"], page=entry["page"], file=relative, size=image.stat().st_size))
                    ready.append(output)
                else:
                    task = dict(album_id=str(data["id"]), key=uuid.uuid4().hex,
                                settings=Settings(output=str(staging), format=fmt, flat_zip=flat).__dict__)
                    ready.append(export_images(task, data["title"], pages, progress))
            for source, target in zip(ready, targets):
                progress(dict(type="export_progress", message="保存导出文件"))
                if os.name == "nt" or source.is_dir():
                    if target.exists():
                        raise FileExistsError("同名导出成品已存在，未覆盖")
                    os.rename(source, target)
                else:
                    os.link(source, target)
                    source.unlink()
                committed.append(target)
                if fmt == "images":
                    atomic_json(album_index(target), dict(version=LAYOUT_VERSION, id=data["id"], title=data["title"], entries=records))
        return committed
    except Exception:
        for target in committed:
            if target.is_dir():
                shutil.rmtree(target)
                album_index(target).unlink(missing_ok=True)
            else:
                target.unlink(missing_ok=True)
        raise
