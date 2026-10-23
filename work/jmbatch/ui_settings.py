import tkinter as tk
from tkinter import ttk,messagebox
from ui_common import *
from core import Settings


def show(app):
    existing=getattr(app,'settings_window',None)
    if existing is not None and existing.winfo_exists():existing.lift();return
    window=tk.Toplevel(app.root);app.settings_window=window;window.title('设置');window.geometry('820x720');window.minsize(650,540);window.transient(app.root)
    nav=ttk.Frame(window,padding=16);nav.pack(side='left',fill='y');ttk.Label(nav,text='设置',font=('Microsoft YaHei UI',21,'bold')).pack(anchor='w',pady=(4,18))
    holder=ttk.Frame(window,style='Card.TFrame');holder.pack(fill='both',expand=True)
    canvas=tk.Canvas(holder,bg='white',highlightthickness=0,yscrollincrement=1);bar=ttk.Scrollbar(holder,command=canvas.yview);bar.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
    body=ttk.Frame(canvas,padding=24,style='Card.TFrame');item=canvas.create_window(0,0,anchor='nw',window=body);canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    anchors=[];links=[];fields={}
    def scroll(first,last):
        bar.set(first,last);top=canvas.canvasy(0);index=0
        for i,anchor in enumerate(anchors):
            if anchor.winfo_y()<=top+30:index=i
        if body.winfo_height()>canvas.winfo_height()+8 and float(last)>=.999:index=len(anchors)-1
        for i,link in enumerate(links):link.configure(foreground=BLUE if i==index else INK)
    canvas.configure(yscrollcommand=scroll)
    def wheel(e):
        if e.widget.winfo_toplevel() is window:canvas.yview_scroll(-int(e.delta/120)*48,'units');return 'break'
    window.bind('<MouseWheel>',wheel)
    def section(title):
        index=len(anchors);anchor=ttk.Label(body,text=title,font=('Microsoft YaHei UI',19,'bold'));anchor.pack(anchor='w',pady=(14,18));anchors.append(anchor)
        label=ttk.Label(nav,text=title,padding=(8,12),cursor='hand2');label.pack(fill='x');label.bind('<Button-1>',lambda e:canvas.yview_moveto(anchor.winfo_y()/max(1,body.winfo_height())));links.append(label)
    def number(key,label):
        row=ttk.Frame(body);row.pack(fill='x',pady=5);ttk.Label(row,text=label,width=24).pack(side='left');value=tk.StringVar(value=str(getattr(app.engine.settings,key)));ttk.Entry(row,textvariable=value,width=12).pack(side='right',fill='x',expand=True);fields[key]=value
    section('下载');number('timeout','任务超时时间（秒，5–120）');number('concurrent_tasks','同时下载任务数（1–4）');number('download_limit_kbps','下载限速（KB/s，0 不限速）')
    all_chapters=tk.BooleanVar(value=app.engine.settings.download_all_chapters);ttk.Checkbutton(body,text='默认下载全部章节',variable=all_chapters).pack(anchor='w',pady=10)
    row=ttk.Frame(body);row.pack(fill='x',pady=8);ttk.Label(row,text='保存目录').pack(side='left');ttk.Label(row,textvariable=app.output_var,foreground=BLUE,wraplength=280).pack(side='left',padx=10);ttk.Button(row,text='选择目录',command=app.choose_dir).pack(side='right')
    from cleanup_ui import show_cleanup
    ttk.Button(body,text='清除缓存',command=lambda:show_cleanup(app)).pack(anchor='w',pady=8)
    section('阅读');ttk.Label(body,text='阅读模式').pack(anchor='w');mode=tk.StringVar(value=app.engine.settings.reading_mode or 'scroll');changed=[False]
    row=ttk.Frame(body);row.pack(fill='x',pady=10)
    for label,value in [('左右翻页','paged'),('上下翻页','vertical'),('上下滚动','scroll')]:ttk.Radiobutton(row,text=label,value=value,variable=mode,command=lambda:changed.__setitem__(0,True)).pack(side='left',padx=4)
    ttk.Label(body,text='多章节观看模式').pack(anchor='w');chapter=tk.IntVar(value=app.engine.settings.chapter_view_mode);row=ttk.Frame(body);row.pack(fill='x',pady=10)
    for label,value in [('多章节合一',1),('分章节观看',2)]:ttk.Radiobutton(row,text=label,value=value,variable=chapter).pack(side='left',padx=8)
    section('更新');row=ttk.Frame(body);row.pack(fill='x');ttk.Button(row,text='检查更新',command=app.updates.show_and_check).pack(side='left');ttk.Button(row,text='更新日志',command=app.updates.show_notes).pack(side='left',padx=10)
    section('软件说明');ttk.Label(body,text='本软件主要为作者自用，维护与开发均由 AI 进行',wraplength=490).pack(anchor='w');ttk.Label(body,text='详情请见').pack(anchor='w',pady=(10,0));repo=ttk.Label(body,text='github.com/norskhelo/jmbatch',foreground=BLUE,cursor='hand2');repo.pack(anchor='w');repo.bind('<Button-1>',lambda e:__import__('webbrowser').open('https://github.com/norskhelo/jmbatch'))
    def save():
        try:
            options=dict(app.engine.settings.__dict__);options.update({key:int(value.get()) for key,value in fields.items()});options.update(output=app.output_var.get(),download_all_chapters=all_chapters.get(),chapter_view_mode=chapter.get())
            if changed[0]:options['reading_mode']=mode.get()
            app.engine.settings=Settings(**options).validate();app.engine.save();window.destroy();notice(app.root,'设置已保存')
        except (ValueError,OSError) as e:messagebox.showerror('设置未保存',str(e),parent=window)
    ttk.Button(body,text='保存并返回',style='Accent.TButton',command=save).pack(fill='x',pady=(24,8))
    ttk.Button(body,text='高级下载设置',command=app.advanced_settings_dialog).pack(anchor='w')
    window.after_idle(lambda:scroll(*canvas.yview()))
