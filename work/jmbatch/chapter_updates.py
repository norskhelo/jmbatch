"""Check album catalogues without downloading pages or consuming declined updates."""
import json
import re
from pathlib import Path

from core import atomic_json


class UpdateHistory:
    def __init__(self, home):
        self.path = Path(home) / "chapter-updates.json"
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except (ValueError, OSError) as error:
            raise OSError("章节更新记录无法读取，原文件已保留。") from error
        if not isinstance(self.data, dict):
            raise OSError("章节更新记录无法读取，请保留原文件后重试。")
        if any(not isinstance(item, dict) or any(not isinstance(item.get(k), list) or
                any(not isinstance(v, str) for v in item[k]) for k in ("known", "anchors"))
               for item in self.data.values()):
            raise OSError("章节更新记录格式无效，原文件已保留。")

    def record(self, tasks):
        before = json.dumps(self.data, sort_keys=True)
        for task in tasks:
            if task.status != "done" or not task.result:
                continue
            item = self.data.setdefault(str(task.album_id), {"known": [], "anchors": []})
            catalog = getattr(task, "chapter_options", [])
            field = "known" if catalog else "anchors"
            item[field] = sorted(set(item[field]) | {c["id"] for c in (catalog or getattr(task, "selected_chapters", []))})
        if json.dumps(self.data, sort_keys=True) != before:
            atomic_json(self.path, self.data)

    def compare(self, album_id, catalog):
        validate_catalog(catalog)
        item = self.data.setdefault(album_id, {"known": [], "anchors": []})
        known = set(item["known"])
        initialized = False
        if not known:
            # Old all-chapter downloads only retained their selected IDs.
            # Infer the old prefix by matching IDs, never by comparing ID values.
            positions = [i for i, c in enumerate(catalog) if c["id"] in item["anchors"]]
            limit = max(positions) + 1 if positions else len(catalog)
            known = {c["id"] for c in catalog[:limit]}
            initialized = not positions
            item["known"] = sorted(known)
            atomic_json(self.path, self.data)
        return [dict(c) for c in catalog if c["id"] not in known], initialized


def validate_catalog(catalog):
    if not catalog or any(not re.fullmatch(r"[0-9]{1,10}", str(c["id"])) or c["number"] < 1 for c in catalog):
        raise ValueError("服务端章节目录无效，请稍后重试。")
    if len({c["id"] for c in catalog}) != len(catalog):
        raise ValueError("章节编号重复，请稍后重试。")


def fetch_catalog(album_id, settings, cookie, cancelled):
    if not re.fullmatch(r"[0-9]{1,10}", album_id):
        raise ValueError("这条漫画记录没有有效的 JM 编号，无法检查更新。")
    import jmcomic
    from worker import parse_cookies
    from network_routes import make_strategy
    metadata = {"timeout": settings.timeout}
    cookies = parse_cookies(cookie)
    if cookies:
        metadata["cookies"] = cookies
    option = jmcomic.JmOption.construct({
        "log": False, "client": {"impl": "api", "retry_times": settings.request_retries,
        "postman": {"type": "curl_cffi_session", "meta_data": metadata}}})
    if cancelled.is_set():
        raise ValueError("检查已取消。")
    client = option.new_jm_client(domain_retry_strategy=make_strategy(lambda text: None))
    try:
        album = client.get_album_detail(album_id)
        catalog = [{"id": str(photo.id), "number": i, "title": str(photo.name or f"第 {i} 章")}
                   for i, photo in enumerate(album, 1)]
        validate_catalog(catalog)
        return catalog
    finally:
        close = getattr(getattr(client, "postman", None), "close", None)
        if callable(close):
            close()


def show(window, key):
    entry = dict(window.library.entries[key])
    settings = window.app.current_settings()
    cookie = window.app.engine.cookie
    def check():
        catalog = fetch_catalog(entry["id"], settings, cookie, window.cancelled)
        if window.cancelled.is_set():
            return None
        return catalog

    def finished(result):
        if result is None or window.cancelled.is_set():
            window.status.set("检查已取消，未加入下载。")
            return
        catalog = result
        history = UpdateHistory(window.app.engine.home)
        history.record(window.app.engine.tasks)
        new, initialized = history.compare(entry["id"], catalog)
        if initialized:
            text = "缺少原下载章节记录，已记录当前目录作为检查起点；以后可检查新增章节。"
        elif not new:
            text = "检查完成，暂无新章节。"
        else:
            preview = "\n".join(f"第 {c['number']} 章 · {c['title']}" for c in new[:20])
            if len(new) > 20:
                preview += f"\n……另 {len(new)-20} 章"
            text = f"发现 {len(new)} 个新章节。\n\n{preview}\n\n是否使用正常下载功能下载？\n保存为独立漫画，原漫画保留。\n保存目录：{settings.output}\n格式：{settings.format.upper()}"
            if window.messagebox.askyesno("漫画章节更新", text, parent=window.window):
                window.app.engine.add_chapter_update(entry["id"], catalog, new, settings)
                window.app.render()
                window.status.set(f"已将 {len(new)} 个新章节加入正常下载队列。")
            else:
                window.status.set("已暂不下载，下次检查仍会提示这些新章节。")
            return
        window.status.set(text)
        window.messagebox.showinfo("漫画章节更新", text, parent=window.window)

    window.run(check, finished)
