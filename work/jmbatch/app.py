"""Windows desktop front end. Run with Python or build a standalone EXE."""
from __future__ import annotations

import ctypes
import json
import multiprocessing
import os
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import VERSION, MAX_TASKS, Settings, parse_ids
from engine import Engine
from download_display import format_size, format_speed, percent, progress_text, size_text, eta_text

BG = "#f3f5f8"
INK = "#172c3e"
MUTED = "#617387"
ACCENT = "#087f8c"
STATUS = {"queued": "等待", "running": "进行中", "paused": "已暂停", "resetting": "重建连接", "failed": "失败", "done": "下载完成", "cancelled": "已取消"}


def app_home():
    return Path(os.environ.get("JM_BATCH_HOME") or (Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JMBatch"))


class InstanceLock:
    def __init__(self, home):
        home.mkdir(parents=True, exist_ok=True)
        self.file = (home / "app.lock").open("a+b")
        self.file.seek(0)
        if self.file.read(1) == b"":
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                self.file.close()
                raise RuntimeError("JM Batch 已在运行，请使用已打开的窗口。")
        else:
            import fcntl
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def close(self):
        self.file.close()


class App:
    def __init__(self, root, home):
        self.root, self.home = root, home
        # Keep a predictable layout under Windows display scaling.
        self.root.tk.call("tk", "scaling", 4 / 3)
        self.notices = []
        self.engine = Engine(home, self.log)
        self.detail_cache = None
        self.root.title(f"JM Batch · 批量下载器 {VERSION}")
        self.root.geometry("1160x850")
        self.root.minsize(1020, 780)
        self.root.configure(bg=BG)
        self._styles()
        self._build()
        from updates import UpdateUI
        self.updates = UpdateUI(self)
        self.update_button.configure(command=self.updates.show)
        self.root.after(1500, self.updates.startup)
        for notice in self.notices:
            self._append_log(notice)
        self.notices.clear()
        self.log("就绪。支持单个编号、多个编号和连续区间；Cookie 仅保存在本次会话内存中。")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(250, self.tick)

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        self.root.option_add("*Font", ("Microsoft YaHei UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background="white")
        style.configure("TLabel", background=BG, foreground=INK, font=("Microsoft YaHei UI", 10))
        style.configure("Card.TLabel", background="white")
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", padding=(13, 8), background="white", foreground=INK, borderwidth=1)
        style.map("TButton", background=[("active", "#e5edf2"), ("disabled", "#eff1f4")])
        style.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#096a75"), ("disabled", "#9bbbbd")], foreground=[("disabled", "white")])
        style.configure("TEntry", padding=6)
        style.configure("Treeview", font=("Microsoft YaHei UI", 10), rowheight=34, background="white", fieldbackground="white", foreground=INK, borderwidth=0)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), background="#e8eef3", padding=8)
        style.map("Treeview", background=[("selected", "#d7edf0")], foreground=[("selected", INK)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#dfe8ed", borderwidth=0, thickness=9)
        style.configure("TRadiobutton", background=BG, foreground=INK)
        style.configure("TCheckbutton", background=BG, foreground=INK)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 6))

    def _build(self):
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="JM Batch", font=("Segoe UI", 26, "bold"), foreground=INK).pack(side="left")
        ttk.Label(header, text="  /  编号批量下载", font=("Microsoft YaHei UI", 12), foreground=MUTED).pack(side="left", pady=(10, 0))
        ttk.Button(header, text="下载设置", command=self.settings_dialog).pack(side="right")
        self.update_button = ttk.Button(header, text="软件更新 / 公告")
        self.update_button.pack(side="right", padx=6)
        ttk.Label(header, text=f"WINDOWS  ·  {VERSION}", foreground=ACCENT, font=("Segoe UI", 10, "bold")).pack(side="right", padx=18)

        dest = ttk.Frame(outer)
        dest.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        dest.columnconfigure(1, weight=1)
        ttk.Label(dest, text="保存到").grid(row=0, column=0, padx=(0, 12))
        self.output_var = tk.StringVar(value=self.engine.settings.output)
        ttk.Entry(dest, textvariable=self.output_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(dest, text="选择目录", command=self.choose_dir).grid(row=0, column=2, padx=(8, 18))
        self.format_var = tk.StringVar(value="images")
        ttk.Label(dest, text="下载保存为排序图片").grid(row=0, column=3, padx=7)
        ttk.Button(dest, text="导出 PDF / ZIP", command=self.export_selected).grid(row=0, column=4)

        entry = ttk.Frame(outer, style="Card.TFrame", padding=12)
        entry.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        entry.columnconfigure(0, weight=1)
        ttk.Label(entry, text="添加下载编号", font=("Microsoft YaHei UI", 11, "bold"), style="Card.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(entry, text="例如 123456, 123460-123465   ·   支持空格、换行、逗号及 JM 前缀", foreground=MUTED, style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 8))
        self.input = tk.Text(entry, height=2, wrap="word", bg="#f7f9fb", fg=INK, relief="flat", highlightthickness=1, highlightbackground="#dce4eb", padx=10, pady=8, undo=True)
        self.input.grid(row=2, column=0, sticky="ew", padx=(0, 16))
        self.input.bind("<Control-Return>", lambda _: self.add_input())
        quick = ttk.Frame(entry, style="Card.TFrame")
        quick.grid(row=0, column=1, rowspan=3, sticky="ns")
        ttk.Label(quick, text="连号快捷添加", style="Card.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.range_start = tk.StringVar()
        self.range_end = tk.StringVar()
        ttk.Entry(quick, textvariable=self.range_start, width=10).grid(row=1, column=0)
        ttk.Label(quick, text=" 至 ", style="Card.TLabel").grid(row=1, column=1)
        ttk.Entry(quick, textvariable=self.range_end, width=10).grid(row=1, column=2)
        ttk.Button(quick, text="添加区间", command=self.add_range).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(entry, text="加入队列  Ctrl + Enter", style="Accent.TButton", command=self.add_input).grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Label(entry, text="按章节、页码保存图片；下载后可在“导出”中选择 PDF / ZIP。", foreground=MUTED, style="Card.TLabel").grid(row=4, column=0, columnspan=2, sticky="w", pady=(9, 0))

        bar = ttk.Frame(outer)
        bar.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.start_button = ttk.Button(bar, text="▶  开始 / 继续", style="Accent.TButton", command=self.start)
        self.start_button.pack(side="left")
        self.pause_button = ttk.Button(bar, text="暂停全部", command=self.pause)
        self.pause_button.pack(side="left", padx=7)
        ttk.Button(bar, text="重试选中", command=self.retry).pack(side="left")
        ttk.Button(bar, text="取消选中", command=self.cancel).pack(side="left", padx=7)
        ttk.Button(bar, text="移除记录", command=self.remove).pack(side="left")
        ttk.Button(bar, text="已下载漫画", command=self.show_library).pack(side="left", padx=6)
        ttk.Button(bar, text="打开文件", command=self.open_selected).pack(side="right")
        ttk.Button(bar, text="打开目录", command=self.open_output).pack(side="right", padx=7)

        stats = ttk.Frame(outer)
        stats.grid(row=4, column=0, sticky="ew", pady=(0, 9))
        self.summary = tk.StringVar(value="还没有任务")
        ttk.Label(stats, textvariable=self.summary, foreground=MUTED).pack(side="left")
        self.speed_text = tk.StringVar(value="落盘速度  —")
        ttk.Label(stats, textvariable=self.speed_text, foreground=ACCENT).pack(side="right")

        table = ttk.Frame(outer)
        table.grid(row=5, column=0, sticky="nsew")
        columns = ("id", "title", "status", "progress", "size", "format", "resets")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="extended", height=5)
        for key, label, width in [("id", "编号", 100), ("title", "标题", 220), ("status", "状态", 95), ("progress", "完成进度", 180), ("size", "漫画大小", 125), ("format", "格式", 65), ("resets", "重置", 60)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=60, stretch=key == "title", anchor="w")
        for tag, color in [("failed", "#b42336"), ("done", "#117767"), ("paused", MUTED), ("cancelled", MUTED), ("resetting", "#9d6507")]:
            self.tree.tag_configure(tag, foreground=color)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.update_details())
        self.tree.bind("<Double-1>", lambda _: self.open_selected())

        progress = ttk.Frame(outer)
        progress.grid(row=6, column=0, sticky="ew", pady=(8, 6))
        self.progress_text = tk.StringVar(value="等待添加任务")
        self.progress_label = ttk.Label(progress, textvariable=self.progress_text, foreground=MUTED, justify="left", wraplength=920)
        self.progress_label.pack(anchor="w", pady=(0, 7))
        progress.bind("<Configure>", lambda event: self.progress_label.configure(wraplength=max(100, event.width)))
        self.progressbar = ttk.Progressbar(progress, mode="determinate", maximum=100)
        self.progressbar.pack(fill="x")

        notebook = ttk.Notebook(outer)
        notebook.grid(row=7, column=0, sticky="ew")
        details_frame = ttk.Frame(notebook)
        logs_frame = ttk.Frame(notebook)
        notebook.add(details_frame, text="任务详情 / 失败原因")
        notebook.add(logs_frame, text="运行记录")
        self.details = self._text_panel(details_frame, 4)
        self.logs = self._text_panel(logs_frame, 4)
        self._set_text(self.details, "选中任务可查看完整错误、输出路径和缓存位置。\n慢速重置会保留已验证图片；PDF / ZIP 导出阶段不触发慢速重置。")

    def _text_panel(self, parent, height):
        text = tk.Text(parent, height=height, wrap="word", relief="flat", bg="white", fg=INK, padx=12, pady=10, state="disabled", font=("Microsoft YaHei UI", 9))
        scroll = ttk.Scrollbar(parent, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return text

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def log(self, message):
        stamp = f"[{time.strftime('%H:%M:%S')}] {message}"
        if hasattr(self, "logs"):
            self._append_log(stamp)
        else:
            self.notices.append(stamp)
        try:
            self.home.mkdir(parents=True, exist_ok=True)
            path = self.home / "app.log"
            if path.exists() and path.stat().st_size > 2_000_000:
                os.replace(path, self.home / "app.previous.log")
            with path.open("a", encoding="utf-8") as stream:
                stream.write(stamp + "\n")
        except OSError:
            pass

    def _append_log(self, message):
        self.logs.configure(state="normal")
        self.logs.insert("end", message + "\n")
        if int(self.logs.index("end-1c").split(".")[0]) > 600:
            self.logs.delete("1.0", "100.0")
        self.logs.see("end")
        self.logs.configure(state="disabled")

    def current_settings(self):
        values = dict(self.engine.settings.__dict__)
        values.update(output=str(Path(self.output_var.get().strip()).expanduser().absolute()), format="images", keep_images=False, numeric_filename=False, flat_zip=False)
        if not self.output_var.get().strip():
            raise ValueError("请选择输出目录。")
        return Settings(**values).validate()

    def choose_dir(self):
        directory = filedialog.askdirectory(title="选择下载保存目录", initialdir=self.output_var.get() if Path(self.output_var.get()).is_dir() else str(Path.home()))
        if directory:
            self.output_var.set(directory)

    def _add(self, text):
        try:
            ids = parse_ids(text)
            if len(self.engine.tasks) + len(ids) > 10000:
                raise ValueError("队列记录上限为 10000，请先移除旧记录。")
            settings = self.current_settings()
            number = self.engine.add(ids, settings)
            self.log(f"加入 {number} 个任务，跳过 {len(ids) - number} 个重复项。")
            self.render()
            return True
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法添加任务", str(exc), parent=self.root)
            return False

    def add_input(self):
        if self._add(self.input.get("1.0", "end")):
            self.input.delete("1.0", "end")

    def add_range(self):
        if not self.range_start.get().strip() or not self.range_end.get().strip():
            messagebox.showinfo("连号输入", "请填写起始编号和结束编号。", parent=self.root)
            return
        if self._add(self.range_start.get().strip() + "-" + self.range_end.get().strip()):
            self.range_start.set("")
            self.range_end.set("")

    def start(self):
        if not any(t.status in ("queued", "paused") for t in self.engine.tasks):
            messagebox.showinfo("没有待下载任务", "请添加编号，或选中失败任务后点击“重试选中”。", parent=self.root)
            return
        self.engine.start()
        self.log("队列开始运行，按同时下载任务数调度；每本图片独立并发下载。")

    def pause(self):
        self.engine.pause()
        self.log("队列已暂停，已验证图片保留。")
        self.render()

    def retry(self):
        try:
            count = self.engine.retry(set(self.tree.selection()), self.current_settings())
            if count:
                self.engine.start()
                self.log(f"重新排队 {count} 个任务，使用当前网络设置；保留原输出路径，下载保存为排序图片。")
            else:
                messagebox.showinfo("重试任务", "请选中失败、暂停或取消的任务。", parent=self.root)
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法重试", str(exc), parent=self.root)

    def cancel(self):
        self.engine.cancel(set(self.tree.selection()))
        self.render()

    def show_library(self):
        from library import LibraryWindow
        existing = getattr(self, "library_window", None)
        if existing and existing.window.winfo_exists():
            existing.window.lift()
            existing.refresh()
        else:
            self.library_window = LibraryWindow(self)

    def remove(self):
        keys = set(self.tree.selection())
        removable = [t for t in self.engine.tasks if t.key in keys and t.status in ("done", "failed", "cancelled", "paused")]
        if not removable:
            messagebox.showinfo("移除记录", "请选中已完成、失败、取消或暂停的任务。", parent=self.root)
            return
        if messagebox.askyesno("移除队列记录", f"移除 {len(removable)} 条记录？\n成品和缓存均保留在原目录。移除后无法通过此记录续传。", parent=self.root):
            try:
                self.engine.library.sync(self.engine.tasks)
            except OSError as exc:
                messagebox.showerror("请先恢复漫画列表", str(exc), parent=self.root)
                return
            self.engine.tasks = [t for t in self.engine.tasks if t not in removable]
            self.engine.save()
            self.render()

    def selected_task(self):
        keys = self.tree.selection()
        return next((t for t in self.engine.tasks if keys and t.key == keys[0]), None)

    def open_output(self):
        task = self.selected_task()
        self._open(Path(task.settings["output"] if task else self.output_var.get()))

    def open_selected(self):
        task = self.selected_task()
        if task and task.result:
            self._open(Path(task.result))
        else:
            self.update_details()

    def _open(self, path):
        if not path.exists():
            messagebox.showinfo("路径尚不存在", str(path), parent=self.root)
            return
        try:
            if os.name == "nt":
                os.startfile(str(path.resolve()))
            else:
                import subprocess
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path.resolve())])
        except OSError as exc:
            messagebox.showerror("无法打开", str(exc), parent=self.root)

    def update_details(self):
        task = self.selected_task()
        if not task:
            return
        from core import task_cache
        value = f"JM{task.album_id}  ·  {task.title}\n{STATUS.get(task.status, task.status)}：{task.phase}\n输出：{task.result or task.settings['output']}\n图片 {task.done}/{task.total or '?'}，本轮复用 {task.cached} 张；自动重置 {task.resets}/{task.settings['max_resets']}\n缓存：{task_cache(task.to_dict())}"
        value += "\n完成进度 " + progress_text(task.done, task.total, task.status) + " · " + size_text(task.done, task.total, task.image_bytes, task.result_bytes, task.status)
        if task.error:
            value += "\n\n失败原因：\n" + task.error
        if task.metrics:
            value += f"\n\n本轮耗时：{task.metrics['total_seconds']:.2f} 秒"
            labels = {"startup": "准备", "metadata": "连接/元数据", "download": "图片下载与处理", "verify": "导出前校验", "export": "导出与清理"}
            value += "\n" + "；".join(f"{labels.get(key, key)} {seconds:.2f}s" for key, seconds in task.metrics.get("stages", {}).items())
        if value != self.detail_cache:
            self._set_text(self.details, value)
            self.detail_cache = value

    def render(self):
        keys = {t.key for t in self.engine.tasks}
        for key in self.tree.get_children():
            if key not in keys:
                self.tree.delete(key)
        for task in self.engine.tasks:
            progress = progress_text(task.done, task.total, task.status)
            size = (format_size(task.result_bytes) if task.result_bytes else "未知（旧记录）") if task.status == "done" else ("约 " + format_size(task.image_bytes * task.total / task.done) if task.done and task.image_bytes else "计算中")
            values = (f"JM{task.album_id}", task.title, STATUS.get(task.status, task.status), progress, size, "图片" if task.settings["format"] == "images" else task.settings["format"].upper(), str(task.resets))
            if self.tree.exists(task.key):
                if tuple(map(str, self.tree.item(task.key, "values"))) != tuple(map(str, values)):
                    self.tree.item(task.key, values=values, tags=(task.status,))
            else:
                self.tree.insert("", "end", iid=task.key, values=values, tags=(task.status,))
        tasks = self.engine.tasks
        done = sum(t.status == "done" for t in tasks)
        failed = sum(t.status == "failed" for t in tasks)
        waiting = sum(t.status in ("queued", "paused") for t in tasks)
        self.summary.set(f"共 {len(tasks)} 本    ·    已完成 {done}    ·    失败 {failed}    ·    待处理 {waiting}")
        active = list(self.engine.active.values())
        selected = self.selected_task()
        state = self.engine.active.get(selected.key) if selected else None
        state = state or (active[0] if active else None)
        current = state.task if state else None
        self.start_button.configure(state="disabled" if self.engine.running else "normal")
        self.pause_button.configure(state="normal" if self.engine.running else "disabled")
        if current:
            self.speed_text.set(f"同时下载 {len(active)} 本 · 总落盘速度  " + format_speed(sum(s.task.speed for s in active)))
            estimate = eta_text(current.status, state.phase, current.done, current.total, current.cached,
                                time.monotonic() - state.download_started, current.speed)
            if current.settings["format"] == "images":
                estimate = estimate.replace("校验 / 导出", "校验 / 保存").replace("导出另计", "保存另计")
            self.progress_text.set(f"JM{current.album_id} · {progress_text(current.done, current.total, current.status)} · {format_speed(current.speed)} · {current.phase[:70]}\n"
                                   + size_text(current.done, current.total, current.image_bytes, current.result_bytes, current.status) + "\n" + estimate)
            self.progressbar["value"] = percent(current.done, current.total, current.status)
        else:
            self.speed_text.set("落盘速度  —")
            latest = next((t for t in reversed(tasks) if t.status == "done"), None)
            self.progress_text.set("队列已暂停，点击开始继续" if waiting and not self.engine.running else
                                   (f"JM{latest.album_id} · 下载完成 · 100.0%\n" + size_text(latest.done, latest.total, latest.image_bytes, latest.result_bytes, latest.status) if latest else "当前没有正在运行的任务"))
            self.progressbar["value"] = 100 if latest and not waiting else 0
        self.update_details()

    def tick(self):
        try:
            self.engine.tick()
            self.render()
        except Exception as exc:
            self.log(f"队列异常：{type(exc).__name__}: {exc}")
            try:
                self.engine.pause()
            except Exception:
                self.engine.stop_workers()
                self.engine.running = False
            messagebox.showerror("队列已暂停", f"{type(exc).__name__}: {exc}\n请检查配置目录是否可写。", parent=self.root)
        self.root.after(250, self.tick)

    def export_selected(self):
        task = self.selected_task()
        self.show_library()
        if task and task.status == "done" and task.result:
            key = self.engine.library.key(task.result)
            if self.library_window.tree.exists(key):
                self.library_window.tree.selection_set(key)
                self.library_window.action("export")
        else:
            self.library_window.status.set("请选择一本已下载的图片漫画，然后点击“导出”。")

    def settings_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("下载设置")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="连接与自动恢复", font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))
        variables = {}
        fields = [
            ("concurrent_tasks", "同时下载任务数", "1–4，默认 2；每个任务单独使用下方图片线程"),
            ("threads", "每个任务图片线程数", "1–16，默认 8；遇限流可调低"),
            ("timeout", "单次请求超时 / 秒", "5–120"),
            ("request_retries", "单次请求重试", "0–5"),
            ("slow_kbps", "慢速阈值 / KB/s", "0 表示仅检测无进度"),
            ("slow_seconds", "慢速观察窗口 / 秒", "15–600，首次等待额外 30 秒"),
            ("stall_seconds", "无进度超时 / 秒", "30–1800，含连接与读取元数据"),
            ("max_resets", "每本最大自动重置次数", "0–10，达到上限后明确报错"),
        ]
        for row, (key, label, hint) in enumerate(fields, 1):
            variables[key] = tk.StringVar(value=str(getattr(self.engine.settings, key)))
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=5)
            ttk.Entry(frame, textvariable=variables[key], width=9).grid(row=row, column=1, padx=8)
            ttk.Label(frame, text=hint, foreground=MUTED).grid(row=row, column=2, sticky="w")
        auto = tk.BooleanVar(value=self.engine.settings.auto_reset)
        ttk.Checkbutton(frame, text="启用慢速 / 无进度自动重置", variable=auto).grid(row=9, column=0, columnspan=3, sticky="w", pady=(14, 5))
        ttk.Label(frame, text="Cookie（可选，仅本次会话有效，不写入配置或日志）").grid(row=12, column=0, columnspan=3, sticky="w", pady=(15, 6))
        cookie = tk.StringVar(value=self.engine.cookie)
        ttk.Entry(frame, textvariable=cookie, show="●", width=65).grid(row=13, column=0, columnspan=3, sticky="ew")
        ttk.Label(frame, text="速度按已完成图片的文件大小估算，大图下载期间可能暂时显示 0。\n重置会终止旧进程并重建连接；导出阶段不重置。\n任务数保存后生效；调低时等待当前任务结束，不中断下载。\n其他设置用于新任务及手动重试；运行中任务保留原设置。", foreground=MUTED, justify="left").grid(row=14, column=0, columnspan=3, sticky="w", pady=15)

        def save():
            try:
                values = self.current_settings().__dict__.copy()
                for key, variable in variables.items():
                    try:
                        values[key] = int(variable.get())
                    except ValueError:
                        raise ValueError("数值设置必须填写整数。")
                values.update(auto_reset=auto.get())
                from worker import parse_cookies
                parse_cookies(cookie.get().strip())
                self.engine.settings = Settings(**values).validate()
                self.engine.cookie = cookie.get().strip()
                self.engine.save()
                self.log("下载设置已保存。Cookie 仅在本次会话中使用。")
                dialog.destroy()
            except (ValueError, OSError) as exc:
                messagebox.showerror("设置无效", str(exc), parent=dialog)
        ttk.Button(frame, text="保存设置", style="Accent.TButton", command=save).grid(row=15, column=0, columnspan=3, sticky="e")

    def close(self):
        if self.engine.active and not messagebox.askyesno("退出 JM Batch", "退出会暂停全部下载任务并保留已验证图片。下次打开可继续。", parent=self.root):
            return
        try:
            self.engine.settings = self.current_settings()
            self.engine.close()
        except Exception as exc:
            self.engine.stop_workers()
            messagebox.showwarning("保存状态失败", str(exc), parent=self.root)
        self.root.destroy()


def main():
    multiprocessing.freeze_support()
    if "--apply-update" in sys.argv:
        from update_install import apply_update
        index = sys.argv.index("--apply-update")
        apply_update(sys.argv[index + 1], sys.argv[index + 2])
        return
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    if "--self-test" in sys.argv:
        from diagnostics import run_self_test
        index = sys.argv.index("--self-test")
        directory = Path(sys.argv[index + 1]).resolve()
        run_self_test(directory)
        return
    root = tk.Tk()
    lock = None
    try:
        lock = InstanceLock(app_home())
        App(root, app_home())
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("JM Batch 无法启动", f"{type(exc).__name__}: {exc}", parent=root)
        root.destroy()
    finally:
        if lock:
            lock.close()


if __name__ == "__main__":
    main()
