"""Explicit export choices, run through the library's cancellable worker."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from albums import export_album


def show_export(library_window, key):
    owner = library_window
    source = owner.library.checked_path(key)
    source_format = owner.library.entries[key]["format"]
    dialog = tk.Toplevel(owner.window)
    dialog.title("导出漫画")
    dialog.transient(owner.window)
    dialog.grab_set()
    panel = ttk.Frame(dialog, padding=20)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="支持 PDF、ZIP 和图片文件夹之间的格式转换，保留源文件。\nPDF 转图片可能损失画质，所有页面归为一个章节。").pack(anchor="w")
    fmt, destination = tk.StringVar(value="images" if source_format == "pdf" else "pdf"), tk.StringVar(value=str(source.parent))
    numeric, flat, split = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
    for label, value in (("PDF", "pdf"), ("ZIP 压缩包", "zip"), ("图片文件夹", "images")):
        ttk.Radiobutton(panel, text=label, value=value, variable=fmt).pack(anchor="w")
    numeric_button = ttk.Checkbutton(panel, text="仅使用编号命名（分章节导出时附加章节序号）", variable=numeric)
    numeric_button.pack(anchor="w", pady=4)
    ttk.Label(panel, text="ZIP 和图片文件夹仅保存图片；多章节按章节分文件夹保存。").pack(anchor="w", pady=4)
    split_button = ttk.Checkbutton(panel, text="按章节分别导出 PDF（未勾选时合并为一本）", variable=split)
    split_button.pack(anchor="w", pady=4)
    def mode(*_):
        split_button.configure(state="normal" if fmt.get() == "pdf" and source_format != "pdf" else "disabled")
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
        options = fmt.get(), numeric.get() and fmt.get() != "images", flat.get(), split.get() and source_format != "pdf"
        dialog.destroy()
        def operation():
            return export_album(source, folder, options[0], options[1], options[2], options[3],
                                lambda e: owner.events.put(("progress", e.get("message", "正在导出"))), owner.cancelled.is_set)
        def finished(paths):
            found, _ = owner.library.discover(folder)
            identities = {str(p) for p in paths}
            owner.library.import_found([e for e in found if e["path"] in identities])
            owner.status.set(f"导出完成，已保存 {len(paths)} 项。源文件已保留。保存位置：{folder}")
        owner.run(operation, finished, pause_required=True)
    ttk.Button(panel, text="开始导出", command=start).pack(anchor="e", pady=(12, 0))
    return dialog
