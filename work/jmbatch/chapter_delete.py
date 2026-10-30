"""Remove chapters by validating a replacement before touching the source."""
import hashlib
import os
import re
import shutil
import uuid
import zipfile
from collections import Counter
from pathlib import Path

from albums import MANIFEST, album_index, image_name, read_album
from core import atomic_json, safe_name
from reader import ReaderSource, ReaderState
from export_sources import MAX_TOTAL_BYTES


def _check(cancelled):
    if cancelled():
        raise InterruptedError("已取消删除章节，原漫画保留")


def _folder_contents(path, pages):
    allowed = {Path(p["path"]).absolute() for p in pages} | {(path / MANIFEST).absolute()}
    directories = {Path(p["path"]).parent.absolute() for p in pages}
    for child in path.rglob("*"):
        if child.is_symlink() or child.is_junction() or (child.is_dir() and child.absolute() not in directories) or (child.is_file() and child.absolute() not in allowed):
            raise OSError("图片目录含额外文件或链接，已停止删除章节")


def inspect(library, key):
    path = library.checked_path(key)
    if path.is_junction():
        raise OSError("拒绝修改目录联接")
    with_source = ReaderSource(path)
    try:
        pages = with_source.pages
        if path.is_dir():
            _folder_contents(path, pages)
            stamp = [(p["chapter"], p["page"], p["path"], Path(p["path"]).stat().st_size, Path(p["path"]).stat().st_mtime_ns) for p in pages]
        else:
            stamp = (path.stat().st_size, path.stat().st_mtime_ns)
        return dict(chapters=dict(Counter(p["chapter"] for p in pages)),
                    stamp=stamp, pages=[p["chapter"] for p in pages])
    finally:
        with_source.close()


def remap_state(state, chapters, removed):
    kept = [i for i, chapter in enumerate(chapters) if chapter not in removed]
    mapping = {old: new for new, old in enumerate(kept)}
    current = state["page"]
    nearest = next((i for i in kept if i >= current), kept[-1])
    result = dict(page=mapping[nearest], mode=state["mode"],
                  bookmarks=[mapping[i] for i in state["bookmarks"] if i in mapping])
    if 'bookmarkNames' in state:
        result['bookmarkNames'] = {str(mapping[i]): state['bookmarkNames'][str(i)]
                                   for i in state['bookmarks'] if i in mapping and str(i) in state['bookmarkNames']}
    return result


def _copy(source, target, cancelled):
    digest = hashlib.sha256()
    with source, open(target, "xb") as output:
        while block := source.read(65536):
            _check(cancelled)
            output.write(block)
            digest.update(block)
        output.flush()
        os.fsync(output.fileno())
    with open(target, "rb") as saved:
        verify = hashlib.sha256()
        while block := saved.read(65536):
            _check(cancelled)
            verify.update(block)
    if digest.digest() != verify.digest():
        raise OSError("剩余图片保存校验失败，原漫画保留")


def delete_chapters(engine, key, selected, expected, cancelled=lambda: False, progress=lambda text: None):
    with engine.file_operation([key]):
        return _delete_chapters(engine, key, selected, expected, cancelled, progress)


def _delete_chapters(engine, key, selected, expected, cancelled, progress):
    library = engine.library
    if library.error:
        raise OSError(library.error)
    item = library.entries[key]
    if item["id"] and not re.fullmatch(r"[0-9]{1,10}", item["id"]):
        raise ValueError("漫画编号无效，请重新扫描导入")
    current = inspect(library, key)
    if current != expected:
        raise OSError("漫画内容已变化，请重新打开章节列表")
    removed = set(selected)
    if not removed or not removed <= current["chapters"].keys():
        raise ValueError("请勾选有效章节")
    if len(removed) == len(current["chapters"]):
        raise ValueError("至少保留一章；删除整本请使用“删除文件”")
    path = Path(item["path"])
    state = ReaderState(library.path.parent)
    if state.error:
        raise OSError(state.error)
    mapped = remap_state(state.get(key, len(current["pages"])), current["pages"], removed)
    target = path.parent / (f"JM{item['id'] or '0'}-{safe_name(item['title'])}-{uuid.uuid4().hex[:8]}" + ("" if path.is_dir() else ".zip"))
    staging = path.parent / (".chapter-delete-" + uuid.uuid4().hex + ".partial")
    committed = False
    published = False
    try:
        _check(cancelled)
        progress("正在保存并校验保留章节…")
        if item["format"] == "images":
            data, pages = read_album(path)
            kept = [p for p in pages if p["chapter"] not in removed]
            numbers = {c: i + 1 for i, c in enumerate(sorted(current["chapters"].keys() - removed))}
            staging.mkdir()
            records = []
            for index, p in enumerate(kept, 1):
                c = numbers[p["chapter"]]
                relative = image_name(c, p["page"], len(numbers))
                dest = staging / relative
                dest.parent.mkdir(exist_ok=True)
                _copy(open(p["path"], "rb"), dest, cancelled)
                records.append(dict(chapter=c, page=p["page"], file=relative, size=dest.stat().st_size))
                progress(f"校验保留图片 {index}/{len(kept)}")
            metadata = dict(version=2, id=data["id"], title=data["title"], entries=records)
        else:
            with ReaderSourceContext(path) as source, zipfile.ZipFile(staging, "x", zipfile.ZIP_DEFLATED) as output:
                discard = {p["entry"].filename for p in source.pages if p["chapter"] in removed}
                output.comment = source.archive.comment
                copied = 0
                for entry in source.archive.infolist():
                    _check(cancelled)
                    if entry.filename in discard:
                        continue
                    # Preserve every non-page entry, including archive metadata.
                    with source.archive.open(entry) as incoming, output.open(entry, "w") as saved:
                        while block := incoming.read(65536):
                            _check(cancelled)
                            copied += len(block)
                            if copied > MAX_TOTAL_BYTES:
                                raise ValueError("ZIP 保留内容总大小超出支持范围")
                            saved.write(block)
            with zipfile.ZipFile(staging) as archive:
                for entry in archive.infolist():
                    with archive.open(entry) as stream:
                        while stream.read(65536):
                            _check(cancelled)
        _check(cancelled)
        if inspect(library, key) != expected:
            raise OSError("漫画内容已变化，原漫画保留；请重试")
        # Commit is short and cannot be cancelled halfway through metadata changes.
        if target.exists():
            raise FileExistsError("目标文件已存在，未覆盖")
        os.rename(staging, target)
        published = True
        if item["format"] == "images":
            atomic_json(album_index(target), metadata)
            read_album(target)
        new_key = library.key(target)
        state.put(new_key, **mapped)
        with engine.state_lock:
            previous = library.entries.copy()
            affected = [(t, t.result) for t in engine.tasks if t.result and library.key(t.result) == key]
            try:
                library.entries = {new_key if k == key else k: dict(v, path=str(target), chapter_count=len(current["chapters"]) - len(removed)) if k == key else v for k, v in previous.items()}
                library.save()
                for task, _ in affected:
                    task.result = str(target)
                engine.save()
            except Exception:
                library.entries = previous
                for task, result in affected:
                    task.result = result
                try:
                    library.save()
                    engine.save()
                except Exception:
                    committed = True  # Keep both complete copies if rollback cannot persist.
                    raise OSError("记录保存及恢复失败，原漫画和新副本均已保留，请检查写入权限：" + str(target))
                raise
        committed = True
        warning = ""
        try:
            if path.is_dir():
                shutil.rmtree(path)
                album_index(path).unlink(missing_ok=True)
            else:
                path.unlink()
        except OSError as error:
            warning = f"\n剩余章节已保存，但旧文件清理未完成，请手动处理：{path}\n{error}"
        from cover_cache import CoverCache
        CoverCache(library.path.parent).forget(path, item["format"])
        return new_key, f"已从漫画库删除 {len(removed)} 章，保留 {len(current['chapters']) - len(removed)} 章。" + warning
    finally:
        if staging.exists():
            if staging.is_dir():
                shutil.rmtree(staging)
            else:
                staging.unlink()
        if published and not committed:
            if target.is_dir():
                shutil.rmtree(target)
                album_index(target).unlink(missing_ok=True)
            else:
                target.unlink()


class ReaderSourceContext(ReaderSource):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
