"""Native Tk reader: virtual continuous pages or a fitted single page."""
import bisect
import queue
from collections import OrderedDict
import tkinter as tk
from tkinter import ttk, messagebox

from reader import ReaderState, ReaderWorker
from reader_paging import CanvasPager
from reader_chrome import ReaderChrome, TapGesture


class ReaderWindow:
    def __init__(self, app, key):
        self.app, self.key = app, key
        self.library = app.engine.library
        entry = self.library.entries[key]
        self.window = tk.Toplevel(app.root)
        self.window.title("阅读 · " + entry["title"])
        self.window.geometry("1000x820")
        self.window.minsize(740, 520)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.closed = False
        self.pages, self.chapters, self.starts = [], [], []
        self.current = 0
        self.marks = set()
        self.mode = tk.StringVar(value="滚动阅读")
        self.generation = 0
        self.images, self.errors = OrderedDict(), {}
        self.pending = set()
        self.heights, self.offsets = [], [0]
        self.save_timer = self.resize_timer = None
        self.state_error_shown = False
        if not hasattr(app, "reader_state"):
            app.reader_state = ReaderState(app.home)
        self.state = app.reader_state
        outer = ttk.Frame(self.window)
        outer.pack(fill="both", expand=True)
        self.top = ttk.Frame(outer)
        self.top.pack(side='top', fill='x')
        self.bottom = ttk.Frame(outer)
        self.bottom.pack(side='bottom', fill='x')
        top_content = ttk.Frame(self.top, padding=(10, 8))
        top_content.pack(fill='x')
        bottom_content = ttk.Frame(self.bottom, padding=(10, 6))
        bottom_content.pack(fill='x')
        bar = ttk.Frame(top_content)
        bar.pack(fill="x")
        ttk.Button(bar, text="上一章", command=lambda: self.chapter_step(-1)).pack(side="left")
        self.chapter_box = ttk.Combobox(bar, state="readonly", width=24)
        self.chapter_box.pack(side="left", padx=6)
        self.chapter_box.bind("<<ComboboxSelected>>", lambda e: self.go(self.starts[self.chapter_box.current()]))
        ttk.Button(bar, text="下一章", command=lambda: self.chapter_step(1)).pack(side="left")
        self.favorite_button = ttk.Button(bar, command=self.favorite)
        self.favorite_button.pack(side="right")
        bar2 = ttk.Frame(top_content)
        bar2.pack(fill="x", pady=8)
        modes = ttk.Combobox(bar2, textvariable=self.mode, state="readonly", values=("滚动阅读", "左右翻页"), width=12)
        modes.pack(side="left")
        modes.bind("<<ComboboxSelected>>", lambda e: self.relayout())
        ttk.Button(bar2, text="‹ 上一页", command=lambda: self.step(-1)).pack(side="left", padx=(8, 3))
        ttk.Button(bar2, text="下一页 ›", command=lambda: self.step(1)).pack(side="left")
        self.jump = tk.StringVar(value="1")
        jump = ttk.Entry(bar2, textvariable=self.jump, width=6)
        jump.pack(side="left", padx=(10, 2))
        jump.bind("<Return>", lambda e: self.jump_page())
        ttk.Button(bar2, text="跳转页码", command=self.jump_page).pack(side="left")
        ttk.Button(bar2, text="书签列表", command=self.bookmarks).pack(side="right")
        self.mark_button = ttk.Button(bar2, text="添加书签", command=self.mark)
        self.mark_button.pack(side="right", padx=4)
        holder = ttk.Frame(outer)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg="#20252c", highlightthickness=0, yscrollincrement=30)
        self.scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.scroll)
        self.canvas.pack(fill="both", expand=True)
        self.scrollbar.place(relx=1, x=0, y=0, anchor='ne', relheight=1)
        self.canvas.configure(yscrollcommand=self.scrolled)
        self.canvas.bind("<Configure>", self.resize)
        self.canvas.bind("<MouseWheel>", self.wheel)
        self.canvas.bind("<Button-4>", lambda e: self.wheel_step(-1))
        self.canvas.bind("<Button-5>", lambda e: self.wheel_step(1))
        self.pager = CanvasPager(self.canvas, self.window, lambda i: self.images.get(i), self.draw, self.page_committed)
        self.pager.enabled = False
        self.tap = TapGesture()
        self.canvas.bind("<ButtonPress-1>", self.pointer_down)
        self.canvas.bind("<B1-Motion>", self.pointer_move)
        self.canvas.bind("<ButtonRelease-1>", self.pointer_up)
        self.window.bind('<Escape>', lambda e: self.chrome.show(True))
        for sequence, delta in (("<Left>", -1), ("<Right>", 1), ("<Prior>", -1), ("<Next>", 1)):
            self.window.bind(sequence, lambda e, d=delta: self.key_page(e, d))
        self.status = tk.StringVar(value="正在读取漫画…")
        ttk.Label(bottom_content, textvariable=self.status).pack(anchor="w")
        ttk.Label(bottom_content, text="点击漫画隐藏或显示工具栏；左右拖动 / 方向键翻页，鼠标滚轮滚动；Esc 显示工具栏").pack(anchor="w")
        self.chrome = ReaderChrome(outer, self.top, self.bottom, (top_content, bottom_content), holder, self.chrome_changed)
        self.viewport_size = (0, 0)
        self.worker = ReaderWorker(entry["path"])
        self.timer = self.window.after(60, self.poll)
        self.refresh_buttons()

    def is_scroll(self):
        return self.mode.get() == "滚动阅读"

    def key_page(self, event, delta):
        if isinstance(event.widget, (ttk.Entry, ttk.Combobox, tk.Listbox)):
            return
        self.step(delta)
        return "break"

    def pointer_down(self, event):
        self.canvas.focus_set()
        self.tap.down(event.x_root, event.y_root)
        self.pager.press(event)

    def pointer_move(self, event):
        self.tap.move(event.x_root, event.y_root)
        self.pager.move(event)

    def pointer_up(self, event):
        tapped = self.tap.up(event.x_root, event.y_root)
        self.pager.release(event)
        if tapped and self.pages:
            self.chrome.toggle()
            self.update_scrollbar()

    def update_scrollbar(self):
        if self.is_scroll() and self.chrome.visible:
            self.scrollbar.place(relx=1, x=0, y=0, anchor='ne', relheight=1)
            self.scrollbar.lift()
        else:
            self.scrollbar.place_forget()

    def chrome_changed(self):
        self.update_scrollbar()
        if self.resize_timer:
            self.window.after_cancel(self.resize_timer)
        self.resize_timer = self.window.after_idle(self.finish_resize)

    def finish_resize(self):
        self.resize_timer = None
        if self.closed or self.chrome.animating or not self.pages:
            return
        size = (self.canvas.winfo_width(), self.canvas.winfo_height())
        if size == self.viewport_size:
            return
        if self.is_scroll() and size[0] == self.viewport_size[0]:
            # Height-only expansion keeps decoded pages and the exact scroll offset.
            top = self.canvas.canvasy(0)
            self.viewport_size = size
            self.layout()
            self.canvas.yview_moveto(top / self.extent)
            self.draw()
        else:
            self.relayout()

    def resize(self, event):
        if self.resize_timer:
            self.window.after_cancel(self.resize_timer)
        if not hasattr(self, 'chrome') or self.chrome.animating:
            self.resize_timer = None
            if hasattr(self, 'pager') and self.pager.enabled and not self.pager.animating and self.pager.drag is None:
                self.pager.place()
            return
        self.resize_timer = self.window.after(180, self.finish_resize)

    def relayout(self):
        self.resize_timer = None
        if not self.pages:
            return
        self.viewport_size = (self.canvas.winfo_width(), self.canvas.winfo_height())
        target = self.pager.target if self.pager.enabled and not self.is_scroll() else self.current
        self.generation += 1
        self.images.clear()
        self.errors.clear()
        self.pending.clear()
        self.heights = [max(200, min(1600, self.canvas.winfo_width() - 32)) * 1.4] * len(self.pages)
        if self.is_scroll():
            self.pager.hide()
        self.update_scrollbar()
        self.layout()
        if not self.is_scroll():
            self.canvas.delete('scroll')
            self.pager.activate(len(self.pages), target)
        self.go(target)

    def layout(self):
        self.offsets = [0]
        for height in self.heights:
            self.offsets.append(self.offsets[-1] + height)
        self.extent = self.offsets[-1] + max(0, self.canvas.winfo_height() - 50)
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), self.extent if self.is_scroll() else self.canvas.winfo_height()))

    def scroll(self, *args):
        self.canvas.yview(*args)
        self.draw()

    def scrolled(self, first, last):
        self.scrollbar.set(first, last)
        if self.pages and self.is_scroll():
            self.current = max(0, min(len(self.pages) - 1, bisect.bisect_right(self.offsets, self.canvas.canvasy(0) + 40) - 1))
            self.refresh_buttons()
            self.schedule_save()
            self.draw()

    def wheel(self, event):
        return self.wheel_step(-1 if event.delta > 0 else 1)

    def wheel_step(self, delta):
        if self.is_scroll():
            self.scroll("scroll", delta * 3, "units")
        else:
            self.step(delta)
        return "break"

    def step(self, delta):
        self.go((self.current if self.is_scroll() else self.pager.target) + delta)

    def page_committed(self, index):
        self.current = index
        self.refresh_buttons()
        self.schedule_save()

    def go(self, index):
        if not self.pages:
            return
        index = max(0, min(len(self.pages) - 1, index))
        if not self.is_scroll():
            self.canvas.yview_moveto(0)
            self.pager.go(index)
            return
        self.current = index
        if self.is_scroll():
            self.canvas.yview_moveto(self.offsets[self.current] / self.extent)
        else:
            self.canvas.yview_moveto(0)
        self.refresh_buttons()
        self.draw()
        self.schedule_save()

    def chapter_step(self, delta):
        if self.starts:
            chapter = bisect.bisect_right(self.starts, self.current) - 1
            self.go(self.starts[max(0, min(len(self.starts) - 1, chapter + delta))])

    def jump_page(self):
        try:
            page = int(self.jump.get())
            if not 1 <= page <= len(self.pages):
                raise ValueError()
            self.go(page - 1)
        except ValueError:
            messagebox.showinfo("跳转页码", f"请输入 1 至 {len(self.pages)} 的总页码。", parent=self.window)

    def draw(self):
        if self.closed or not self.pages:
            return
        if not self.is_scroll():
            self.draw_paged()
            return
        self.canvas.delete("scroll")
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.is_scroll():
            top = self.canvas.canvasy(0)
            first = max(0, bisect.bisect_right(self.offsets, top) - 1)
            last = min(len(self.pages), bisect.bisect_right(self.offsets, top + height) + 1)
            visible = list(range(first, min(last, first + 6)))
        else:
            visible = [self.current]
        for index in visible:
            y = self.offsets[index] if self.is_scroll() else 0
            photo = self.images.get(index)
            if photo:
                self.images.move_to_end(index)
                if not self.is_scroll():
                    y = max(0, (height - photo.height()) / 2)
                self.canvas.create_image(width / 2, y, image=photo, anchor="n", tags='scroll')
            else:
                self.canvas.create_text(width / 2, y + (50 if self.is_scroll() else height / 2), text=self.errors.get(index, "正在加载…"), fill="white", width=max(100, width - 80), tags='scroll')
        # Replace obsolete work. Already decoded results are accepted only for this layout.
        needed = [i for i in visible if i not in self.images and i not in self.errors]
        self.pending = set(needed)
        self.worker.request([(self.generation, i, width - 32, 0 if self.is_scroll() else max(100, height - 24)) for i in needed])
        while len(self.images) > 6:
            candidates = [i for i in self.images if i not in visible]
            if not candidates:
                break
            self.images.pop(candidates[0])

    def draw_paged(self):
        self.pager.ready()
        target = self.pager.target
        width = max(100, self.canvas.winfo_width() - 32)
        height = max(100, self.canvas.winfo_height() - 24)
        desired = [target]
        if target == self.pager.page and not self.pager.animating:
            desired += [target + self.pager.direction, target - self.pager.direction]
        budget = 32 * 1024 * 1024
        estimate = min(4_000_000, min(1600, width) * min(8192, height)) * 4
        desired = [i for i in desired if 0 <= i < len(self.pages)][:max(1, budget // max(1, estimate))]
        for index in desired:
            if index in self.images:
                self.images.move_to_end(index)
        size = sum(p.width() * p.height() * 4 for p in self.images.values())
        for index in list(self.images):
            if len(self.images) <= 6 and size <= budget:
                break
            if index in (self.pager.page, target):
                continue
            photo = self.images.pop(index)
            size -= photo.width() * photo.height() * 4
        needed = [i for i in desired if i not in self.images and i not in self.errors]
        self.pending = set(needed)
        self.worker.request([(self.generation, i, width, height) for i in needed])
        if needed and getattr(self, 'timer', None):
            self.window.after_cancel(self.timer)
            self.timer = self.window.after(16, self.poll)
        if target in self.errors:
            self.pager.error(self.errors[target])

    def poll(self):
        from PIL import ImageTk
        self.timer = None
        dirty = False
        try:
            while True:
                result = self.worker.results.get_nowait()
                kind = result[0]
                if kind == "ready":
                    self.pages = result[1]
                    for i, page in enumerate(self.pages):
                        if page["chapter"] not in self.chapters:
                            self.chapters.append(page["chapter"])
                            self.starts.append(i)
                    self.chapter_box["values"] = [f"第 {c} 章（{(self.starts + [len(self.pages)])[i+1] - self.starts[i]} 页）" for i, c in enumerate(self.chapters)]
                    try:
                        saved = self.state.get(self.key, len(self.pages))
                        self.current, self.marks = saved["page"], set(saved["bookmarks"])
                        self.mode.set("滚动阅读" if saved["mode"] == "scroll" else "左右翻页")
                    except ValueError as exc:
                        self.state.error = str(exc)
                    self.relayout()
                elif kind == "fatal":
                    self.status.set("无法阅读：" + result[1])
                    messagebox.showerror("无法阅读", result[1], parent=self.window)
                else:
                    _, generation, index, value = result
                    self.worker.acknowledge(generation, index)
                    if generation != self.generation:
                        if kind == "image":
                            value.close()
                        continue
                    self.pending.discard(index)
                    if kind == "image":
                        self.images[index] = ImageTk.PhotoImage(value, master=self.window)
                        if self.is_scroll():
                            anchor = self.current
                            offset = self.canvas.canvasy(0) - self.offsets[anchor]
                            self.heights[index] = value.height
                            self.layout()
                            self.canvas.yview_moveto((self.offsets[anchor] + offset) / self.extent)
                        value.close()
                    else:
                        self.errors[index] = "本页读取失败，可跳到下一页：\n" + value
                    dirty = True
        except queue.Empty:
            pass
        if dirty:
            self.draw()
        self.timer = self.window.after(16 if self.pending or self.pager.animating else 80, self.poll)

    def refresh_buttons(self):
        entry = self.library.entries.get(self.key, {})
        self.favorite_button.configure(text="★ 已收藏" if entry.get("favorite") else "☆ 收藏")
        self.mark_button.configure(text="移除本页书签" if self.current in self.marks else "添加书签")
        if self.pages:
            chapter = bisect.bisect_right(self.starts, self.current) - 1
            self.chapter_box.current(chapter)
            count = (self.starts + [len(self.pages)])[chapter + 1] - self.starts[chapter]
            self.status.set(f"第 {self.pages[self.current]['chapter']} 章 · 本章 {self.current-self.starts[chapter]+1}/{count} 页 · 总页码 {self.current+1}/{len(self.pages)}" + (" · PDF 按一个章节显示" if self.library.entries.get(self.key, {}).get("format") == "pdf" else ""))
            if self.window.focus_get() is not None and not isinstance(self.window.focus_get(), ttk.Entry):
                self.jump.set(str(self.current + 1))

    def favorite(self):
        try:
            self.library.favorite(self.key)
            self.refresh_buttons()
            library_window = getattr(self.app, "library_window", None)
            if library_window and library_window.window.winfo_exists():
                library_window.render()
        except Exception as exc:
            messagebox.showerror("收藏失败", str(exc), parent=self.window)

    def mark(self):
        if not self.pages:
            return
        if self.current in self.marks:
            self.marks.remove(self.current)
        else:
            self.marks.add(self.current)
        self.save()
        self.refresh_buttons()

    def bookmarks(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("书签列表")
        dialog.geometry("430x380")
        box = tk.Listbox(dialog)
        box.pack(fill="both", expand=True, padx=12, pady=12)
        marks = sorted(self.marks)
        for i in marks:
            box.insert("end", f"第 {self.pages[i]['chapter']} 章 · 第 {self.pages[i]['page']} 页（总第 {i+1} 页）")
        if not marks:
            box.insert("end", "暂无书签。阅读时点击“添加书签”保存当前页。")
        def choose(remove=False):
            if not marks or not box.curselection():
                return
            index = marks[box.curselection()[0]]
            if remove:
                self.marks.discard(index)
                self.save()
                self.refresh_buttons()
            else:
                self.go(index)
            dialog.destroy()
        box.bind("<Double-1>", lambda e: choose())
        ttk.Button(dialog, text="跳转", command=choose).pack(side="left", padx=12, pady=8)
        ttk.Button(dialog, text="删除书签", command=lambda: choose(True)).pack(side="left", pady=8)

    def schedule_save(self):
        if self.save_timer:
            self.window.after_cancel(self.save_timer)
        self.save_timer = self.window.after(600, self.save)

    def save(self):
        if self.save_timer:
            self.window.after_cancel(self.save_timer)
        self.save_timer = None
        if self.pages:
            try:
                self.state.put(self.key, self.current, "scroll" if self.is_scroll() else "paged", self.marks)
            except Exception as exc:
                if not self.state_error_shown:
                    self.state_error_shown = True
                    messagebox.showwarning("阅读记录未保存", str(exc), parent=self.window)

    def close(self):
        if self.closed:
            return
        self.save()
        self.closed = True
        self.chrome.close()
        self.pager.close()
        for timer in (self.timer, self.save_timer, self.resize_timer):
            if timer:
                self.window.after_cancel(timer)
        self.worker.close()
        self.images.clear()
        self.app.readers.pop(self.key, None)
        self.window.destroy()


def open_reader(app, key):
    if not hasattr(app, "readers"):
        app.readers = {}
    existing = app.readers.get(key)
    if existing and not existing.closed:
        existing.window.lift()
        existing.window.focus_force()
        return existing
    reader = ReaderWindow(app, key)
    app.readers[key] = reader
    return reader
