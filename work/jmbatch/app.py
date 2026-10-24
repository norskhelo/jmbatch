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
from chapter_ui import poll_chapters

BG = "#f5f5f7"
INK = "#1d1f26"
MUTED = "#747780"
ACCENT = "#73757c"
STATUS = {"cancelling": "正在取消", "cancel_failed": "清理失败", "selecting": "待选章节", "queued": "等待下载", "running": "下载中", "paused": "已暂停", "resetting": "正在重连", "failed": "下载失败", "done": "下载完成", "cancelled": "已取消"}


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
        self.root.title(f"JM Batch {VERSION}")
        self.root.geometry("1160x850")
        self.root.minsize(1020, 820)
        self.root.configure(bg=BG)
        self._styles()
        self._build()
        from updates import UpdateUI
        self.updates = UpdateUI(self)
        self.update_button.configure(command=self.updates.show_and_check)
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
        style.configure("TFrame", background="white")
        style.configure("Card.TFrame", background="white")
        style.configure("TLabel", background="white", foreground=INK, font=("Microsoft YaHei UI", 10))
        style.configure("Card.TLabel", background="white")
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", padding=(13, 8), background="white", foreground=INK, borderwidth=1)
        style.map("TButton", background=[("active", "#e8e8ec"), ("disabled", "#eff1f4")])
        style.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#606269"), ("disabled", "#aaaab0")], foreground=[("disabled", "white")])
        style.configure("Fab.TButton", background=ACCENT, foreground="white", font=("Segoe UI",22), padding=(12,6))
        style.configure("TEntry", padding=9)
        style.configure("Treeview", font=("Microsoft YaHei UI", 10), rowheight=34, background="white", fieldbackground="white", foreground=INK, borderwidth=0)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), background="#e8eef3", padding=8)
        style.map("Treeview", background=[("selected", "#e5e5e9")], foreground=[("selected", INK)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#dfe8ed", borderwidth=0, thickness=9)
        style.configure("TRadiobutton", background=BG, foreground=INK)
        style.configure("TCheckbutton", background=BG, foreground=INK)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 6))

    def _build(self):
        from ui_main import build
        build(self)

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

    def save_format(self):
        self.engine.settings.format = self.format_var.get()
        try:
            self.engine.save()
        except OSError as error:
            messagebox.showerror("格式设置未保存", str(error), parent=self.root)

    def current_settings(self):
        values = dict(self.engine.settings.__dict__)
        values.update(output=str(Path(self.output_var.get().strip()).expanduser().absolute()), format=self.format_var.get(), keep_images=False, numeric_filename=False, flat_zip=False)
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
            messagebox.showinfo("连续编号", "请填写起始编号和结束编号。", parent=self.root)
            return
        if self._add(self.range_start.get().strip() + "-" + self.range_end.get().strip()):
            self.range_start.set("")
            self.range_end.set("")

    def start(self):
        if not any(t.status in ("queued", "paused", "selecting") for t in self.engine.tasks):
            messagebox.showinfo("没有待下载任务", "请添加编号，或选中失败任务后点击“重试任务”。", parent=self.root)
            return
        self.engine.start()
        self.log("队列开始运行，按同时下载任务数调度；每本图片独立并发下载。")

    def pause(self):
        self.engine.pause()
        self.log("队列已暂停，已验证图片保留。")
        self.render()

    def retry(self):
        try:
            cancelling = {t.key for t in self.engine.tasks if t.key in self.tree.selection() and t.status == "cancel_failed"}
            if cancelling:
                self.engine.cancel(cancelling)
            count = self.engine.retry(set(self.tree.selection()), self.current_settings())
            if count:
                self.engine.start()
                self.log(f"重新排队 {count} 个任务，使用当前网络设置；保留原输出路径和下载格式。")
            elif not cancelling:
                messagebox.showinfo("重试任务", "请选择已失败、已暂停或已取消的任务，然后重试。", parent=self.root)
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法重试", str(exc), parent=self.root)

    def cancel(self):
        try:
            self.engine.cancel(set(self.tree.selection()))
        except OSError as exc:
            messagebox.showerror("无法保存取消状态", str(exc), parent=self.root)
        self.render()

    def show_library(self):
        from ui_main import show_library
        show_library(self)

    def remove(self):
        keys = set(self.tree.selection())
        removable = [t for t in self.engine.tasks if t.key in keys and t.status in ("done", "failed", "cancelled", "paused")]
        if not removable:
            messagebox.showinfo("移除记录", "请选择已结束或已暂停的任务。正在下载的任务无法移除。", parent=self.root)
            return
        if messagebox.askyesno("移除队列记录", f"确定移除所选的 {len(removable)} 条任务记录？\n已保存文件和缓存将保留。移除后无法通过这些记录继续下载。", parent=self.root):
            try:
                self.engine.library.sync(self.engine.tasks)
            except OSError as exc:
                messagebox.showerror("无法移除记录", str(exc), parent=self.root)
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
            try:
                self.engine.library.sync(self.engine.tasks)
                self.read_comic(self.engine.library.key(task.result))
            except Exception as exc:
                messagebox.showerror("无法阅读", str(exc), parent=self.root)
        else:
            self.update_details()

    def read_comic(self, key):
        from reader_ui import open_reader
        return open_reader(self, key)

    def _open(self, path):
        if not path.exists():
            messagebox.showinfo("保存位置不存在", str(path), parent=self.root)
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
        value = f"JM{task.album_id}  ·  {task.title}\n{STATUS.get(task.status, task.status)}：{task.phase}\n保存位置：{task.result or task.settings['output']}\n图片 {task.done}/{task.total or '?'}，本轮复用 {task.cached} 张；自动重连 {task.resets}/{task.settings['max_resets']}\n缓存：{task_cache(task.to_dict())}"
        value += "\n完成进度 " + progress_text(task.done, task.total, task.status) + " · " + size_text(task.done, task.total, task.image_bytes, task.result_bytes, task.status)
        if task.error:
            value += "\n\n失败原因：\n" + task.error
        if task.metrics:
            value += f"\n\n本轮耗时：{task.metrics['total_seconds']:.2f} 秒"
            labels = {"startup": "准备", "metadata": "读取漫画信息", "download": "图片下载与处理", "verify": "导出前校验", "export": "导出与清理"}
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
                self.tree.insert("", "end", iid=task.key, image=self.download_covers.placeholder, values=values, tags=(task.status,))
        tasks = self.engine.tasks
        self.download_covers.poll(tasks)
        done = sum(t.status == "done" for t in tasks)
        failed = sum(t.status == "failed" for t in tasks)
        waiting = sum(t.status in ("queued", "paused", "selecting") for t in tasks)
        selecting = sum(t.status == "selecting" for t in tasks)
        self.summary.set(f"共 {len(tasks)} 本    ·    已完成 {done}    ·    失败 {failed}    ·    待处理 {waiting}")
        active = list(self.engine.active.values())
        selected = self.selected_task()
        state = self.engine.active.get(selected.key) if selected else None
        state = state or (active[0] if active else None)
        current = state.task if state else None
        self.start_button.configure(state="disabled" if self.engine.running else "normal")
        self.pause_button.configure(state="normal" if self.engine.running or selecting else "disabled")
        if current:
            self.speed_text.set(f"同时下载 {len(active)} 本 · 总实时速度  " + format_speed(sum(s.task.speed for s in active)))
            estimate = eta_text(current.status, state.phase, current.done, current.total, current.cached,
                                time.monotonic() - state.download_started, current.speed)
            if current.settings["format"] == "images":
                estimate = estimate.replace("校验 / 导出", "校验 / 保存").replace("导出另计", "保存另计")
            self.progress_text.set(f"JM{current.album_id} · {progress_text(current.done, current.total, current.status)} · {format_speed(current.speed)} · {current.phase[:70]}\n"
                                   + size_text(current.done, current.total, current.image_bytes, current.result_bytes, current.status) + "\n" + estimate)
            self.progressbar["value"] = percent(current.done, current.total, current.status)
        else:
            self.speed_text.set("实时速度  —")
            latest = next((t for t in reversed(tasks) if t.status == "done"), None)
            self.progress_text.set(f"{selecting} 本等待选择下载章节" if selecting else "队列已暂停，点击“开始下载”继续" if waiting and not self.engine.running else
                                   (f"JM{latest.album_id} · 下载完成 · 100.0%\n" + size_text(latest.done, latest.total, latest.image_bytes, latest.result_bytes, latest.status) if latest else "暂无正在下载的任务"))
            self.progressbar["value"] = 100 if latest and not waiting else 0
        self.update_details()
        from ui_main import refresh
        refresh(self)

    def tick(self):
        try:
            self.engine.tick()
            self.render()
            poll_chapters(self)
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
                self.library_window.enter_batch(key)
                self.library_window.tree.selection_set(key)
                self.library_window.action("export")
        else:
            self.library_window.status.set("请在漫画库选择一本漫画，然后点击“导出漫画”。")

    def settings_dialog(self):
        from ui_settings import show
        return show(self)

    def advanced_settings_dialog(self):
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
            ("concurrent_tasks", "同时下载任务数", "1–4，默认 2；各任务独立使用图片线程"),
            ("threads", "每任务图片线程数", "1–16，默认 8；遇限流可调低"),
            ("chapter_workers", "每任务章节并行数", "1–8，默认 4；超时或限流时可调低"),
            ("timeout", "请求超时（秒）", "5–120"),
            ("request_retries", "请求重试次数", "0–5"),
            ("slow_kbps", "慢速阈值（KB/s）", "0 表示仅检测无进度"),
            ("slow_seconds", "慢速检测时长（秒）", "15–600，首次等待额外 30 秒"),
            ("stall_seconds", "无进度超时（秒）", "30–1800，含连接与读取元数据"),
            ("max_resets", "每任务自动重连上限", "0–10，达到上限后停止任务并提示"),
        ]
        for row, (key, label, hint) in enumerate(fields, 1):
            variables[key] = tk.StringVar(value=str(getattr(self.engine.settings, key)))
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=5)
            ttk.Entry(frame, textvariable=variables[key], width=9).grid(row=row, column=1, padx=8)
            ttk.Label(frame, text=hint, foreground=MUTED).grid(row=row, column=2, sticky="w")
        auto = tk.BooleanVar(value=self.engine.settings.auto_reset)
        all_chapters = tk.BooleanVar(value=self.engine.settings.download_all_chapters)
        chapter_modes = ("1 多章节合一", "2 分章节观看")
        chapter_view = ttk.Combobox(frame, state="readonly", values=chapter_modes, width=20)
        chapter_view.current(self.engine.settings.chapter_view_mode - 1)
        ttk.Label(frame, text="多章节观看模式").grid(row=12, column=0, sticky="w", pady=8)
        chapter_view.grid(row=12, column=1, columnspan=2, sticky="w")
        ttk.Checkbutton(frame, text="默认下载全部章节（仅对未选择章节的任务生效）", variable=all_chapters).grid(row=11, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(frame, text="下载缓慢或无进度时自动重连", variable=auto).grid(row=10, column=0, columnspan=3, sticky="w", pady=(14, 5))
        ttk.Label(frame, text="Cookie（可选，仅本次会话有效，不写入配置或日志）").grid(row=13, column=0, columnspan=3, sticky="w", pady=(15, 6))
        cookie = tk.StringVar(value=self.engine.cookie)
        ttk.Entry(frame, textvariable=cookie, show="●", width=65).grid(row=14, column=0, columnspan=3, sticky="ew")
        ttk.Label(frame, text="并行数越高，请求越多；遇到超时或限流时可适当调低。\n实时速度按每秒完成下载、处理并写入缓存的图片字节统计。大图未完成时可能为 0，不叠加网络和磁盘字节。\n自动重连会重新建立下载连接，导出期间不执行。\n任务数保存后生效；调低时等待当前任务完成。\n其他设置用于新任务和手动重试，运行中任务保留原设置。", foreground=MUTED, justify="left").grid(row=15, column=0, columnspan=3, sticky="w", pady=15)

        def save():
            try:
                values = self.current_settings().__dict__.copy()
                for key, variable in variables.items():
                    try:
                        values[key] = int(variable.get())
                    except ValueError:
                        raise ValueError("请输入有效的整数，并确认数值在允许范围内。")
                values.update(auto_reset=auto.get(), download_all_chapters=all_chapters.get(),
                              chapter_view_mode=chapter_view.current() + 1)
                from worker import parse_cookies
                parse_cookies(cookie.get().strip())
                self.engine.settings = Settings(**values).validate()
                self.engine.cookie = cookie.get().strip()
                self.engine.save()
                self.log("设置已保存。多章节观看模式在重新打开漫画后生效。Cookie 仅在本次会话中使用。")
                dialog.destroy()
            except (ValueError, OSError) as exc:
                messagebox.showerror("设置无效", str(exc), parent=dialog)
        ttk.Button(frame, text="保存设置", style="Accent.TButton", command=save).grid(row=16, column=0, columnspan=3, sticky="e")

    def close(self):
        if self.engine.active and not messagebox.askyesno("退出 JM Batch", "退出会暂停全部下载任务并保留已验证图片。下次打开可继续。", parent=self.root):
            return
        for reader in list(getattr(self, "readers", {}).values()):
            reader.close()
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
    if "--self-test-tiles" in sys.argv:
        from diagnostics import run_tile_self_test
        index = sys.argv.index("--self-test-tiles")
        run_tile_self_test(Path(sys.argv[index + 1]).resolve())
        return
    if "--self-test-update-dialog" in sys.argv:
        from update_ui_checks import run
        run(Path(sys.argv[sys.argv.index("--self-test-update-dialog") + 1]).resolve())
        return
    if "--self-test-chapter-updates" in sys.argv:
        from chapter_update_checks import run
        run(Path(sys.argv[sys.argv.index("--self-test-chapter-updates") + 1]).resolve())
        return
    if "--self-test-download" in sys.argv:
        from download_checks import run
        run(Path(sys.argv[sys.argv.index("--self-test-download") + 1]).resolve())
        raise SystemExit(0)
    if "--self-test-bookmarks" in sys.argv:
        from bookmark_checks import run
        run(Path(sys.argv[sys.argv.index("--self-test-bookmarks") + 1]).resolve())
        raise SystemExit(0)
    if "--self-test-chapter-view" in sys.argv:
        from chapter_view_checks import run
        run(Path(sys.argv[sys.argv.index("--self-test-chapter-view") + 1]).resolve())
        return
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
