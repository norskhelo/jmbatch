"""One isolated process per album. No UI imports; reusable by other front ends."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path

from core import Settings, ZIP_LAYOUT_VERSION, atomic_json, explain_error, export_images, task_cache, verify_image
from chapters import ChapterChoiceRequired, resolve_chapters
from chapter_metadata import MetadataCache, cache_scope, hydrate


def parse_cookies(text: str):
    cookies = {}
    for part in text.split(";"):
        if "=" in part:
            key, value = part.strip().split("=", 1)
            if key.strip():
                cookies[key.strip()] = value.strip()
    if text.strip() and not cookies:
        raise ValueError("Cookie 格式无效，请使用 key=value; key2=value2 格式。")
    return cookies


def run_download(task: dict, cookie: str, emit, client_factory=None):
    started_at = time.perf_counter()
    stage_started = started_at
    stage = "startup"
    stage_seconds = {}
    received_bytes = 0
    output_event = emit

    def emit(event):
        nonlocal stage, stage_started, received_bytes
        now = time.perf_counter()
        if event.get("type") == "progress":
            received_bytes = event["bytes"]
        if event.get("type") in ("phase", "done"):
            stage_seconds[stage] = stage_seconds.get(stage, 0) + now - stage_started
            stage, stage_started = event.get("phase", "done"), now
        if event.get("type") == "done":
            output_event({"type": "metrics", "metrics": {
                "total_seconds": round(now - started_at, 3),
                "stages": {key: round(value, 3) for key, value in stage_seconds.items()},
                "downloaded_image_bytes": received_bytes,
            }})
        output_event(event)

    import jmcomic
    from network_routes import HttpFailure, make_strategy
    route_strategy = make_strategy(lambda message: emit({"type": "route", "message": message}))

    settings = Settings(**task["settings"]).validate()
    output = Path(settings.output)
    output.mkdir(parents=True, exist_ok=True)
    cache = task_cache(task)
    cache.mkdir(parents=True, exist_ok=True)
    marker = cache / "completed.json"

    def finish(artifact, total, size):
        from cache_cleanup import clean_task
        emit({"type": "phase", "phase": "cleanup", "message": "正在清理下载临时缓存"})
        cleaned = clean_task(task, completed=True, progress=lambda r: emit({
            "type": "export_progress", "message": r.message(True)}))
        notice = cleaned.message(True) if cleaned.files or cleaned.errors else ""
        emit({"type": "done", "path": str(artifact), "total": total, "result_bytes": size,
              "message": "下载完成" + ("；" + notice if notice else ""), "cleanup": notice})

    if marker.exists():
        completed = json.loads(marker.read_text(encoding="utf-8"))
        artifact = Path(completed["path"])
        if settings.format == "images" and completed.get("format") == "images" and completed.get("album_layout_version") == 2 and artifact.parent.resolve() == output.resolve():
            from albums import read_album
            try:
                _, saved = read_album(artifact, verify=True)
            except (OSError, ValueError, KeyError):
                pass
            else:
                finish(artifact, len(saved), sum(Path(e["path"]).stat().st_size for e in saved))
                return
        if (artifact.is_file() and artifact.parent.resolve() == output.resolve()
                and settings.format != "images"
                and completed.get("numeric_filename", False) == settings.numeric_filename
                and (settings.format != "zip" or completed.get("zip_layout_version", 0) == ZIP_LAYOUT_VERSION)):
            if artifact.suffix == ".pdf":
                from pypdf import PdfReader
                with artifact.open("rb") as stream:
                    valid = len(PdfReader(stream).pages) == completed["images"]
            else:
                import zipfile
                with zipfile.ZipFile(artifact) as archive:
                    valid = archive.testzip() is None and len(archive.infolist()) == completed["images"]
            if valid:
                finish(artifact, completed["images"], artifact.stat().st_size)
                return
    if shutil.disk_usage(output).free < 256 * 1024 ** 2:
        raise OSError(28, "下载前至少需要 256 MB 可用空间。")
    metadata = {"timeout": settings.timeout}
    cookies = parse_cookies(cookie)
    if cookies:
        metadata["cookies"] = cookies
    option = jmcomic.JmOption.construct({
        "log": False,
        "client": {"impl": "api", "retry_times": settings.request_retries,
                   "postman": {"type": "curl_cffi_session", "meta_data": metadata}},
        "dir_rule": {"rule": "Bd_Pid", "base_dir": str(cache / "images")},
        "download": {"cache": True, "image": {"decode": True, "suffix": ".jpg"},
                     "threading": {"image": settings.threads, "photo": 1}},
    })

    class ObservedDownloader(jmcomic.JmDownloader):
        def __init__(self, opt):
            super().__init__(opt)
            self.progress_lock = threading.Lock()
            self.expected = 0
            self.completed = 0
            self.cached_count = 0
            self.network_bytes = 0
            self.image_bytes = 0
            self.entries = []
            self.chapter_numbers = {}
            self.expected_chapters = {}
            self.failed_pages = []
            self.verified_cache = set()

        def create_client(self):
            return client_factory() if client_factory else self.option.new_jm_client(domain_retry_strategy=route_strategy)

        def download_by_album_detail(self, album):
            album.save_path = str(cache / "images")
            emit({"type": "title", "title": album.name})
            self.before_album(album)
            photos = list(album)
            if not photos:
                raise ValueError("该编号没有可下载的章节。")
            catalog = [{"id": str(photo.id), "number": index, "title": str(photo.name or f"第 {index} 章")}
                       for index, photo in enumerate(photos, 1)]
            chosen = resolve_chapters(catalog, task.get("selected_chapters"), settings.download_all_chapters)
            task["selected_chapters"] = chosen
            emit({"type": "chapter_plan", "chapters": chosen})
            available = {str(photo.id): photo for photo in photos}
            photos = [available[item["id"]] for item in chosen]
            details = MetadataCache(cache / 'chapters', cache_scope(album, cookie))
            hydrate(photos, details, self.client.check_photo,
                    lambda done, total, cached: emit({'type': 'metadata',
                        'message': f'读取所选章节 {done}/{total}（复用 {cached} 章，最多 {settings.chapter_workers} 章并行）'}),
                    workers=settings.chapter_workers)
            for item, photo in zip(chosen, photos):
                index = item["number"]
                if len(photo) == 0:
                    raise ValueError(f"第 {index} 章没有图片，可能是访问权限或服务端数据异常。")
                self.chapter_numbers[str(photo.id)] = index
                self.expected_chapters[index] = len(photo)
                self.expected += len(photo)
            self.restore_cache(photos)
            emit({"type": "phase", "phase": "download", "message": f"继续下载剩余 {self.expected - self.completed} 张图片", "total": self.expected})
            for photo in photos:
                self.download_by_photo_detail(photo)
            if self.failed_pages:
                # A stale image list/CDN may be responsible. Refresh only failed
                # chapters on retry; successful chapters keep their metadata.
                details.invalidate({str(im.from_photo.id): im.from_photo for im, _ in self.failed_pages}.values())
            if len(self.failed_pages) == 1:
                image, error = self.failed_pages[0]
                chapter = self.chapter_numbers[str(image.from_photo.id)]
                for attempt in range(1, 3):
                    if (isinstance(error, (PermissionError, MemoryError)) or getattr(error, "errno", None) in (13, 28)
                            or isinstance(error, HttpFailure) and error.status < 500 or "429" in str(error)):
                        break
                    emit({"type": "phase", "phase": "page_retry", "total": self.expected,
                          "message": f"仅第 {chapter} 章第 {image.index} 页失败，单独重试 {attempt}/2（其他图片保留）"})
                    client = None
                    try:
                        client = client_factory() if client_factory else self.option.new_jm_client(domain_retry_strategy=route_strategy)
                        self._download_image(image, client)
                        self.failed_pages.clear()
                        break
                    except Exception as retry_error:
                        error = retry_error
                    finally:
                        if client is not None:
                            close = getattr(getattr(client, "postman", None), "close", None)
                            if callable(close):
                                try:
                                    close()
                                except Exception:
                                    pass
                if self.failed_pages:
                    raise IOError(f"第 {chapter} 章第 {image.index} 页下载失败（单页重试结束）：{error}；已保留其他图片，未生成完整文件") from error
            elif self.failed_pages:
                positions = "、".join(f"第 {self.chapter_numbers[str(im.from_photo.id)]} 章第 {im.index} 页" for im, _ in self.failed_pages[:5])
                raise IOError(f"{len(self.failed_pages)} 页下载失败：{positions}；{self.failed_pages[0][1]}；已保留成功图片，未生成完整文件")
            self.after_album(album)

        def restore_cache(self, photos):
            # Cache validation is local work, not a slow network transfer. Publish a
            # single reconciled snapshot so resumed progress never counts from zero.
            emit({"type": "phase", "phase": "cache", "message": "正在校验已有图片，保留原进度"})
            checked = 0
            last_update = time.monotonic()
            for photo in photos:
                chapter = self.chapter_numbers[str(photo.id)]
                for page in range(1, len(photo) + 1):
                    target = cache / "images" / f"{chapter:04d}" / f"{page:05d}.jpg"
                    if target.is_file():
                        try:
                            verify_image(target)
                        except (OSError, ValueError, SyntaxError):
                            pass  # Missing/broken images are repaired by the download path.
                        else:
                            self.verified_cache.add((chapter, page))
                            self.entries.append({"chapter": chapter, "page": page, "path": str(target)})
                            self.image_bytes += target.stat().st_size
                    checked += 1
                    now = time.monotonic()
                    if now - last_update >= .25 or checked == self.expected:
                        emit({"type": "metadata", "message": f"校验已有图片 {checked}/{self.expected}，已确认 {len(self.verified_cache)} 张可复用"})
                        last_update = now
            self.completed = self.cached_count = len(self.verified_cache)
            emit({"type": "progress", "done": self.completed, "total": self.expected,
                  "cached": self.cached_count, "bytes": 0, "image_bytes": self.image_bytes,
                  "message": f"已恢复 {self.completed}/{self.expected} 张图片，只下载缺失或损坏页"})

        def do_filter(self, detail):
            if not detail.is_photo():
                return super().do_filter(detail)
            chapter = self.chapter_numbers[str(detail.id)]
            pending = []
            for image in detail:
                if (chapter, image.index) not in self.verified_cache:
                    pending.append(image)
                    continue
                # Preserve jmcomic's success bookkeeping without scheduling cached pages.
                target = cache / "images" / f"{chapter:04d}" / f"{image.index:05d}.jpg"
                image.save_path = str(target)
                image.cache = image.exists = True
                self.before_image(image, str(target))
                self.after_image(image, str(target))
            return pending

        def download_by_image_detail(self, image):
            try:
                self._download_image(image, self.client)
            except Exception as error:
                with self.progress_lock:
                    self.failed_pages.append((image, error))

        def _download_image(self, image, client):
            chapter = self.chapter_numbers[str(image.from_photo.id)]
            target = cache / "images" / f"{chapter:04d}" / f"{image.index:05d}.jpg"
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save_path = str(target)
            image.cache = True
            image.exists = target.is_file()
            self.before_image(image, str(target))
            if image.exists:
                try:
                    verify_image(target)
                except Exception:
                    target.unlink()
                    image.exists = False
            if not image.exists:
                if shutil.disk_usage(output).free < 32 * 1024 ** 2:
                    raise OSError(28, "剩余磁盘空间低于 32 MB，已停止写入图片。")
                partial = target.with_name(target.stem + ".partial.jpg")
                try:
                    client.download_by_image_detail(image, str(partial), decode_image=True)
                    verify_image(partial)
                    os.replace(partial, target)
                finally:
                    partial.unlink(missing_ok=True)
            self.after_image(image, str(target))
            with self.progress_lock:
                image_size = target.stat().st_size
                self.image_bytes += image_size
                self.completed += 1
                if image.exists:
                    self.cached_count += 1
                else:
                    self.network_bytes += image_size
                self.entries.append({"chapter": chapter, "page": image.index, "path": str(target)})
                emit({"type": "progress", "done": self.completed, "total": self.expected,
                      "cached": self.cached_count, "bytes": self.network_bytes, "image_bytes": self.image_bytes,
                      "message": f"第 {chapter} 章 · 图片 {image.index}/{len(image.from_photo)}"})

    emit({"type": "phase", "phase": "metadata", "message": "正在连接并读取漫画信息"})
    album, downloader = jmcomic.download_album(task["album_id"], option, downloader=ObservedDownloader, check_exception=True)
    entries = sorted(downloader.entries, key=lambda x: (x["chapter"], x["page"]))
    if len(entries) != downloader.expected:
        raise ValueError(f"图片不完整：预期 {downloader.expected} 张，实际 {len(entries)} 张。未生成完整文件。")
    for chapter, count in downloader.expected_chapters.items():
        if [e["page"] for e in entries if e["chapter"] == chapter] != list(range(1, count + 1)):
            raise ValueError(f"第 {chapter} 章存在缺页或重复页，未生成完整文件。")
    if settings.format == "images":
        from albums import save_album
        final, result_size = save_album(task, album.name, entries, emit)
    else:
        final = export_images(task, album.name, entries, emit)
        result_size = final.stat().st_size
    finish(final, len(entries), result_size)


def worker_entry(task: dict, cookie: str, channel):
    # Dependency debug messages may include signed URLs; never persist them.
    import sys
    with open(os.devnull, "w", encoding="utf-8") as sink:
        sys.stdout = sink
        sys.stderr = sink
        try:
            run_download(task, cookie, channel.put)
        except ChapterChoiceRequired as choice:
            channel.put({"type": "chapters", "chapters": choice.chapters})
        except Exception as exc:
            channel.put({"type": "error", "error": explain_error(exc, cookie)})
