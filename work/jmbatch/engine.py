"""Persistent concurrent queue with killable workers and bounded slow-speed resets."""
from __future__ import annotations

import json
import multiprocessing as mp
import queue
import time
from pathlib import Path
from dataclasses import dataclass

from core import Settings, SpeedWatch, Task, atomic_json
from worker import worker_entry
from library import Library

ACTIVE = {"running", "resetting"}


@dataclass
class WorkerState:
    task: Task
    process: object = None
    channel: object = None
    watch: object = None
    phase: str = "metadata"
    bytes: int = 0
    download_started: float = 0
    next_start: float = 0
    exit_seen: float | None = None


class Engine:
    def __init__(self, home: Path, notify=lambda message: None, worker_target=worker_entry):
        self.home = home
        self.notify = notify
        self.worker_target = worker_target
        self.tasks: list[Task] = []
        self.settings = Settings()
        self.cookie = ""
        self.running = False
        self.active: dict[str, WorkerState] = {}
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
        for state in list(self.active.values()):
            self._stop_process(state)
            state.task.status = "paused"
            state.task.phase = "已暂停，保留已验证图片"
            state.task.speed = 0
        self.active.clear()
        for task in self.tasks:
            if task.status == "queued":
                task.status = "paused"
                task.phase = "已暂停"
        self.save()

    def cancel(self, keys):
        for task in self.tasks:
            if task.key not in keys or task.status in ("done", "cancelled"):
                continue
            state = self.active.pop(task.key, None)
            if state:
                self._stop_process(state)
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

    def _stop_process(self, state):
        if state.process:
            if state.process.is_alive():
                state.process.terminate()
            state.process.join(timeout=2)
            if state.process.is_alive():
                state.process.kill()
                state.process.join(timeout=1)
            state.process.close()
            state.process = None
        if state.channel:
            state.channel.close()
            state.channel = None
        state.exit_seen = None

    def _launch(self, task: Task, now):
        state = WorkerState(task)
        self.active[task.key] = state
        task.status = "running"
        task.phase = "正在恢复下载，保留原进度" if task.done else "正在启动下载进程"
        # Keep the persisted snapshot until the worker reconciles actual cache files.
        task.result_bytes = 0
        state.download_started = 0
        task.error = ""
        task.metrics = {}
        task.speed = 0
        state.phase = "metadata"
        state.bytes = 0
        state.watch = SpeedWatch(Settings(**task.settings), now)
        state.channel = self.context.Queue()
        state.process = self.context.Process(target=self.worker_target, args=(task.to_dict(), self.cookie, state.channel), daemon=True)
        try:
            state.process.start()
        except Exception as exc:
            state.process = None
            state.channel.close()
            state.channel = None
            self._fail(state, f"无法启动下载进程：{type(exc).__name__}: {exc}")
            return
        self.notify(f"JM{task.album_id} 开始下载（{task.settings['format'].upper()}）")
        self.save()

    def _fail(self, state, message):
        task = state.task
        self._stop_process(state)
        task.status = "failed"
        task.error = message
        task.phase = "下载失败，点击任务查看原因"
        task.speed = 0
        self.notify(f"JM{task.album_id} 失败：{message}")
        self.active.pop(task.key, None)
        self.save()

    def _handle(self, state, event, now):
        task = state.task
        kind = event.get("type")
        if kind == "title":
            task.title = event["title"]
        elif kind == "route":
            task.phase = event["message"]
        elif kind == "metadata":
            task.phase = event["message"]
            state.watch.last_progress = now
        elif kind == "phase":
            state.phase = event["phase"]
            task.phase = event["message"]
            if state.phase in ("download", "page_retry"):
                task.total = event["total"]
                state.watch = SpeedWatch(Settings(**task.settings), now)
                if state.phase == "download":
                    state.download_started = now
        elif kind == "progress":
            task.done, task.total, task.cached = event["done"], event["total"], event["cached"]
            state.bytes = event["bytes"]
            task.image_bytes = event.get("image_bytes", task.image_bytes)
            task.phase = event["message"]
            state.watch.last_progress = now
        elif kind == "export_progress":
            task.phase = event["message"]
        elif kind == "error":
            self._fail(state, event["error"])
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
                labels = {"startup": "准备", "metadata": "连接/元数据", "cache": "已有图片校验", "download": "图片下载与处理", "verify": "导出前校验", "export": "导出与清理"}
                stages = task.metrics.get("stages", {})
                text = "，".join(f"{labels.get(key, key)} {seconds:.2f}s" for key, seconds in stages.items())
                self.notify(f"JM{task.album_id} 本轮耗时 {task.metrics['total_seconds']:.2f}s：{text}")
            self._stop_process(state)
            self.active.pop(task.key, None)
            self.save()

    def _tick_worker(self, state, now):
        task = state.task
        if task.status == "resetting":
            if now >= state.next_start:
                self._launch(task, now)
            return
        if state.channel:
            for _ in range(300):
                try:
                    event = state.channel.get_nowait()
                except queue.Empty:
                    break
                self._handle(state, event, now)
                if task.key not in self.active:
                    return
        if state.process:
            if not state.process.is_alive():
                # Allow multiprocessing's feeder to deliver its terminal event.
                if state.exit_seen is None:
                    state.exit_seen = now
                elif now - state.exit_seen > 1:
                    code = state.process.exitcode
                    self._fail(state, f"下载进程意外退出（退出码 {code}）。可能是依赖、系统资源或安全软件拦截；已保留缓存，可重试。")
            elif state.phase == "page_retry":
                task.speed = 0
                if now - state.watch.last_progress >= max(state.watch.settings.stall_seconds, state.watch.settings.timeout * (state.watch.settings.request_retries + 1) * 2):
                    self._fail(state, "单页重试超时；已保留其他图片，请查看失败页后重试任务。")
            elif state.phase in ("metadata", "download"):
                speed, reason = state.watch.sample(now, state.bytes)
                task.speed = speed
                # A slow byte rate is only meaningful in the image phase.
                if state.phase == "metadata" and now - state.watch.last_progress < state.watch.settings.stall_seconds:
                    reason = None
                if reason:
                    if task.resets >= task.settings["max_resets"]:
                        self._fail(state, f"{reason}；已达到自动重置上限 {task.settings['max_resets']} 次。请检查网络或调低慢速阈值后重试。")
                    else:
                        self._stop_process(state)
                        task.resets += 1
                        task.status = "resetting"
                        task.speed = 0
                        delay = min(30, 3 * 2 ** (task.resets - 1))
                        task.phase = f"{reason}；{delay} 秒后重建连接（{task.resets}/{task.settings['max_resets']}）"
                        self.notify(f"JM{task.album_id} 自动重置：{task.phase}")
                        state.next_start = now + delay
                        self.save()
            else:
                task.speed = 0

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        for state in list(self.active.values()):
            self._tick_worker(state, now)
        if self.running:
            for task in self.tasks:
                if len(self.active) >= self.settings.concurrent_tasks:
                    break
                if task.status == "queued" and task.key not in self.active:
                    self._launch(task, now)
            if not self.active and not any(t.status == "queued" for t in self.tasks):
                self.running = False
                self.notify("下载完成" if self.tasks and all(t.status == "done" for t in self.tasks)
                            else "本轮队列已结束；失败任务可选中后重试。")
                self.save()
        if self.active and now - self.last_saved > 5:
            self.save()

    def stop_workers(self):
        for state in list(self.active.values()):
            self._stop_process(state)

    def close(self):
        self.pause()
