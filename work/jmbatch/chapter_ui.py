"""One nonblocking chapter picker at a time; closing postpones this task."""
import tkinter as tk
from tkinter import ttk, messagebox

class ChapterPicker:
    def __init__(self, app, task):
        self.app, self.task = app, task
        self.window = win = tk.Toplevel(app.root)
        win.title("选择下载章节")
        win.geometry("620x480")
        win.minsize(520, 340)
        win.transient(app.root)
        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"JM{task.album_id} · {task.title}", wraplength=550).pack(anchor="w")
        ttk.Label(body, text="请选择要下载的章节。稍后选择或关闭此窗口会暂停任务。").pack(anchor="w", pady=8)
        area = ttk.Frame(body)
        area.pack(fill="both", expand=True)
        self.list = tk.Listbox(area, selectmode="multiple", exportselection=False)
        scroll = ttk.Scrollbar(area, command=self.list.yview)
        self.list.configure(yscrollcommand=scroll.set)
        self.list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for chapter in task.chapter_options:
            self.list.insert("end", f"第 {chapter['number']} 章 · {chapter['title']}")
        self.list.selection_set(0, "end")
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="全选", command=lambda: self.list.selection_set(0, "end")).pack(side="left")
        ttk.Button(buttons, text="取消全选", command=lambda: self.list.selection_clear(0, "end")).pack(side="left", padx=6)
        ttk.Button(buttons, text="下载所选章节", command=self.confirm).pack(side="right")
        ttk.Button(buttons, text="稍后选择", command=self.postpone).pack(side="right", padx=6)
        win.protocol("WM_DELETE_WINDOW", self.postpone)

    def confirm(self):
        try:
            self.app.engine.choose_chapters(self.task.key, [self.task.chapter_options[i]["id"] for i in self.list.curselection()])
        except (ValueError, OSError) as error:
            messagebox.showerror("无法开始下载", str(error), parent=self.window)
            return
        self.window.destroy()

    def postpone(self):
        self.app.engine.postpone_chapters(self.task.key)
        self.window.destroy()

def poll_chapters(app):
    picker = getattr(app, "chapter_picker", None)
    if picker and picker.window.winfo_exists():
        if picker.task.status != "selecting":
            picker.window.destroy()
        else:
            return
    if app.root.grab_current():
        return
    task = next((t for t in app.engine.tasks if t.status == "selecting"), None)
    if task:
        app.chapter_picker = ChapterPicker(app, task)
