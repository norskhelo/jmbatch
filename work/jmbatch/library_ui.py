"""Library UI. Slow directory and batch operations run outside Tk's thread."""
import queue
import threading
from collections import OrderedDict
from pathlib import Path


class LibraryWindow:
    def __init__(self, app):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.app, self.library = app, app.engine.library
        self.messagebox = messagebox
        self.busy = False
        self.batch_mode = False
        self.press_timer = None
        self.pressed = None
        self.row_press = False
        self.filter = ("", False)
        self.cancelled = threading.Event()
        self.events = queue.Queue()
        from covers import CoverWorker
        self.cover_worker = CoverWorker()
        self.cover_generation = 0
        self.cover_pending = set()
        self.cover_images = OrderedDict()
        self.window = tk.Toplevel(app.root)
        self.window.title("漫画库")
        self.window.geometry("1000x640")
        self.window.minsize(850, 520)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        body = ttk.Frame(self.window, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)
        self.hint = tk.StringVar(value="点击漫画开始阅读，长按进入批量处理。")
        ttk.Label(body, textvariable=self.hint).grid(row=0, column=0, sticky="w")
        bar = ttk.Frame(body)
        bar.grid(row=1, column=0, sticky="ew", pady=8)
        bar.columnconfigure(1, weight=1)
        self.query = tk.StringVar()
        self.only_favorites = tk.BooleanVar()
        ttk.Label(bar, text="搜索编号或标题").grid(row=0, column=0)
        ttk.Entry(bar, textvariable=self.query, width=18).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Checkbutton(bar, text="仅显示收藏", variable=self.only_favorites, command=self.render).grid(row=0, column=2)
        ttk.Button(bar, text="扫描保存目录", command=self.scan).grid(row=0, column=3, padx=6)
        ttk.Button(bar, text="刷新", command=self.refresh).grid(row=0, column=4)
        self.query.trace_add("write", lambda *_: self.render())
        select_bar = ttk.Frame(body)
        select_bar.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.mode_button = ttk.Button(select_bar, text="批量处理", command=self.toggle_batch)
        self.mode_button.pack(side="left", padx=(0, 6))
        self.selection_controls = ttk.Frame(select_bar)
        self.selection_controls.pack(side="left")
        for label, mode in (("全选", "all"), ("反选", "invert"), ("取消选择", "none")):
            ttk.Button(self.selection_controls, text=label, command=lambda m=mode: self.select(m)).pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(select_bar, text="停止操作", command=self.cancelled.set, state="disabled")
        self.stop_button.pack(side="right")
        holder = ttk.Frame(body)
        holder.grid(row=3, column=0, sticky="nsew")
        ttk.Style(self.window).configure("Library.Treeview", rowheight=106)
        self.tree = ttk.Treeview(holder, columns=("favorite", "id", "title", "format"), height=1, show="tree headings", selectmode="none", style="Library.Treeview")
        self.tree.heading("#0", text="封面")
        self.tree.column("#0", width=92, minwidth=92, stretch=False)
        from PIL import Image, ImageDraw, ImageTk
        placeholder = Image.new("RGB", (72, 96), "#e8edf1")
        draw = ImageDraw.Draw(placeholder)
        draw.rectangle((19, 22, 53, 74), outline="#96a6b2", width=2)
        for y in (38, 48, 58):
            draw.line((26, y, 46, y), fill="#96a6b2", width=2)
        self.cover_placeholder = ImageTk.PhotoImage(placeholder, master=self.window)
        for name, label, width in (("favorite", "收藏", 55), ("id", "编号", 90), ("title", "标题 / 文件名", 490), ("format", "格式", 75)):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, stretch=name == "title")
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<ButtonPress-1>", self.press)
        self.tree.bind("<ButtonRelease-1>", self.release)
        self.tree.bind("<Double-ButtonPress-1>", self.repeat_press)
        self.tree.bind("<Triple-ButtonPress-1>", self.repeat_press)
        self.tree.bind("<B1-Motion>", self.motion)
        for event in ("<Leave>", "<MouseWheel>", "<FocusOut>"):
            self.tree.bind(event, lambda e: self.cancel_press(), add="+")
        self.tree.bind("<Return>", self.keyboard_activate)
        self.tree.bind("<space>", self.keyboard_activate)
        self.tree.bind("<Control-a>", lambda e: self.select("all") or "break")
        self.window.bind("<Escape>", lambda e: self.exit_batch())
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
        self.batch_rows = []
        for row, pairs in enumerate(((("开始阅读", "open"), ("导出漫画", "export"), ("打开保存目录", "folder")),
                      (("批量收藏", "favorite_on"), ("取消收藏", "favorite_off"), ("批量删除文件", "delete"), ("仅移除记录", "forget"))), start=3):
            actions = ttk.Frame(footer)
            actions.grid(row=row, column=0, sticky="ew", pady=3)
            self.batch_rows.append(actions)
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
        self.update_mode()
        self.cover_timer = self.window.after(100, self.poll_covers)
        self.window.bind("<Destroy>", self.cover_destroyed, add="+")

    def cover_destroyed(self, event):
        if event.widget == self.window:
            self.cancel_press()
            self.cover_worker.close()
            self.window.after_cancel(self.cover_timer)
            self.cover_images.clear()

    def cancel_press(self):
        if self.press_timer is not None:
            self.window.after_cancel(self.press_timer)
            self.press_timer = None
        self.pressed = None

    def press(self, event):
        self.cancel_press()
        self.row_press = False
        key = self.tree.identify_row(event.y)
        if self.busy:
            return "break"
        if not key or self.tree.identify_region(event.x, event.y) not in ("tree", "cell"):
            return
        self.tree.focus_set()
        self.tree.focus(key)
        self.row_press = True
        self.pressed = (key, event.x, event.y, event.state)
        self.press_timer = self.window.after(500, self.long_press)
        return "break"

    def repeat_press(self, event):
        if self.batch_mode:
            return self.press(event)
        self.cancel_press()
        return "break"

    def motion(self, event):
        if not self.row_press:
            return
        if self.pressed and (abs(event.x-self.pressed[1]) > 8 or abs(event.y-self.pressed[2]) > 8):
            self.cancel_press()
        return "break"

    def long_press(self):
        pressed = self.pressed
        self.cancel_press()
        if pressed and not self.busy and self.tree.exists(pressed[0]):
            self.enter_batch(pressed[0])

    def release(self, event):
        row_press, self.row_press = self.row_press, False
        pressed = self.pressed
        self.cancel_press()
        if (pressed and not self.busy and self.tree.identify_row(event.y) == pressed[0]
                and abs(event.x-pressed[1]) <= 8 and abs(event.y-pressed[2]) <= 8):
            if self.batch_mode:
                key = pressed[0]
                if key in self.tree.selection():
                    self.tree.selection_remove(key)
                else:
                    self.tree.selection_add(key)
                self.details()
            else:
                self.app.read_comic(pressed[0])
        return "break" if row_press else None

    def keyboard_activate(self, event=None):
        key = self.tree.focus()
        if not self.busy and key and self.tree.exists(key):
            if self.batch_mode:
                if key in self.tree.selection():
                    self.tree.selection_remove(key)
                else:
                    self.tree.selection_add(key)
                self.details()
            else:
                self.app.read_comic(key)
        return "break"

    def enter_batch(self, key=None):
        if self.busy:
            return
        if not self.batch_mode:
            self.tree.selection_set(())
        self.batch_mode = True
        if key and self.tree.exists(key):
            self.tree.selection_add(key)
        self.update_mode()

    def exit_batch(self):
        if self.busy:
            return "break"
        self.cancel_press()
        self.batch_mode = False
        self.tree.selection_set(())
        self.update_mode()
        return "break"

    def toggle_batch(self):
        if self.batch_mode:
            self.exit_batch()
        else:
            self.enter_batch()

    def update_mode(self):
        self.mode_button.configure(text="完成" if self.batch_mode else "批量处理")
        self.hint.set("批量处理：点击漫画勾选或取消，点击“完成”或按 Esc 退出。" if self.batch_mode else "点击漫画开始阅读，长按进入批量处理。")
        if self.batch_mode:
            self.selection_controls.pack(side="left")
            self.path_entry.grid()
            for row in self.batch_rows:
                row.grid()
        else:
            self.selection_controls.pack_forget()
            self.path_entry.grid_remove()
            for row in self.batch_rows:
                row.grid_remove()
        self.details()

    def poll_covers(self):
        from PIL import ImageTk
        try:
            while True:
                generation, key, result = self.cover_worker.results.get_nowait()
                if generation != self.cover_generation:
                    continue
                self.cover_pending.discard(key)
                if not self.tree.exists(key):
                    continue
                photo = ImageTk.PhotoImage(result, master=self.window) if result is not None else self.cover_placeholder
                self.cover_images[key] = photo
                self.tree.item(key, image=photo)
                while len(self.cover_images) > 64:
                    old, _ = self.cover_images.popitem(last=False)
                    if self.tree.exists(old):
                        self.tree.item(old, image=self.cover_placeholder)
        except queue.Empty:
            pass
        # Request only visible rows; Tk images are created only on Tk's thread.
        visible = dict.fromkeys(self.tree.identify_row(y) for y in range(0, self.tree.winfo_height(), 20))
        for key in visible:
            if not key:
                continue
            if key in self.cover_images:
                self.cover_images.move_to_end(key)
            elif key not in self.cover_pending and key in self.library.entries:
                item = self.library.entries[key]
                try:
                    self.cover_worker.jobs.put_nowait((self.cover_generation, key, item["path"], item["format"]))
                    self.cover_pending.add(key)
                except queue.Full:
                    break
        self.cover_timer = self.window.after(100, self.poll_covers)

    def close(self):
        if self.busy:
            self.cancelled.set()
            self.status.set("正在停止操作，请稍候。当前文件处理完成后即可关闭。")
        else:
            self.window.destroy()

    def select(self, mode):
        if self.busy:
            return
        self.enter_batch()
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
        self.cancel_press()
        current_filter = (self.query.get(), self.only_favorites.get())
        selected = self.tree.selection() if current_filter == self.filter and self.batch_mode else ()
        self.filter = current_filter
        self.cover_generation += 1
        self.cover_worker.clear()
        self.cover_pending.clear()
        self.cover_images.clear()
        self.tree.delete(*self.tree.get_children())
        for key, item in self.library.select(self.query.get(), self.only_favorites.get()):
            self.tree.insert("", "end", iid=key, image=self.cover_placeholder, values=("★" if item["favorite"] else "", item["id"] or "未识别", item["title"], item["format"].upper()))
        self.tree.selection_set([k for k in selected if self.tree.exists(k)])
        self.details()

    def details(self, *_):
        if self.busy:
            return
        selected = self.tree.selection()
        path = self.library.entries[selected[0]]["path"] if len(selected) == 1 and selected[0] in self.library.entries else ""
        self.detail.set(f"当前显示 {len(self.tree.get_children())} 项" + (f"，已选 {len(selected)} 项" if self.batch_mode else ""))
        self.path_text.set(path)
        for action, button in self.action_buttons.items():
            enabled = self.batch_mode and (len(selected) == 1 if action in ("open", "folder") else bool(selected))
            button.configure(state="normal" if enabled else "disabled")

    def run(self, operation, finished, pause_required=False):
        if self.busy:
            return
        if pause_required and (self.app.engine.running or any(t.status in ("running", "resetting") for t in self.app.engine.tasks)):
            self.messagebox.showinfo("请先暂停", "导出、批量删除或移除记录前，请先暂停下载队列。", parent=self.window)
            return
        self.busy = True
        self.cancel_press()
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
        if not self.messagebox.askyesno("扫描保存目录", "将此目录中可识别的图片文件夹、PDF 和 ZIP 添加到漫画库。已存在的漫画保留原有标题和收藏。\n\n" + folder, parent=self.window):
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
                from export_ui import show_export
                show_export(self, selected)
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
                if action == "open":
                    self.app.read_comic(selected[0])
                else:
                    self.app._open(Path(self.library.entries[selected[0]]["root"]))
            else:
                delete = action == "delete"
                preview = "\n".join(self.library.entries[k]["path"] for k in selected[:8])
                if len(selected) > 8:
                    preview += f"\n……另 {len(selected)-8} 项"
                prompt = "永久删除所选图片目录及全部图片，或所选 PDF / ZIP，不进入回收站。" if delete else "只移除选中的记录与收藏，文件保留；以后可重新扫描导入。"
                if not self.messagebox.askyesno("确认删除文件" if delete else "确认移除记录", prompt + "\n\n" + preview, parent=self.window):
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
