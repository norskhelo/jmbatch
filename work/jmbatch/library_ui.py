"""Library UI. Slow directory and batch operations run outside Tk's thread."""
import queue
import threading
from collections import OrderedDict
from pathlib import Path


class LibraryWindow:
    def __init__(self, app, parent=None):
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
        self.collection = ""
        self.visible_items = {}
        self.cancelled = threading.Event()
        self.events = queue.Queue()
        from covers import CoverWorker
        from cover_cache import CoverCache
        cache = CoverCache(self.library.path.parent)
        from collection_covers import load_collection_cover
        self.cover_worker = CoverWorker(lambda path, fmt: load_collection_cover(path, cache.load) if fmt == "collection" else cache.load(path, fmt))
        self.cover_generation = 0
        self.cover_pending = set()
        self.cover_images = OrderedDict()
        from ui_library import build
        build(self,parent)

    def reset_page(self):
        self.cancel_press()
        self.pressed = None
        self.row_press = False
        self.batch_mode = self.moving = False
        self.moving_keys = []
        self.move_origin = self.collection = ""
        self.query.set("")
        self.only_favorites.set(False)
        self.tree.selection_set(())
        self.tree.focus("")
        self.status.set("")
        self.reset_viewport = True
        from ui_library import update_mode
        update_mode(self)
        self.render()
        self.tree.yview_moveto(0)

    def back(self):
        if self.moving:
            from ui_library import cancel_move
            cancel_move(self)
            return True
        if self.batch_mode:
            self.exit_batch()
            return True
        if self.collection:
            self.navigate("")
            return True
        return False

    def change_display(self):
        from display_view import save_mode
        if self.busy:
            self.display_mode.set(self.tree.mode)
            return
        self.cancel_press()
        self.tree.set_mode(self.display_mode.get())
        try:
            save_mode(self.library.path.parent, "library", self.display_mode.get())
        except OSError as exc:
            self.status.set(f"显示方式未能保存：{exc}")

    def navigate(self, collection):
        if self.busy:
            return "break"
        self.collection = collection
        if not self.moving:self.exit_batch()
        self.query.set("")
        self.only_favorites.set(False)
        self.render()
        return "break"

    def activate(self, key):
        if key in self.library.collections:
            self.navigate(key)
        elif key in self.library.entries and not self.moving:
            self.app.read_comic(key)

    def create_collection(self):
        from ui_library import new_collection
        new_collection(self)

    def choose_collection(self, title, callback, include_default=False):
        import tkinter as tk
        from tkinter import ttk
        choices = ([ ("", "漫画库（默认收藏夹）") ] if include_default else []) + list(self.library.collections.items())
        if not choices:
            self.messagebox.showinfo("收藏夹", "请先新建收藏夹。", parent=self.window)
            return
        dialog = tk.Toplevel(self.window)
        dialog.title(title)
        dialog.transient(self.window)
        box = tk.Listbox(dialog, width=44, height=min(12, len(choices)), exportselection=False)
        box.pack(fill="both", expand=True, padx=12, pady=12)
        for _, name in choices:
            box.insert("end", name)
        box.selection_set(0)
        def confirm():
            if box.curselection():
                key = choices[box.curselection()[0]][0]
                dialog.destroy()
                callback(key)
        ttk.Button(dialog, text="确定", command=confirm).pack(pady=(0, 12))
        box.bind("<Double-Button-1>", lambda e: confirm())
        dialog.grab_set()

    def manage_collection(self):
        if self.busy:
            return
        import tkinter as tk
        from tkinter import ttk, simpledialog
        def manage(key):
            dialog = tk.Toplevel(self.window)
            dialog.title("管理收藏夹")
            dialog.transient(self.window)
            ttk.Label(dialog, text=self.library.collection_name(key), wraplength=360).pack(padx=16, pady=16)
            def rename():
                name = simpledialog.askstring("重命名收藏夹", "收藏夹名称", initialvalue=self.library.collection_name(key), parent=dialog)
                if name is not None:
                    try:
                        self.library.rename_collection(key, name)
                        dialog.destroy()
                        self.render()
                    except Exception as exc:
                        self.messagebox.showerror("无法重命名", str(exc), parent=dialog)
            def delete():
                if self.messagebox.askyesno("删除收藏夹", "仅删除此收藏夹，其中的漫画将回到漫画库。漫画文件、星标和阅读记录保留。", parent=dialog):
                    try:
                        self.library.delete_collection(key)
                        dialog.destroy()
                        self.navigate("")
                    except Exception as exc:
                        self.messagebox.showerror("无法删除收藏夹", str(exc), parent=dialog)
            ttk.Button(dialog, text="重命名", command=rename).pack(padx=16, pady=4)
            ttk.Button(dialog, text="删除收藏夹", command=delete).pack(padx=16, pady=(4, 16))
            dialog.grab_set()
        keys = self.tree.selection()
        key = keys[0] if len(keys) == 1 and keys[0] in self.library.collections else self.collection
        if key:
            manage(key)
        else:
            self.choose_collection("选择要管理的收藏夹", manage)

    def cover_destroyed(self, event):
        if event.widget == self.window:
            if hasattr(self,'update_cancelled'):self.update_cancelled.set()
            self.cancel_press()
            self.cover_worker.close()
            self.window.after_cancel(self.cover_timer)
            if getattr(self,'chapter_scan_timer',None):self.window.after_cancel(self.chapter_scan_timer)
            self.cover_images.clear()

    def cancel_press(self):
        if self.press_timer is not None:
            self.window.after_cancel(self.press_timer)
            self.press_timer = None
        self.pressed = None

    def press(self, event):
        self.cancel_press()
        self.row_press = False
        key = self.tree.identify_at(event.x, event.y)
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
        if (pressed and not self.busy and self.tree.identify_at(event.x, event.y) == pressed[0]
                and abs(event.x-pressed[1]) <= 8 and abs(event.y-pressed[2]) <= 8):
            if self.batch_mode:
                key = pressed[0]
                if key in self.tree.selection():
                    self.tree.selection_remove(key)
                else:
                    self.tree.selection_add(key)
                self.details()
            else:
                self.activate(pressed[0])
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
                self.activate(key)
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
        from ui_library import update_mode
        update_mode(self)
        self.details()

    def poll_covers(self):
        from PIL import ImageTk
        from covers import fit_cover
        try:
            while True:
                generation, key, result = self.cover_worker.results.get_nowait()
                if generation != self.cover_generation:
                    continue
                self.cover_pending.discard(key)
                if not self.tree.exists(key):
                    continue
                photo = ImageTk.PhotoImage(fit_cover(result), master=self.window) if result is not None else self.cover_placeholder
                self.cover_images[key] = photo
                self.tree.item(key, image=photo)
                while len(self.cover_images) > 64:
                    old, _ = self.cover_images.popitem(last=False)
                    if self.tree.exists(old):
                        self.tree.item(old, image=self.cover_placeholder)
        except queue.Empty:
            pass
        # Request only visible rows; Tk images are created only on Tk's thread.
        visible = self.tree.visible_keys()
        for key in visible:
            if not key:
                continue
            if key in self.cover_images:
                self.cover_images.move_to_end(key)
            elif key not in self.cover_pending and key in self.visible_items:
                item = self.visible_items[key]
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
        if self.collection and self.collection not in self.library.collections:
            self.collection = ""
        current_filter = (self.query.get(), self.only_favorites.get(), self.collection)
        same_filter = current_filter == self.filter
        selected = self.tree.selection() if same_filter and self.batch_mode else ()
        children = self.tree.get_children()
        focus = self.tree.focus() if same_filter else ""
        position = self.tree.item_position() if children else 0
        first = min(int(position), max(0, len(children) - 1))
        self.filter = current_filter
        from ui_library import sorted_items
        items = sorted_items(self,self.library.browse(*current_filter))
        previous_folders = {k: v for k, v in self.visible_items.items() if k in self.library.collections}
        self.visible_items = dict(items)
        current_folders = {k: v for k, v in items if k in self.library.collections}
        self.breadcrumb.set("漫画库 / " + self.library.collection_name(self.collection) if self.collection else "漫画库（默认收藏夹）")
        self.back_button.configure(state="normal" if self.collection else "disabled")
        if previous_folders != current_folders and same_filter:
            self.cover_generation += 1
            self.cover_worker.clear()
            self.cover_pending.clear()
            self.cover_images.clear()
            for key in children:
                self.tree.item(key, image=self.cover_placeholder)
        keys = [key for key, _ in items]
        present = set(keys)
        if not same_filter:
            self.cover_generation += 1
            self.cover_worker.clear()
            self.cover_pending.clear()
            self.cover_images.clear()
            self.tree.delete(*children)
        else:
            for key in children:
                if key not in present:
                    self.tree.delete(key)
                    self.cover_images.pop(key, None)
        for index, (key, item) in enumerate(items):
            values = ("" if item["format"] == "collection" else "★" if item["favorite"] else "",
                      item["id"] + " 本" if item["format"] == "collection" else item["id"] or "未识别",
                      item["title"], "收藏夹" if item["format"] == "collection" else item["format"].upper())
            if self.tree.exists(key):
                self.tree.item(key, values=values)
                self.tree.move(key, "", index)
            else:
                self.tree.insert("", index, iid=key, image=self.cover_placeholder, values=values)
        self.tree.selection_set([k for k in selected if self.tree.exists(k)])
        if same_filter and keys:
            # Keep the first visible comic in place, even if rows above it changed.
            anchor = next((k for k in children[first:] if k in present), None)
            top = keys.index(anchor) if anchor else min(first, len(keys) - 1)
            self.tree.move_to_index(top + position - int(position))
            if focus in present:
                self.tree.focus(focus)
        elif not same_filter:
            self.tree.yview_moveto(0)
        if getattr(self, 'reset_viewport', False):
            self.tree.yview_moveto(0)
            self.reset_viewport = False
        self.details()
        from ui_library import prepare_chapter_counts
        prepare_chapter_counts(self)

    def details(self, *_):
        if self.busy:
            return
        selected = self.tree.selection()
        path = self.library.entries[selected[0]]["path"] if len(selected) == 1 and selected[0] in self.library.entries else ""
        from ui_library import update_mode
        update_mode(self)
        self.detail.set(f"当前显示 {len(self.tree.get_children())} 项" + (f"，已选 {len(selected)} 项" if self.batch_mode else ""))
        self.path_text.set(path)
        for action, button in self.action_buttons.items():
            enabled = self.batch_mode and (len(selected) == 1 if action in ("open", "folder", "chapters", "updates") else bool(selected))
            if any(k not in self.library.entries for k in selected) and action != "open":
                enabled = False
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
            if action == "open":
                if len(selected) == 1:
                    self.activate(selected[0])
                return
            if any(k not in self.library.entries for k in selected):
                self.messagebox.showinfo("请选择漫画", "此操作仅适用于漫画。收藏夹请使用“管理收藏夹”。", parent=self.window)
                return
            if action == "collection":
                def move(key):
                    try:
                        self.library.move_to_collection(selected, key)
                        self.status.set(f"已将 {len(selected)} 本漫画移入{self.library.collection_name(key)}")
                        self.render()
                    except Exception as exc:
                        self.messagebox.showerror("移动失败", str(exc), parent=self.window)
                self.choose_collection("移入收藏夹", move, True)
            elif action == "updates":
                if len(selected) == 1:
                    from chapter_updates import show
                    show(self, selected[0])
            elif action == "chapters":
                if len(selected) == 1:
                    from chapter_delete_ui import show
                    show(self, selected[0])
            elif action == "export":
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
