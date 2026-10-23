"""Concept C001: fixed contents rail and one continuous settings document."""
import tkinter as tk
from tkinter import ttk,messagebox
from ui_common import *
from core import Settings


def show(app):
    existing=getattr(app,'settings_window',None)
    if existing is not None and existing.winfo_exists():existing.lift();return
    window=tk.Toplevel(app.root);app.settings_window=window;window.title('设置');window.geometry(f'700x{min(840,window.winfo_screenheight()-100)}');window.minsize(620,560);window.transient(app.root)
    nav=tk.Frame(window,bg='#edf0f5',width=166);nav.pack(side='left',fill='y');nav.pack_propagate(False)
    tk.Label(nav,text='设置',bg='#edf0f5',fg=INK,font=('Microsoft YaHei UI',20,'bold'),anchor='w').pack(fill='x',padx=22,pady=(24,18))
    holder=ttk.Frame(window,style='Card.TFrame');holder.pack(fill='both',expand=True)
    canvas=tk.Canvas(holder,bg='white',highlightthickness=0,yscrollincrement=1);canvas.pack(fill='both',expand=True)
    body=ttk.Frame(canvas,padding=(26,14,26,24),style='Card.TFrame');item=canvas.create_window(0,0,anchor='nw',window=body)
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    anchors=[];links=[];fields={};initializing=[True]
    all_chapters=tk.BooleanVar(value=app.engine.settings.download_all_chapters);mode=tk.StringVar(value=app.engine.settings.reading_mode or 'scroll');chapter=tk.IntVar(value=app.engine.settings.chapter_view_mode);changed=[False]
    def save(close=False):
        if initializing[0]:return
        try:
            options=dict(app.engine.settings.__dict__);options.update({key:int(value.get()) for key,value in fields.items()});options.update(output=app.output_var.get(),download_all_chapters=all_chapters.get(),chapter_view_mode=chapter.get())
            if changed[0]:options['reading_mode']=mode.get()
            app.engine.settings=Settings(**options).validate();app.engine.save()
            if close:window.destroy()
        except (ValueError,OSError) as error:
            if close:messagebox.showerror('设置未保存',str(error),parent=window)
    def scroll(first,last):
        top=canvas.canvasy(0);index=0
        for i,anchor in enumerate(anchors):
            if anchor.winfo_y()<=top+28:index=i
        if body.winfo_height()>canvas.winfo_height()+8 and float(last)>=.999:index=len(anchors)-1
        for i,link in enumerate(links):link.configure(fg=BLUE if i==index else INK,bg='#d1d5df' if i==index else '#edf0f5')
    canvas.configure(yscrollcommand=scroll)
    def wheel(e):
        if e.widget.winfo_toplevel() is window:canvas.yview_scroll(-int(e.delta/120)*48,'units');return 'break'
    window.bind('<MouseWheel>',wheel)
    def section(title,inline=False):
        if anchors:tk.Frame(body,bg=LINE,height=1).pack(fill='x',pady=(14,8))
        row=ttk.Frame(body);row.pack(fill='x',pady=(6,8));anchor=ttk.Label(row,text=title,font=('Microsoft YaHei UI',18,'bold'));anchor.pack(side='left');anchors.append(row)
        label=tk.Label(nav,text=title,bg='#edf0f5',fg=INK,padx=16,pady=12,anchor='w',font=('Microsoft YaHei UI',12),cursor='hand2');label.pack(fill='x',padx=10,pady=2);label.bind('<Button-1>',lambda e:canvas.yview_moveto(row.winfo_y()/max(1,body.winfo_height())));links.append(label)
        return row
    def number(key,label):
        row=ttk.Frame(body);row.pack(fill='x',pady=5);ttk.Label(row,text=label,width=22).pack(side='left');value=tk.StringVar(value=str(getattr(app.engine.settings,key)));field=Input(row,textvariable=value,height=38,width=120);field.pack(side='right',fill='x',expand=True);field.editor.bind('<FocusOut>',lambda e:save());fields[key]=value
    section('下载');number('timeout','任务超时时间');number('concurrent_tasks','同时下载任务数');number('download_limit_kbps','下载限速')
    row=ttk.Frame(body);row.pack(fill='x',pady=8);ttk.Label(row,text='默认下载全部章节',width=22).pack(side='left');ttk.Checkbutton(row,variable=all_chapters,command=save).pack(side='left')
    row=ttk.Frame(body);row.pack(fill='x',pady=8);ttk.Label(row,text='保存目录',width=10).pack(side='left');path=Input(row,textvariable=app.output_var,height=38,width=120);path.editor.configure(state='readonly',readonlybackground=BG,fg=MUTED);path.pack(side='left',fill='x',expand=True,padx=(0,8));ttk.Button(row,text='选择目录',command=app.choose_dir).pack(side='right')
    from cleanup_ui import show_cleanup
    ttk.Button(body,text='清除缓存',command=lambda:show_cleanup(app)).pack(anchor='w',padx=(80,0),pady=4)
    section('阅读');ttk.Label(body,text='阅读模式').pack(anchor='w');row=ttk.Frame(body);row.pack(fill='x',pady=(8,12))
    def reading():changed[0]=True;save()
    for label,value in [('左右翻页','paged'),('上下翻页','vertical'),('上下滚动','scroll')]:ttk.Radiobutton(row,text=label,value=value,variable=mode,command=reading).pack(side='left',expand=True,anchor='w')
    ttk.Label(body,text='多章节观看模式').pack(anchor='w');row=ttk.Frame(body);row.pack(fill='x',pady=(10,4))
    for label,value in [('多章节合一',1),('分章节观看',2)]:ttk.Radiobutton(row,text=label,value=value,variable=chapter,command=save).pack(side='left',padx=(0,24))
    row=section('更新');ttk.Button(row,text='检查更新',command=app.updates.show_and_check).pack(side='left',padx=(52,8));ttk.Button(row,text='更新日志',command=app.updates.show_notes).pack(side='left')
    section('软件说明');ttk.Label(body,text='本软件主要为作者自用，维护与开发均由 AI 进行',wraplength=425).pack(anchor='w');ttk.Label(body,text='详情请见：').pack(anchor='w');repo=ttk.Label(body,text='github.com/norskhelo/jmbatch',foreground=BLUE,cursor='hand2');repo.pack(anchor='w');repo.bind('<Button-1>',lambda e:__import__('webbrowser').open('https://github.com/norskhelo/jmbatch'))
    initializing[0]=False;window.protocol('WM_DELETE_WINDOW',lambda:save(True));window.bind('<Escape>',lambda e:save(True));window.after_idle(lambda:scroll(*canvas.yview()))
