"""Persistent catalogue of completed exports, separate from the download queue."""
from __future__ import annotations

import json
import os
import re
import time
import shutil
from pathlib import Path

from core import atomic_json


class Library:
    def __init__(self, home):
        self.path = Path(home) / "library.json"
        self.entries = {}
        self.error = ""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("version") != 1 or not isinstance(data["entries"], dict):
                    raise ValueError("目录格式无效")
                self.entries = data["entries"]
                for key, item in self.entries.items():
                    if key != self.key(item["path"]) or not isinstance(item["favorite"], bool):
                        raise ValueError("漫画记录无效")
                    for field in ("id", "title", "root", "format"):
                        if not isinstance(item[field], str):
                            raise ValueError("漫画记录无效")
            except Exception as exc:
                self.entries = {}
                self.error = f"已下载漫画列表无法读取，原文件已保留；本次禁止修改列表：{exc}"

    @staticmethod
    def key(path):
        return os.path.normcase(os.path.abspath(path))

    def save(self):
        if self.error:
            raise OSError(self.error)
        atomic_json(self.path, {"version": 1, "entries": self.entries})

    def sync(self, tasks):
        if self.error:
            raise OSError(self.error)
        previous_entries = self.entries.copy()
        changed = False
        for task in tasks:
            if task.status != "done" or not task.result:
                continue
            key = self.key(task.result)
            previous = self.entries.get(key, {})
            item = dict(id=str(task.album_id), title=task.title, path=os.path.abspath(task.result),
                        root=os.path.abspath(task.settings["output"]), format=task.settings["format"],
                        favorite=previous.get("favorite", False), added=previous.get("added", time.time()))
            if item != previous:
                self.entries[key] = item
                changed = True
        if changed:
            try:
                self.save()
            except Exception:
                self.entries = previous_entries
                raise

    def select(self, query="", favorites=False):
        query = query.strip().casefold()
        return [(key, item) for key, item in reversed(list(self.entries.items()))
                if (not favorites or item["favorite"]) and
                (not query or query in (item["id"] + " " + item["title"] + " " + Path(item["path"]).name).casefold())]

    def favorite(self, key):
        item = self.entries[key]
        old = item["favorite"]
        item["favorite"] = not old
        try:
            self.save()
        except Exception:
            item["favorite"] = old
            raise

    def set_favorites(self, keys, value):
        previous = self.entries.copy()
        for key in dict.fromkeys(keys):
            if key in self.entries:
                self.entries[key] = dict(self.entries[key], favorite=bool(value))
        try:
            self.save()
        except Exception:
            self.entries = previous
            raise

    @staticmethod
    def discover(folder, cancelled=None):
        """Read only the selected folder; skip links, directories and partial exports."""
        if not str(folder).strip():
            raise OSError("请先设置保存目录")
        root = Path(folder).resolve(strict=True)
        if not root.is_dir():
            raise OSError("保存目录不存在或不是文件夹")
        found, skipped = [], 0
        with os.scandir(root) as files:
            for entry in files:
                if cancelled and cancelled.is_set():
                    raise InterruptedError("扫描已取消，未导入文件")
                if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                    from albums import MANIFEST
                    if ".partial" in entry.name or not ((Path(entry.path) / MANIFEST).is_file() or re.fullmatch(r"JM[0-9]{1,10}-.*-[0-9a-f]{8}", entry.name)):
                        if entry.name.lower().endswith((".pdf", ".zip")):
                            skipped += 1
                        continue
                    try:
                        from albums import read_album
                        data, _ = read_album(entry.path)
                        found.append(dict(id=str(data["id"]), title=data["title"], path=entry.path, root=str(root), format="images", favorite=False, added=time.time()))
                    except (OSError, ValueError, KeyError):
                        skipped += 1
                    continue
                if not entry.name.lower().endswith((".pdf", ".zip")):
                    continue
                try:
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False) or entry.stat(follow_symlinks=False).st_size == 0:
                        skipped += 1
                        continue
                    path = Path(entry.path)
                    match = re.match(r"^(?:JM)?([0-9]{3,10})(?=$|[\s_.-])", path.stem, re.I)
                    found.append(dict(id=match[1] if match else "", title=path.stem,
                                      path=str(path), root=str(root), format=path.suffix[1:].lower(),
                                      favorite=False, added=time.time()))
                except OSError:
                    skipped += 1
        return found, skipped

    def import_found(self, found):
        if self.error:
            raise OSError(self.error)
        previous = self.entries.copy()
        identities = {os.path.normcase(os.path.realpath(e["path"])) for e in self.entries.values()}
        added = 0
        for item in found:
            identity = os.path.normcase(os.path.realpath(item["path"]))
            if identity in identities:
                continue
            self.entries[self.key(item["path"])] = item
            identities.add(identity)
            added += 1
        try:
            if added:
                self.save()
        except Exception:
            self.entries = previous
            raise
        return added

    def checked_path(self, key):
        item = self.entries[key]
        path, root = Path(item["path"]), Path(item["root"])
        if (item["format"] != "images" and path.suffix.lower() not in (".pdf", ".zip")) or path.is_symlink():
            raise OSError("只允许操作记录中的 PDF / ZIP 普通文件")
        if path.resolve().parent != root.resolve() or path.parent.absolute() != root.absolute():
            raise OSError("文件已离开原保存目录，已停止操作")
        if item["format"] == "images":
            from albums import read_album
            read_album(path)
            return path
        if not path.is_file():
            raise FileNotFoundError("文件不存在、已移动，或保存目录暂时不可用")
        return path

    def remove(self, key, tasks, delete_file=False):
        if self.error:
            raise OSError(self.error)
        item = self.entries[key]
        # Do not race a task which may currently publish into the same directory.
        if any(t.status in ("queued", "running", "resetting") and
               self.key(t.settings["output"]) == self.key(item["root"]) and
               str(t.album_id) == item["id"] for t in tasks):
            raise OSError("这本漫画仍有待下载或进行中的任务，请先暂停或取消")
        if delete_file:
            target = self.checked_path(key)
            if item["format"] == "images":
                # checked_path verified the absolute direct child of the recorded root.
                # Reject foreign files/links before recursive removal of an album.
                from albums import read_album, MANIFEST
                _, images = read_album(target)
                allowed = {Path(e["path"]).absolute() for e in images} | {(target / MANIFEST).absolute()}
                allowed_dirs = {Path(e["path"]).parent.absolute() for e in images}
                for child in target.rglob("*"):
                    if child.is_symlink() or (child.is_file() and child.absolute() not in allowed) or (child.is_dir() and child.absolute() not in allowed_dirs):
                        raise OSError("图片目录含额外文件或链接，已停止删除；请手动处理")
                shutil.rmtree(target)
            else:
                target.unlink()
        for task in tasks:
            if task.result and self.key(task.result) == key:
                task.result = ""
                if delete_file:
                    task.status = "cancelled"
                    task.phase = "成品已删除，可重试下载"
        previous = self.entries.pop(key)
        try:
            self.save()
        except Exception:
            self.entries[key] = previous
            if delete_file:
                raise OSError("文件已删除，但漫画列表保存失败；请检查磁盘空间与写入权限")
            raise

    def remove_many(self, keys, tasks, delete_file=False, cancelled=None, progress=lambda done, total: None):
        keys = list(dict.fromkeys(keys))
        done, errors = [], []
        for index, key in enumerate(keys):
            if cancelled and cancelled.is_set():
                break
            try:
                self.remove(key, tasks, delete_file)
                done.append(key)
            except Exception as exc:
                errors.append((key, str(exc)))
            progress(index + 1, len(keys))
        return done, errors, len(keys) - len(done) - len(errors)


from library_ui import LibraryWindow
