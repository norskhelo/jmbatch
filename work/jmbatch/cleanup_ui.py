"""Background cache maintenance with a modal progress/result window."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from cache_cleanup import clean_tasks


def show_cleanup(app):
    engine = app.engine
    if engine.running or engine.active or engine.cleaning:
        messagebox.showinfo('清理下载缓存', '请先暂停全部下载，等待请求结束；清理过程中不能开始下载。', parent=app.root)
        return
    engine.cleaning = True
    tasks = list(engine.tasks)
    window = tk.Toplevel(app.root)
    window.title('清理下载缓存')
    window.transient(app.root)
    window.grab_set()
    window.protocol('WM_DELETE_WINDOW', lambda: None)
    label = ttk.Label(window, text='正在清理…', padding=20, wraplength=500)
    label.pack(fill='x')
    ttk.Label(window, text='保留成品、完成标记、未完成任务的完整图片和章节缓存。\n仅清理已完成任务的可删除缓存及任务内临时文件。', padding=20).pack()
    events = queue.Queue()

    def work():
        try:
            result = clean_tasks(tasks, lambda r: events.put(('progress', r.message())))
            events.put(('done', result.message()))
        except Exception as error:
            events.put(('done', '部分清理未完成：' + str(error)))

    def poll():
        while not events.empty():
            kind, text = events.get_nowait()
            label.configure(text=text)
            if kind == 'done':
                engine.cleaning = False
                app.log(text)
                window.protocol('WM_DELETE_WINDOW', window.destroy)
                ttk.Button(window, text='关闭', command=window.destroy).pack(pady=12)
                return
        app.root.after(100, poll)

    threading.Thread(target=work, daemon=True).start()
    app.root.after(100, poll)
