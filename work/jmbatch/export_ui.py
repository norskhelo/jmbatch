"""Explicit export choices, run through the library's cancellable worker."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from batch_export import export_many


def show_export(library_window, keys):
    owner = library_window
    keys = list(dict.fromkeys([keys] if isinstance(keys, str) else keys))
    if not keys:
        return
    items = [owner.library.entries[key] for key in keys]
    all_pdf = all(item['format'] == 'pdf' for item in items)
    from ui_common import modal, actions
    dialog, panel = modal(owner.window)
    ttk.Label(panel, text="导出为", anchor="center", font=("Microsoft YaHei UI", 16, "bold")).pack(fill="x", pady=(0, 20))
    fmt, destination = tk.StringVar(value="zip" if all_pdf else "pdf"), tk.StringVar(value=items[0]['root'])
    numeric, split = tk.BooleanVar(), tk.BooleanVar()
    formats = ttk.Frame(panel); formats.pack(fill="x")
    for label, value in (("pdf", "pdf"), ("zip", "zip")):
        ttk.Radiobutton(formats, text=label, value=value, variable=fmt).pack(side="left", expand=True)
    def start():
        folder = Path(destination.get())
        if not folder.is_absolute():
            messagebox.showerror("导出目录无效", "请选择有效的导出文件夹。", parent=dialog)
            return
        options = fmt.get(), numeric.get() and fmt.get() != "images", split.get() and fmt.get() == 'pdf'
        dialog.destroy()
        def operation():
            return export_many(owner.library, keys, folder, *options,
                               progress=lambda message: owner.events.put(("progress", message)), cancelled=owner.cancelled.is_set)
        def finished(result):
            summary = result.summary() + f"\n保存位置：{folder}\n源文件已保留。"
            owner.status.set(result.summary() + f" 保存位置：{folder}")
            if result.errors or result.warnings:
                details = '\n'.join(result.errors[:20] + result.warnings)
                if len(result.errors) > 20:
                    details += f"\n……另 {len(result.errors)-20} 本失败"
                messagebox.showwarning("导出结果", summary+'\n\n'+details, parent=owner.window)
            elif len(keys) > 1 or result.stopped:
                messagebox.showinfo("导出结果", summary, parent=owner.window)
        owner.run(operation, finished, pause_required=True)
    actions(panel, "确认", "取消", start, dialog.destroy)
    return dialog
