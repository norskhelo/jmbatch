"""Library chapter selection and explicit destructive confirmation."""
def show(library_window, key):
    import tkinter as tk
    from tkinter import ttk
    from chapter_delete import inspect, delete_chapters
    owner = library_window
    if key in getattr(owner.app, "readers", {}):
        owner.messagebox.showinfo("请先关闭阅读器", "请先关闭这本漫画的阅读窗口，再删除章节。", parent=owner.window)
        return

    def choose(plan):
        if len(plan["chapters"]) <= 1:
            owner.messagebox.showinfo("没有可单独删除的章节", "本书仅识别到一个章节。PDF 或平铺 ZIP 没有可分辨的分章信息；删除整本请使用“删除文件”。", parent=owner.window)
            return
        dialog = tk.Toplevel(owner.window)
        dialog.title("删除章节")
        dialog.geometry("480x420")
        dialog.transient(owner.window)
        dialog.grab_set()
        ttk.Label(dialog, text="勾选要删除的章节（至少保留一章）").pack(pady=12)
        box = tk.Listbox(dialog, selectmode="multiple", exportselection=False)
        box.pack(fill="both", expand=True, padx=16)
        chapters = list(plan["chapters"])
        for c in chapters:
            box.insert("end", f"第 {c} 章 · {plan['chapters'][c]} 页")
        def confirm():
            selected = [chapters[i] for i in box.curselection()]
            if not selected or len(selected) == len(chapters):
                owner.messagebox.showinfo("请选择章节", "请选择要删除的章节，并至少保留一章。", parent=dialog)
                return
            text = f"将永久删除 {len(selected)} 章，共 {sum(plan['chapters'][c] for c in selected)} 页。\n" + "、".join(f"第 {c} 章" for c in selected) + "\n\n删除页的书签会移除。先校验保留章节再替换漫画，文件名会更新，需要临时可用空间；不进入回收站。"
            if not owner.messagebox.askyesno("确认删除章节", text, parent=dialog):
                return
            dialog.destroy()
            def finished(result):
                new_key, message = result
                if hasattr(owner.app, "reader_state"):
                    from reader import ReaderState
                    owner.app.reader_state = ReaderState(owner.app.home)
                owner.cover_generation += 1
                owner.cover_pending.clear()
                owner.cover_images.clear()
                owner.render()
                owner.tree.selection_set(new_key)
                owner.status.set(message)
                owner.app.render()
                if "清理未完成" in message:
                    owner.messagebox.showwarning("旧文件清理未完成", message, parent=owner.window)
            owner.run(lambda: delete_chapters(owner.app.engine, key, selected, plan, owner.cancelled.is_set,
                      lambda text: owner.events.put(("progress", text))), finished, True)
        bar = ttk.Frame(dialog)
        bar.pack(pady=12)
        ttk.Button(bar, text="删除所选章节", command=confirm).pack(side="left", padx=8)
        ttk.Button(bar, text="取消", command=dialog.destroy).pack(side="left")
    owner.run(lambda: inspect(owner.library, key), choose, True)
