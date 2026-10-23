"""Reader controls; navigation and decoding stay in ReaderWindow."""
import tkinter as tk
from tkinter import ttk, messagebox
from ui_common import modal, actions, placeholder, BG, INK, notice, Input, rounded, LINE


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
    row=ttk.Frame(reader.page_buttons);row.pack(fill='x',pady=(8,0));row.columnconfigure((0,1),weight=1,uniform='pages')
    ttk.Button(row,text='上一页',command=lambda:reader.step(-1)).grid(row=0,column=0,sticky='ew',padx=(0,5))
    ttk.Button(row,text='下一页',command=lambda:reader.step(1)).grid(row=0,column=1,sticky='ew',padx=(5,0))


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
    panel.overrideredirect(True); panel.transient(reader.window); panel.configure(bg='#ff00ff');panel.attributes('-transparentcolor','#ff00ff')
    surface=tk.Canvas(panel,bg='#ff00ff',highlightthickness=0);surface.pack(fill='both',expand=True)
    body = ttk.Frame(surface, padding=16);item=surface.create_window(1,13,anchor='nw',window=body)
    def shape(event):
        surface.delete('outline');rounded(surface,0,12,event.width-1,event.height-13,10,fill='white',outline=LINE,tags='outline');surface.create_polygon(24,13,34,1,44,13,fill='white',outline=LINE,tags='outline');surface.create_line(25,13,43,13,fill='white',width=2,tags='outline');surface.tag_lower('outline');surface.itemconfigure(item,width=event.width-2,height=event.height-15)
    surface.bind('<Configure>',shape)
    name = Input(body); name.pack(fill='x'); placeholder(name, '请输入名称')
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
    panel.geometry(f'{width}x{body.winfo_reqheight()+16}+{x}+{button.winfo_rooty()+button.winfo_height()-2}')
    panel.deiconify();panel.lift();panel.grab_set();name.focus_set();panel.bind('<Escape>', lambda e: panel.destroy())


def jump(reader):
    if not reader.pages: return
    dialog, body = modal(reader.window, 440, blur=True)
    value = tk.StringVar()
    entry = Input(body, textvariable=value); entry.pack(fill='x'); placeholder(entry, '请输入页码')
    holder = ttk.Frame(body); holder.pack(fill='both', expand=True, pady=(16, 0))
    canvas=tk.Canvas(holder,height=210,highlightthickness=0,bg='white',yscrollincrement=1)
    scroll=ttk.Scrollbar(holder,command=canvas.yview);scroll.pack(side='right',fill='y');canvas.configure(yscrollcommand=scroll.set);canvas.pack(fill='both',expand=True)
    marks=sorted(reader.marks)
    def go():
        try:
            page=int(value.get())
            if not 1<=page<=len(reader.pages):raise ValueError()
        except ValueError:
            messagebox.showinfo('页码无效',f'请输入 1 至 {len(reader.pages)} 的页码。',parent=dialog);return
        dialog.destroy();reader.window.after_idle(lambda:reader.go(page-1))
    def paint(event=None):
        canvas.delete('all');width=canvas.winfo_width()
        for index,page in enumerate(marks):
            y=index*49;rounded(canvas,0,y,width-4,42,6,fill=BG,outline='',tags=f'mark-{index}')
            canvas.create_text(12,y+21,text=reader.bookmark_names.get(str(page),f'第 {page+1} 页'),anchor='w',fill=INK,font=('Microsoft YaHei UI',11),tags=f'mark-{index}')
            canvas.tag_bind(f'mark-{index}','<Button-1>',lambda e,p=page:(value.set(str(p+1)),go()))
            canvas.tag_bind(f'mark-{index}','<Button-3>',lambda e,p=page:menu(e,p))
        canvas.configure(scrollregion=(0,0,width,len(marks)*49))
    def remove(page):
        marks.remove(page);reader.marks.discard(page);reader.bookmark_names.pop(str(page),None);reader.save();paint()
    def menu(event,page):
        popup=tk.Menu(dialog,tearoff=False);popup.add_command(label='删除书签',command=lambda:remove(page));popup.tk_popup(event.x_root,event.y_root)
    canvas.bind('<Configure>',paint);canvas.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-int(e.delta/120)*40,'units'))
    actions(body,'跳转','取消',go,dialog.destroy)
    entry.editor.bind('<Return>', lambda e: go())
