"""One isolated process per album. No UI imports; reusable by other front ends."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path

from core import Settings, ZIP_LAYOUT_VERSION, atomic_json, explain_error, export_images, task_cache, verify_image


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
    if marker.exists():
        completed = json.loads(marker.read_text(encoding="utf-8"))
        artifact = Path(completed["path"])
        if settings.format == "images" and completed.get("format") == "images" and artifact.parent.resolve() == output.resolve():
            from albums import read_album
            try:
                _, saved = read_album(artifact, verify=True)
            except (OSError, ValueError, KeyError):
                pass
            else:
                emit({"type": "done", "path": str(artifact), "total": len(saved),
                      "result_bytes": sum(Path(e["path"]).stat().st_size for e in saved), "message": "下载完成"})
                return
        if (artifact.is_file() and artifact.parent.resolve() == output.resolve()
                and settings.format != "images"
                and completed.get("numeric_filename", False) == settings.numeric_filename
                and (settings.format != "zip" or (completed.get("flat_zip", False) == settings.flat_zip
                     and (not settings.flat_zip or completed.get("zip_layout_version", 0) == ZIP_LAYOUT_VERSION)))):
            if artifact.suffix == ".pdf":
                from pypdf import PdfReader
                with artifact.open("rb") as stream:
                    valid = len(PdfReader(stream).pages) == completed["images"]
            else:
                import zipfile
                with zipfile.ZipFile(artifact) as archive:
                    valid = archive.testzip() is None and len(archive.infolist()) == completed["images"] + (0 if settings.flat_zip else 1)
            if valid:
                emit({"type": "done", "path": str(artifact), "total": completed["images"], "result_bytes": artifact.stat().st_size, "message": "下载完成"})
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

        def create_client(self):
            return client_factory() if client_factory else self.option.new_jm_client(domain_retry_strategy=route_strategy)

        def download_by_album_detail(self, album):
            album.save_path = str(cache / "images")
            emit({"type": "title", "title": album.name})
            self.before_album(album)
            photos = list(album)
            if not photos:
                raise ValueError("该编号没有可下载的章节。")
            # Hydrate all chapter metadata before displaying an exact total.
            for index, photo in enumerate(photos, 1):
                self.client.check_photo(photo)
                if len(photo) == 0:
                    raise ValueError(f"第 {index} 章没有图片，可能是访问权限或服务端数据异常。")
                self.chapter_numbers[str(photo.id)] = index
                self.expected_chapters[index] = len(photo)
                self.expected += len(photo)
                emit({"type": "metadata", "message": f"读取章节 {index}/{len(photos)}"})
            emit({"type": "phase", "phase": "download", "message": "正在下载图片", "total": self.expected})
            for photo in photos:
                self.download_by_photo_detail(photo)
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
                    raise IOError(f"第 {chapter} 章第 {image.index} 页下载失败（单页重试结束）：{error}；已保留其他图片，未生成成品") from error
            elif self.failed_pages:
                positions = "、".join(f"第 {self.chapter_numbers[str(im.from_photo.id)]} 章第 {im.index} 页" for im, _ in self.failed_pages[:5])
                raise IOError(f"{len(self.failed_pages)} 页下载失败：{positions}；{self.failed_pages[0][1]}；已保留成功图片，未生成成品")
            self.after_album(album)

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
        raise ValueError(f"图片不完整：预期 {downloader.expected} 张，实际 {len(entries)} 张。未生成成品。")
    for chapter, count in downloader.expected_chapters.items():
        if [e["page"] for e in entries if e["chapter"] == chapter] != list(range(1, count + 1)):
            raise ValueError(f"第 {chapter} 章存在缺页或重复页，未生成成品。")
    if settings.format == "images":
        from albums import save_album
        final, result_size = save_album(task, album.name, entries, emit)
    else:
        final = export_images(task, album.name, entries, emit)
        result_size = final.stat().st_size
    warning = ""
    if not settings.keep_images:
        try:
            # This path is solely owned by this task; completed.json remains.
            images = cache / "images"
            if images.is_symlink() or images.resolve().parent != cache.resolve():
                raise ValueError("图片缓存路径异常")
            shutil.rmtree(images)
        except (OSError, ValueError) as exc:
            warning = "成品已保存，但图片缓存清理失败：" + str(exc)
    emit({"type": "done", "path": str(final), "total": len(entries), "result_bytes": result_size, "message": "下载完成" + ("；" + warning if warning else "")})


def worker_entry(task: dict, cookie: str, channel):
    # Dependency debug messages may include signed URLs; never persist them.
    import sys
    with open(os.devnull, "w", encoding="utf-8") as sink:
        sys.stdout = sink
        sys.stderr = sink
        try:
            run_download(task, cookie, channel.put)
        except Exception as exc:
            channel.put({"type": "error", "error": explain_error(exc, cookie)})
