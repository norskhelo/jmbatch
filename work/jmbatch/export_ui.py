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
    dialog = tk.Toplevel(owner.window)
    dialog.title(f"导出漫画 · {len(keys)} 本")
    dialog.transient(owner.window)
    dialog.grab_set()
    panel = ttk.Frame(dialog, padding=20)
    panel.pack(fill="both", expand=True)
    titles = '\n'.join((f"JM{item['id']} · " if item['id'] else '') + (item['title'][:100] + ('…' if len(item['title']) > 100 else '')) for item in items[:3])
    if len(items) > 3:
        titles += f"\n……另 {len(items)-3} 本"
    ttk.Label(panel, text=f"已选择 {len(keys)} 本漫画\n"+titles, wraplength=600).pack(anchor="w", pady=(0, 8))
    ttk.Label(panel, text="支持 PDF、ZIP 和图片文件夹之间的格式转换，保留源文件。\nPDF 转图片可能损失画质，所有页面归为一个章节。").pack(anchor="w")
    ttk.Label(panel, text="使用同一格式和目录，逐本独立导出；单本失败继续其余漫画。\n同名文件不覆盖。停止后保留已完成的导出结果。", wraplength=600).pack(anchor="w", pady=6)
    fmt, destination = tk.StringVar(value="images" if all_pdf else "pdf"), tk.StringVar(value=items[0]['root'])
    numeric, split = tk.BooleanVar(), tk.BooleanVar()
    for label, value in (("PDF", "pdf"), ("ZIP 压缩包", "zip"), ("图片文件夹", "images")):
        ttk.Radiobutton(panel, text=label, value=value, variable=fmt).pack(anchor="w")
    numeric_button = ttk.Checkbutton(panel, text="仅使用编号命名（分章节导出时附加章节序号）", variable=numeric)
    numeric_button.pack(anchor="w", pady=4)
    ttk.Label(panel, text="ZIP 和图片文件夹仅保存图片；多章节按章节分文件夹保存。").pack(anchor="w", pady=4)
    split_button = ttk.Checkbutton(panel, text="按章节分别导出 PDF（未勾选时合并为一本）", variable=split)
    split_button.pack(anchor="w", pady=4)
    def mode(*_):
        split_button.configure(state="normal" if fmt.get() == "pdf" and not all_pdf else "disabled")
        numeric_button.configure(state="disabled" if fmt.get() == "images" else "normal")
    fmt.trace_add("write", mode)
    mode()
    ttk.Entry(panel, textvariable=destination, width=60).pack(fill="x", pady=8)
    def choose():
        folder = filedialog.askdirectory(parent=dialog, initialdir=destination.get(), title="选择导出目录")
        if folder:
            destination.set(folder)
    ttk.Button(panel, text="选择导出目录", command=choose).pack(anchor="w")
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
    ttk.Button(panel, text="开始导出", command=start).pack(anchor="e", pady=(12, 0))
    return dialog
