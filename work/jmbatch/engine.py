"""Persistent serial queue with killable workers and bounded slow-speed resets."""
from __future__ import annotations

import json
import multiprocessing as mp
import queue
import time
from pathlib import Path

from core import Settings, SpeedWatch, Task, atomic_json
from worker import worker_entry
from library import Library

ACTIVE = {"running", "resetting"}


class Engine:
    def __init__(self, home: Path, notify=lambda message: None, worker_target=worker_entry):
        self.home = home
        self.notify = notify
        self.worker_target = worker_target
        self.tasks: list[Task] = []
        self.settings = Settings()
        self.cookie = ""
        self.running = False
        self.current = None
        self.process = None
        self.channel = None
        self.watch = None
        self.phase = ""
        self.bytes = 0
        self.download_started = 0
        self.next_start = 0
        self.exit_seen = None
        self.last_saved = 0
        self.context = mp.get_context("spawn")
        self.load()
        self.library = Library(home)
        try:
            self.library.sync(self.tasks)
        except OSError as exc:
            self.notify(str(exc))

    def load(self):
        path = self.home / "queue.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            settings = Settings(**data.get("settings", {})).validate()
            settings.format = "images"
            tasks = [Task(**raw) for raw in data.get("tasks", [])]
            for task in tasks:
                Settings(**task.settings).validate()
                if task.status in ACTIVE or task.status == "queued":
                    task.status = "paused"
                    task.phase = "已恢复；点击开始继续"
                task.speed = 0
                if task.status != "done":
                    task.settings.update(format="images", numeric_filename=False, flat_zip=False, keep_images=False)
            self.settings, self.tasks = settings, tasks
        except Exception as exc:
            # Preserve a corrupt queue for recovery instead of overwriting it.
            backup = self.home / f"queue-unreadable-{time.time_ns()}.json"
            path.rename(backup)
            self.notify(f"队列文件无法读取，已备份至 {backup}：{exc}")

    def save(self):
        atomic_json(self.home / "queue.json", {"version": 1, "settings": self.settings.__dict__, "tasks": [t.to_dict() for t in self.tasks]})
        self.last_saved = time.monotonic()

    def add(self, ids, settings: Settings):
        existing = {(t.album_id, t.settings["output"], t.settings["format"]) for t in self.tasks if t.status != "cancelled"}
        count = 0
        for album_id in ids:
            key = (album_id, settings.output, settings.format)
            if key not in existing:
                self.tasks.append(Task(album_id, dict(settings.__dict__)))
                existing.add(key)
                count += 1
        self.settings = settings
        self.save()
        return count

    def start(self):
        for task in self.tasks:
            if task.status == "paused":
                task.status = "queued"
                task.phase = "排队中"
        self.running = True
        self.save()

    def pause(self):
        self.running = False
        if self.current:
            self._stop_process()
            self.current.status = "paused"
            self.current.phase = "已暂停，保留已验证图片"
            self.current.speed = 0
            self.current = None
        for task in self.tasks:
            if task.status == "queued":
                task.status = "paused"
                task.phase = "已暂停"
        self.save()

    def cancel(self, keys):
        for task in self.tasks:
            if task.key not in keys or task.status in ("done", "cancelled"):
                continue
            if task is self.current:
                self._stop_process()
                self.current = None
            task.status = "cancelled"
            task.speed = 0
            task.phase = "已取消，缓存保留供重试"
        self.save()

    def retry(self, keys, settings: Settings | None = None):
        count = 0
        for task in self.tasks:
            if task.key in keys and task.status in ("failed", "cancelled", "paused"):
                if settings:
                    # Keep original output and format so resume uses its own cache.
                    task.settings.update({k: v for k, v in settings.__dict__.items() if k not in ("output", "format")})
                task.status = "queued"
                task.phase = "等待重试"
                task.settings["format"] = "images"
                task.error = ""
                task.resets = 0
                count += 1
        self.save()
        return count

    def _stop_process(self):
        if self.process:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1)
            self.process.close()
            self.process = None
        if self.channel:
            self.channel.close()
            self.channel = None
        self.exit_seen = None

    def _launch(self, task: Task, now):
        self.current = task
        task.status = "running"
        task.phase = "正在启动下载进程"
        task.done = task.cached = 0
        task.total = task.image_bytes = task.result_bytes = 0
        self.download_started = 0
        task.error = ""
        task.metrics = {}
        task.speed = 0
        self.phase = "metadata"
        self.bytes = 0
        self.watch = SpeedWatch(Settings(**task.settings), now)
        self.channel = self.context.Queue()
        self.process = self.context.Process(target=self.worker_target, args=(task.to_dict(), self.cookie, self.channel), daemon=True)
        try:
            self.process.start()
        except Exception as exc:
            self.process = None
            self.channel.close()
            self.channel = None
            self._fail(f"无法启动下载进程：{type(exc).__name__}: {exc}")
            return
        self.notify(f"JM{task.album_id} 开始下载（{task.settings['format'].upper()}）")
        self.save()

    def _fail(self, message):
        task = self.current
        self._stop_process()
        task.status = "failed"
        task.error = message
        task.phase = "下载失败，点击任务查看原因"
        task.speed = 0
        self.notify(f"JM{task.album_id} 失败：{message}")
        self.current = None
        self.save()

    def _handle(self, event, now):
        task = self.current
        kind = event.get("type")
        if kind == "title":
            task.title = event["title"]
        elif kind == "route":
            task.phase = event["message"]
        elif kind == "metadata":
            task.phase = event["message"]
            self.watch.last_progress = now
        elif kind == "phase":
            self.phase = event["phase"]
            task.phase = event["message"]
            if self.phase in ("download", "page_retry"):
                task.total = event["total"]
                self.watch = SpeedWatch(Settings(**task.settings), now)
                if self.phase == "download":
                    self.download_started = now
        elif kind == "progress":
            task.done, task.total, task.cached = event["done"], event["total"], event["cached"]
            self.bytes = event["bytes"]
            task.image_bytes = event.get("image_bytes", task.image_bytes)
            task.phase = event["message"]
            self.watch.last_progress = now
        elif kind == "export_progress":
            task.phase = event["message"]
        elif kind == "error":
            self._fail(event["error"])
        elif kind == "metrics":
            task.metrics = event["metrics"]
        elif kind == "done":
            task.status = "done"
            task.done = task.total = event["total"]
            task.result = event["path"]
            task.result_bytes = event.get("result_bytes", 0)
            task.phase = event["message"]
            task.speed = 0
            self.notify(f"JM{task.album_id} 下载完成：{task.result}")
            try:
                self.library.sync(self.tasks)
            except OSError as exc:
                self.notify(f"文件已下载，但漫画列表保存失败：{exc}")
            if task.metrics:
                labels = {"startup": "准备", "metadata": "连接/元数据", "download": "图片下载与处理", "verify": "导出前校验", "export": "导出与清理"}
                stages = task.metrics.get("stages", {})
                text = "，".join(f"{labels.get(key, key)} {seconds:.2f}s" for key, seconds in stages.items())
                self.notify(f"JM{task.album_id} 本轮耗时 {task.metrics['total_seconds']:.2f}s：{text}")
            self._stop_process()
            self.current = None
            self.save()

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if self.current and self.current.status == "resetting":
            if now >= self.next_start:
                self._launch(self.current, now)
            return
        if self.current and self.channel:
            for _ in range(300):
                try:
                    event = self.channel.get_nowait()
                except queue.Empty:
                    break
                self._handle(event, now)
                if self.current is None:
                    break
        if self.current and self.process:
            if not self.process.is_alive():
                # Allow multiprocessing's feeder to deliver its terminal event.
                if self.exit_seen is None:
                    self.exit_seen = now
                elif now - self.exit_seen > 1:
                    code = self.process.exitcode
                    self._fail(f"下载进程意外退出（退出码 {code}）。可能是依赖、系统资源或安全软件拦截；已保留缓存，可重试。")
            elif self.phase == "page_retry":
                self.current.speed = 0
                if now - self.watch.last_progress >= max(self.watch.settings.stall_seconds, self.watch.settings.timeout * (self.watch.settings.request_retries + 1) * 2):
                    self._fail("单页重试超时；已保留其他图片，请查看失败页后重试任务。")
            elif self.phase in ("metadata", "download"):
                speed, reason = self.watch.sample(now, self.bytes)
                self.current.speed = speed
                # A slow byte rate is only meaningful in the image phase.
                if self.phase == "metadata" and now - self.watch.last_progress < self.watch.settings.stall_seconds:
                    reason = None
                if reason:
                    task = self.current
                    if task.resets >= task.settings["max_resets"]:
                        self._fail(f"{reason}；已达到自动重置上限 {task.settings['max_resets']} 次。请检查网络或调低慢速阈值后重试。")
                    else:
                        self._stop_process()
                        task.resets += 1
                        task.status = "resetting"
                        task.speed = 0
                        delay = min(30, 3 * 2 ** (task.resets - 1))
                        task.phase = f"{reason}；{delay} 秒后重建连接（{task.resets}/{task.settings['max_resets']}）"
                        self.notify(f"JM{task.album_id} 自动重置：{task.phase}")
                        self.next_start = now + delay
                        self.save()
            else:
                self.current.speed = 0
        if self.running and self.current is None:
            task = next((t for t in self.tasks if t.status == "queued"), None)
            if task:
                self._launch(task, now)
            else:
                self.running = False
                self.notify("下载完成" if self.tasks and all(t.status == "done" for t in self.tasks)
                            else "本轮队列已结束；失败任务可选中后重试。")
                self.save()
        if self.current and now - self.last_saved > 5:
            self.save()

    def close(self):
        self.pause()
