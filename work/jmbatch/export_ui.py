"""Explicit export choices, run through the library's cancellable worker."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from albums import export_album, read_album


def show_export(library_window, key):
    owner = library_window
    source = owner.library.checked_path(key)
    if owner.library.entries[key]["format"] != "images":
        raise ValueError("请选择已下载的图片目录；旧版 PDF / ZIP 可直接打开或分享")
    _, images = read_album(source)
    chapters = len({e["chapter"] for e in images})
    dialog = tk.Toplevel(owner.window)
    dialog.title("导出图片漫画")
    dialog.transient(owner.window)
    dialog.grab_set()
    panel = ttk.Frame(dialog, padding=20)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text=f"{len(images)} 张图片 · {chapters} 个章节\n导出保留原始图片，可重复选择其他格式。").pack(anchor="w")
    fmt, destination = tk.StringVar(value="pdf"), tk.StringVar(value=str(source.parent))
    numeric, flat, split = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
    for label, value in (("PDF", "pdf"), ("ZIP 图片包", "zip")):
        ttk.Radiobutton(panel, text=label, value=value, variable=fmt).pack(anchor="w")
    numeric_button = ttk.Checkbutton(panel, text="文件名仅编号（分章节时附章节序号）", variable=numeric)
    numeric_button.pack(anchor="w", pady=4)
    ttk.Label(panel, text="ZIP：单章节图片平铺，多章节分目录；仅包含图片。").pack(anchor="w", pady=4)
    split_button = ttk.Checkbutton(panel, text="PDF 分章节导出（不勾选则统一导出为一本）", variable=split)
    split_button.pack(anchor="w", pady=4)
    def mode(*_):
        split_button.configure(state="normal" if fmt.get() == "pdf" and chapters > 1 else "disabled")
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
            messagebox.showerror("导出目录无效", "请选择完整的绝对路径", parent=dialog)
            return
        options = fmt.get(), numeric.get(), flat.get(), split.get() and chapters > 1
        dialog.destroy()
        def operation():
            return export_album(source, folder, options[0], options[1], options[2], options[3],
                                lambda e: owner.events.put(("progress", e.get("message", "正在导出"))), owner.cancelled.is_set)
        def finished(paths):
            found, _ = owner.library.discover(folder)
            identities = {str(p) for p in paths}
            owner.library.import_found([e for e in found if e["path"] in identities])
            owner.status.set(f"导出完成：{len(paths)} 个文件，原始图片保留。保存到 {folder}")
        owner.run(operation, finished, pause_required=True)
    ttk.Button(panel, text="开始导出", command=start).pack(anchor="e", pady=(12, 0))
    return dialog
