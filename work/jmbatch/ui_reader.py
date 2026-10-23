"""Reader controls; navigation and decoding stay in ReaderWindow."""
import tkinter as tk
from tkinter import ttk, messagebox
from ui_common import modal, actions, placeholder, BG, INK, notice


def controls(reader, top, bottom, title):
    ttk.Label(top, text=title, anchor='center', font=('Microsoft YaHei UI', 16, 'bold'), wraplength=700).pack(fill='x', pady=(0, 12))
    grid = ttk.Frame(top)
    grid.pack(fill='x')
    reader.chapter_box = ttk.Combobox(top, state='readonly')  # chapter model, hidden
    reader.jump = tk.StringVar(value='1')
    reader.favorite_button = ttk.Button(grid, command=reader.favorite)
    reader.mark_button = ttk.Button(grid, text='书签', command=lambda: bookmark(reader))
    buttons = [ttk.Button(grid, text='章节列表', command=lambda: chapters(reader)), reader.favorite_button,
               reader.mark_button, ttk.Button(grid, text='跳转', command=lambda: jump(reader))]
    for i, button in enumerate(buttons):
        grid.columnconfigure(i % 2, weight=1, uniform='reader')
        button.grid(row=i // 2, column=i % 2, sticky='ew', padx=5, pady=4)
    reader.page_buttons = ttk.Frame(bottom)
    actions(reader.page_buttons, '上一页', '下一页', lambda: reader.step(-1), lambda: reader.step(1))


def chapters(reader):
    dialog, body = modal(reader.window, 480)
    ttk.Label(body, text='章节列表', font=('Microsoft YaHei UI', 16, 'bold')).pack(pady=(0, 12))
    holder = ttk.Frame(body); holder.pack(fill='both', expand=True)
    box = tk.Listbox(holder, height=min(12, max(3, len(reader.starts))), relief='flat', bd=0, exportselection=False)
    scroll = ttk.Scrollbar(holder, command=box.yview); scroll.pack(side='right', fill='y')
    box.configure(yscrollcommand=scroll.set); box.pack(fill='both', expand=True)
    for text in reader.chapter_box['values']: box.insert('end', text)
    def choose():
        if box.curselection():
            index = reader.starts[box.curselection()[0]]
            dialog.destroy(); reader.window.after_idle(lambda: reader.go(index))
    actions(body, '确认', '取消', choose, dialog.destroy)


def bookmark(reader):
    if not reader.pages: return
    previous = getattr(reader, 'bookmark_panel', None)
    if previous and previous.winfo_exists(): previous.destroy()
    panel = tk.Toplevel(reader.window); reader.bookmark_panel = panel
    panel.overrideredirect(True); panel.transient(reader.window); panel.configure(bg='#dadce1')
    body = ttk.Frame(panel, padding=16); body.pack(fill='both', expand=True, padx=1, pady=1)
    name = ttk.Entry(body); name.pack(fill='x'); placeholder(name, '请输入名称')
    page = reader.current
    def add():
        value = name.get().strip()
        if not 1 <= len(value) <= 80:
            messagebox.showinfo('书签名称', '请输入 1–80 个字符的名称。', parent=panel); return
        reader.marks.add(page); reader.bookmark_names[str(page)] = value
        reader.save(); panel.destroy(); notice(reader.window, '书签已添加')
    actions(body, '添加', '取消', add, panel.destroy)
    panel.update_idletasks()
    button = reader.mark_button
    width = min(360, reader.window.winfo_width() - 32)
    x = min(button.winfo_rootx(), reader.window.winfo_rootx() + reader.window.winfo_width() - width - 16)
    panel.geometry(f'{width}x{body.winfo_reqheight()+2}+{x}+{button.winfo_rooty()+button.winfo_height()+6}')
    panel.grab_set(); name.focus_set(); panel.bind('<Escape>', lambda e: panel.destroy())


def jump(reader):
    if not reader.pages: return
    dialog, body = modal(reader.window, 440, blur=True)
    value = tk.StringVar()
    entry = ttk.Entry(body, textvariable=value); entry.pack(fill='x'); placeholder(entry, '请输入页码')
    holder = ttk.Frame(body); holder.pack(fill='both', expand=True, pady=(16, 0))
    box = tk.Listbox(holder, height=7, relief='flat', borderwidth=0, bg='white', fg=INK, selectbackground=BG, selectforeground=INK, exportselection=False)
    scroll = ttk.Scrollbar(holder, command=box.yview); scroll.pack(side='right', fill='y')
    box.configure(yscrollcommand=scroll.set); box.pack(fill='both', expand=True)
    marks = sorted(reader.marks)
    for page in marks: box.insert('end', reader.bookmark_names.get(str(page), f'第 {page+1} 页'))
    if not marks: box.insert('end', '暂无书签')
    def selected(event=None):
        if marks and box.curselection(): value.set(str(marks[box.curselection()[0]] + 1))
    box.bind('<<ListboxSelect>>', selected)
    def go():
        try:
            page = int(value.get())
            if not 1 <= page <= len(reader.pages): raise ValueError()
        except ValueError:
            messagebox.showinfo('页码无效', f'请输入 1 至 {len(reader.pages)} 的页码。', parent=dialog); return
        dialog.destroy(); reader.window.after_idle(lambda: reader.go(page-1))
    # Retain removal of existing bookmarks without adding a permanent toolbar.
    def remove(event=None):
        if marks and box.curselection():
            index = box.curselection()[0]; page = marks.pop(index)
            reader.marks.discard(page); reader.bookmark_names.pop(str(page), None); reader.save(); box.delete(index)
    box.bind('<Delete>', remove)
    menu = tk.Menu(dialog, tearoff=False); menu.add_command(label='删除书签', command=remove)
    box.bind('<Button-3>', lambda e: (box.selection_clear(0, 'end'), box.selection_set(box.nearest(e.y)), menu.tk_popup(e.x_root, e.y_root)))
    actions(body, '跳转', '取消', go, dialog.destroy)
    box.bind('<Double-Button-1>', lambda e: (selected(), go()))
    entry.bind('<Return>', lambda e: go())
