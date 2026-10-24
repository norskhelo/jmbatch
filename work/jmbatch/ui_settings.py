"""Concept C001: fixed contents rail and one continuous settings document."""
import tkinter as tk
import time
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk,messagebox
from ui_common import *
from core import Settings


def slide(app, entering, finished):
    """Move the two live pages together, with the same path in reverse on return."""
    if getattr(app,'settings_transition',None) is not None:return
    page=app.settings_page
    state=app.settings_transition=object()
    tag=getattr(app,'settings_input_tag',None)
    if tag is None:
        tag=app.settings_input_tag=f'SettingsSlide:{app.root}'
        def block(event):
            if getattr(app,'settings_transition',None) is not None:return 'break'
        for event in ('<ButtonPress>','<Double-ButtonPress-1>','<ButtonRelease>','<Motion>','<MouseWheel>','<KeyPress>','<KeyRelease>'):
            app.root.bind_class(tag,event,block)
    def bind(widget):
        if tag not in widget.bindtags():widget.bindtags((tag,)+widget.bindtags())
        for child in widget.winfo_children():bind(child)
    bind(app.main_page);bind(page)
    app.root.focus_set()
    app.main_page.pack_forget()
    app.main_page.place(relx=0 if entering else -1,y=0,relwidth=1,relheight=1)
    page.place(relx=1 if entering else 0,y=0,relwidth=1,relheight=1);page.lift()
    app.root.update_idletasks()
    # Tk child HWNDs otherwise reuse stale pixels while their parents slide.
    import ctypes
    from ctypes import wintypes
    redraw=ctypes.windll.user32.RedrawWindow
    redraw.argtypes=[wintypes.HWND,ctypes.c_void_p,ctypes.c_void_p,wintypes.UINT]
    started=time.monotonic()
    def frame():
        if getattr(app,'settings_transition',None) is not state:return
        t=min(1,(time.monotonic()-started)/.3);eased=t*t*(3-2*t)
        progress=eased if entering else 1-eased
        app.main_page.place_configure(relx=-progress);page.place_configure(relx=1-progress)
        app.root.update_idletasks()
        redraw(app.root.winfo_id(),None,None,0x185)  # invalidate, erase, all children, update now
        app.root.update_idletasks()
        if t<1:app.settings_animation=app.root.after(16,frame)
        else:
            app.settings_transition=None;app.settings_animation=None
            app.main_page.place_forget()
            if entering:page.place_configure(relx=0)
            else:app.main_page.pack(fill='both',expand=True)
            finished()
    frame()


def show(app):
    if getattr(app,'settings_page',None) is not None or getattr(app,'page_exchange',None) is not None or getattr(app,'settings_transition',None) is not None:return
    page=app.settings_page=tk.Frame(app.root,bg='white')
    nav=tk.Frame(page,bg='#edf0f5',width=166);nav.pack(side='left',fill='y');nav.pack_propagate(False)
    back=square_button(ttk.Button(nav,text='←',command=lambda:save(True)));back.pack(anchor='w',padx=16,pady=(16,0))
    tk.Label(nav,text='设置',bg='#edf0f5',fg=INK,font=('Microsoft YaHei UI',20,'bold'),anchor='w').pack(fill='x',padx=16,pady=(16,18))
    page.bind('<Configure>',lambda e:nav.configure(width=max(100,min(166,e.width//4))) if e.widget is page else None)
    holder=ttk.Frame(page,style='Card.TFrame');holder.pack(fill='both',expand=True)
    canvas=tk.Canvas(holder,bg='white',highlightthickness=0,yscrollincrement=1);canvas.pack(fill='both',expand=True)
    body=ttk.Frame(canvas,padding=(16,14,16,24),style='Card.TFrame');item=canvas.create_window(0,0,anchor='nw',window=body)
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    anchors=[];links=[];fields={};initializing=[True]
    all_chapters=tk.BooleanVar(value=app.engine.settings.download_all_chapters);mode=tk.StringVar(value=app.engine.settings.reading_mode or 'scroll');chapter=tk.IntVar(value=app.engine.settings.chapter_view_mode);changed=[False]
    def save(close=False):
        if initializing[0] or getattr(app,'settings_transition',None) is not None:return
        try:
            options=dict(app.engine.settings.__dict__);options.update({key:int(value.get()) for key,value in fields.items()});options.update(output=app.output_var.get(),download_all_chapters=all_chapters.get(),chapter_view_mode=chapter.get())
            if changed[0]:options['reading_mode']=mode.get()
            app.engine.settings=Settings(**options).validate();app.engine.save()
            if close:
                def returned():
                    app.root.unbind('<MouseWheel>',wheel_binding)
                    app.settings_page=None;app.close_settings=None
                    page.destroy();app.settings_button.focus_set()
                    from ui_main import paint_live_seam
                    app.root.after_idle(lambda:paint_live_seam(app))
                slide(app,False,returned)
        except (ValueError,OSError) as error:
            if close:messagebox.showerror('设置未保存',str(error),parent=app.root)
    def scroll(first,last):
        top=canvas.canvasy(0);index=0
        for i,anchor in enumerate(anchors):
            if anchor.winfo_y()<=top+28:index=i
        if body.winfo_height()>canvas.winfo_height()+8 and float(last)>=.999:index=len(anchors)-1
        for i,link in enumerate(links):link.configure(fg=BLUE if i==index else INK,bg='#d1d5df' if i==index else '#edf0f5')
    canvas.configure(yscrollcommand=scroll)
    def wheel(e):
        widget=e.widget
        while widget is not None:
            if widget is page:canvas.yview_scroll(-int(e.delta/120)*48,'units');return 'break'
            widget=widget.master
    wheel_binding=app.root.bind('<MouseWheel>',wheel,add='+')
    def section(title,inline=False):
        if anchors:tk.Frame(body,bg=LINE,height=1).pack(fill='x',pady=(14,8))
        row=ttk.Frame(body);row.pack(fill='x',pady=(6,8));anchor=ttk.Label(row,text=title,font=('Microsoft YaHei UI',18,'bold'));anchor.pack(side='left');anchors.append(row)
        label=tk.Label(nav,text=title,bg='#edf0f5',fg=INK,padx=16,pady=12,anchor='w',font=('Microsoft YaHei UI',12),cursor='hand2');label.pack(fill='x',padx=10,pady=2);label.bind('<Button-1>',lambda e:canvas.yview_moveto(row.winfo_y()/max(1,body.winfo_height())));links.append(label)
        return row
    def number(key,label):
        row=ttk.Frame(body);row.pack(fill='x',pady=5);ttk.Label(row,text=label,width=16).pack(side='left');value=tk.StringVar(value=str(getattr(app.engine.settings,key)));field=Input(row,textvariable=value,width=110);field.pack(side='right',fill='x',expand=True,padx=(12,0));field.editor.bind('<FocusOut>',lambda e:save());fields[key]=value
    section('下载');number('timeout','任务超时时间');number('concurrent_tasks','同时下载任务数');number('download_limit_kbps','下载限速')
    row=ttk.Frame(body);row.pack(fill='x',pady=8);ttk.Label(row,text='默认下载全部章节').pack(side='left');ttk.Checkbutton(row,variable=all_chapters,command=save).pack(side='left',padx=12)
    row=ttk.Frame(body);row.pack(fill='x',pady=8);ttk.Label(row,text='保存目录').pack(side='left');path=Input(row,multiline=True,width=80);path.editor.configure(state='disabled',wrap='char',fg=MUTED);path.pack(side='left',fill='x',expand=True,padx=8);ttk.Button(row,text='选择目录',command=lambda:(app.choose_dir(),save())).pack(side='right')
    def refresh_path(*_):
        value=app.output_var.get().strip()
        display=str(Path(value).expanduser().absolute()) if value else ''
        path.editor.configure(state='normal');path.editor.delete('1.0','end');path.editor.insert('1.0',display);path.editor.configure(state='disabled');path.schedule_fit()
    path_trace=app.output_var.trace_add('write',refresh_path)
    page.bind('<Destroy>',lambda e:app.output_var.trace_remove('write',path_trace) if e.widget is page else None,add='+')
    refresh_path()
    from cleanup_ui import show_cleanup
    ttk.Button(body,text='清除缓存',command=lambda:show_cleanup(app)).pack(anchor='w',padx=(80,0),pady=4)
    section('阅读');ttk.Label(body,text='阅读模式').pack(anchor='w');row=ttk.Frame(body);row.pack(fill='x',pady=(8,12))
    def reading():changed[0]=True;save()
    for label,value in [('左右翻页','paged'),('上下翻页','vertical'),('上下滚动','scroll')]:ttk.Radiobutton(row,text=label,value=value,variable=mode,command=reading).pack(side='left',expand=True,anchor='w')
    ttk.Label(body,text='多章节观看模式').pack(anchor='w');row=ttk.Frame(body);row.pack(fill='x',pady=(10,4))
    for label,value in [('多章节合一',1),('分章节观看',2)]:ttk.Radiobutton(row,text=label,value=value,variable=chapter,command=save).pack(side='left',padx=(0,24))
    row=section('更新');update_button=ttk.Button(row,text='检查更新');update_button.pack(side='left',padx=(16,8));app.updates.bind_settings_button(update_button);ttk.Button(row,text='更新日志',command=app.updates.show_notes).pack(side='left')
    section('软件说明');description=ttk.Label(body,text='本软件主要为作者自用，维护与开发均由 AI 进行',wraplength=425);description.pack(anchor='w');body.bind('<Configure>',lambda e:description.configure(wraplength=max(120,e.width-32)),add='+');ttk.Label(body,text='详情请见：').pack(anchor='w');repo=ttk.Label(body,text='github.com/norskhelo/jmbatch',foreground=BLUE,cursor='hand2');repo.pack(anchor='w');repo.bind('<Button-1>',lambda e:__import__('webbrowser').open('https://github.com/norskhelo/jmbatch'))
    initializing[0]=False;app.close_settings=lambda:save(True)
    slide(app,True,back.focus_set);page.after_idle(lambda:scroll(*canvas.yview()))
