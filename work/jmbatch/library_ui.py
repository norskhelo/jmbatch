"""Library UI. Slow directory and batch operations run outside Tk's thread."""
import queue
import threading
from pathlib import Path


class LibraryWindow:
    def __init__(self, app):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.app, self.library = app, app.engine.library
        self.messagebox = messagebox
        self.busy = False
        self.cancelled = threading.Event()
        self.events = queue.Queue()
        self.window = tk.Toplevel(app.root)
        self.window.title("已下载漫画")
        self.window.geometry("1000x640")
        self.window.minsize(850, 520)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        body = ttk.Frame(self.window, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)
        ttk.Label(body, text="图片目录 / PDF / ZIP · Ctrl / Shift 多选 · 原始图片可重复导出").grid(row=0, column=0, sticky="w")
        bar = ttk.Frame(body)
        bar.grid(row=1, column=0, sticky="ew", pady=8)
        bar.columnconfigure(1, weight=1)
        self.query = tk.StringVar()
        self.only_favorites = tk.BooleanVar()
        ttk.Label(bar, text="编号 / 标题").grid(row=0, column=0)
        ttk.Entry(bar, textvariable=self.query, width=18).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Checkbutton(bar, text="只看收藏", variable=self.only_favorites, command=self.render).grid(row=0, column=2)
        ttk.Button(bar, text="扫描保存目录", command=self.scan).grid(row=0, column=3, padx=6)
        ttk.Button(bar, text="刷新", command=self.refresh).grid(row=0, column=4)
        self.query.trace_add("write", lambda *_: self.render())
        select_bar = ttk.Frame(body)
        select_bar.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        for label, mode in (("全选当前结果", "all"), ("反选", "invert"), ("取消选择", "none")):
            ttk.Button(select_bar, text=label, command=lambda m=mode: self.select(m)).pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(select_bar, text="停止操作", command=self.cancelled.set, state="disabled")
        self.stop_button.pack(side="right")
        holder = ttk.Frame(body)
        holder.grid(row=3, column=0, sticky="nsew")
        self.tree = ttk.Treeview(holder, columns=("favorite", "id", "title", "format"), height=1, show="headings", selectmode="extended")
        for name, label, width in (("favorite", "收藏", 65), ("id", "编号", 100), ("title", "标题 / 文件名", 590), ("format", "格式", 75)):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, stretch=name == "title")
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.action("open"))
        self.tree.bind("<<TreeviewSelect>>", self.details)
        # Reserve footer space independently of the list's requested height.
        footer = ttk.Frame(body)
        footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        self.detail = tk.StringVar()
        ttk.Label(footer, textvariable=self.detail, width=1).grid(row=0, column=0, sticky="ew")
        self.path_text = tk.StringVar()
        self.path_entry = ttk.Entry(footer, textvariable=self.path_text, state="readonly", width=1)
        self.path_entry.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        self.status = tk.StringVar()
        ttk.Label(footer, textvariable=self.status, width=1).grid(row=2, column=0, sticky="ew", pady=(3, 5))
        self.action_buttons = {}
        for row, pairs in enumerate(((("打开图片 / 文件", "open"), ("导出", "export"), ("打开保存目录", "folder")),
                      (("批量收藏", "favorite_on"), ("取消收藏", "favorite_off"), ("批量删除文件", "delete"), ("仅移除记录", "forget"))), start=3):
            actions = ttk.Frame(footer)
            actions.grid(row=row, column=0, sticky="ew", pady=3)
            for label, action in pairs:
                button = ttk.Button(actions, text=label, command=lambda a=action: self.action(a))
                button.pack(side="left", padx=(0, 6))
                self.action_buttons[action] = button
        self.refresh()
        self.window.update_idletasks()
        # Leave at least a heading and a few rows after honoring the actual font metrics.
        fixed_height = body.winfo_reqheight() - holder.winfo_reqheight()
        min_width = max(850, bar.winfo_reqwidth() + 32, select_bar.winfo_reqwidth() + 32, footer.winfo_reqwidth() + 32)
        self.window.minsize(min_width, max(520, fixed_height + 100))

    def close(self):
        if self.busy:
            self.cancelled.set()
            self.status.set("正在停止；当前文件操作结束后即可关闭。")
        else:
            self.window.destroy()

    def select(self, mode):
        if self.busy:
            return
        children = self.tree.get_children()
        selected = set(self.tree.selection())
        self.tree.selection_set(children if mode == "all" else [k for k in children if k not in selected] if mode == "invert" else [])

    def refresh(self):
        if self.busy:
            return
        try:
            self.library.sync(self.app.engine.tasks)
            self.render()
        except Exception as exc:
            self.messagebox.showerror("无法读取漫画列表", str(exc), parent=self.window)

    def render(self):
        if self.busy:
            return
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for key, item in self.library.select(self.query.get(), self.only_favorites.get()):
            self.tree.insert("", "end", iid=key, values=("★" if item["favorite"] else "", item["id"] or "未识别", item["title"], item["format"].upper()))
        self.tree.selection_set([k for k in selected if self.tree.exists(k)])
        self.details()

    def details(self, *_):
        if self.busy:
            return
        selected = self.tree.selection()
        path = self.library.entries[selected[0]]["path"] if len(selected) == 1 and selected[0] in self.library.entries else ""
        self.detail.set(f"当前显示 {len(self.tree.get_children())} 项，已选 {len(selected)} 项")
        self.path_text.set(path)

    def run(self, operation, finished, pause_required=False):
        if self.busy:
            return
        if pause_required and (self.app.engine.running or any(t.status in ("running", "resetting") for t in self.app.engine.tasks)):
            self.messagebox.showinfo("请先暂停", "导出、批量删除或移除记录前，请先暂停下载队列。", parent=self.window)
            return
        self.busy = True
        self.cancelled.clear()
        self.stop_button.configure(state="normal")
        self.status.set("正在处理…")
        self.window.grab_set()
        def worker():
            try:
                self.events.put(("done", operation()))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        def poll():
            try:
                while True:
                    kind, value = self.events.get_nowait()
                    if kind == "progress":
                        self.status.set(value)
                        continue
                    self.busy = False
                    self.stop_button.configure(state="disabled")
                    self.window.grab_release()
                    try:
                        if kind == "error":
                            raise OSError(value)
                        finished(value)
                    except Exception as exc:
                        self.messagebox.showerror("操作未完成", str(exc), parent=self.window)
                    self.render()
                    return
            except queue.Empty:
                self.window.after(80, poll)
        self.window.after(80, poll)

    def scan(self):
        if self.busy:
            return
        folder = self.app.output_var.get().strip()
        if not self.messagebox.askyesno("扫描保存目录", "导入此目录中的 JM Batch 图片目录及 PDF / ZIP。图片目录按清单验证；重复项保留收藏和标题。\n\n" + folder, parent=self.window):
            return
        def finish(result):
            found, skipped = result
            if self.cancelled.is_set():
                self.status.set("扫描已取消，未导入文件")
                return
            added = self.library.import_found(found)
            self.status.set(f"扫描完成：新增 {added} 项，已存在 {len(found)-added} 项，跳过 {skipped} 项。")
        self.run(lambda: self.library.discover(folder, self.cancelled), finish)

    def action(self, action):
        if self.busy:
            return
        selected = list(self.tree.selection())
        if not selected:
            return
        try:
            if action == "export":
                if len(selected) != 1:
                    raise ValueError("请选择一本图片漫画导出")
                from export_ui import show_export
                show_export(self, selected[0])
            elif action in ("favorite", "favorite_on", "favorite_off"):
                if action == "favorite":
                    self.library.favorite(selected[0])
                else:
                    self.library.set_favorites(selected, action == "favorite_on")
                self.status.set(f"已更新 {len(selected)} 项收藏")
                self.render()
            elif action in ("open", "folder"):
                if len(selected) != 1:
                    self.messagebox.showinfo("请选择一项", "打开文件或目录时请选择一项。", parent=self.window)
                    return
                self.app._open(self.library.checked_path(selected[0]) if action == "open" else Path(self.library.entries[selected[0]]["root"]))
            else:
                delete = action == "delete"
                preview = "\n".join(self.library.entries[k]["path"] for k in selected[:8])
                if len(selected) > 8:
                    preview += f"\n……另 {len(selected)-8} 项"
                prompt = "永久删除所选图片目录及全部图片，或所选 PDF / ZIP，不进入回收站。" if delete else "只移除选中的记录与收藏，文件保留；以后可重新扫描导入。"
                if not self.messagebox.askyesno(f"确认处理 {len(selected)} 项", prompt + "\n\n" + preview, parent=self.window):
                    return
                def finished(result):
                    done, errors, unprocessed = result
                    self.app.engine.save()
                    self.app.render()
                    self.status.set(f"成功 {len(done)} 项，失败 {len(errors)} 项，未处理 {unprocessed} 项。")
                    if errors:
                        self.messagebox.showwarning("部分操作失败", "失败记录已保留：\n\n" + "\n".join(f"{Path(k).name}：{error}" for k, error in errors[:20]), parent=self.window)
                self.run(lambda: self.library.remove_many(selected, self.app.engine.tasks, delete, self.cancelled,
                         lambda done, total: self.events.put(("progress", f"正在处理 {done} / {total} 项"))), finished, True)
        except Exception as exc:
            self.messagebox.showerror("操作未完成", str(exc), parent=self.window)
