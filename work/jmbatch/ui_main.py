"""Main page composition; queue operations remain owned by App and Engine."""
import tkinter as tk
from tkinter import ttk,messagebox
from display_view import DisplayView
from ui_common import *
from core import VERSION
from download_display import percent,format_speed,size_text


class DownloadList(DisplayView):
    def __init__(self,parent,app,**kwargs):
        self.app=app
        super().__init__(parent,kind='download',**kwargs)
        self.canvas.configure(bg='white')
        self.press_job=None;self.pressed=None;self.held=False
        self.bind('<ButtonPress-1>',self.press)
        self.bind('<ButtonRelease-1>',self.release)
        self.bind('<B1-Motion>',self.motion)
        self.bind('<MouseWheel>',self.cancel_press,add='+')
        self.bind('<Button-3>',self.context)

    def _resize(self,event=None):
        position=self.item_position();self.columns=1;self.cell_width=max(1,self.canvas.winfo_width());self.cell_height=142
        self._extent();self.move_to_index(position);self._schedule()

    def _paint(self):
        self.paint_timer=None
        if self.mode!='tiles':return
        self._extent();self.canvas.delete('all');keys=self.get_children();chosen=set(self.selection())
        tasks={t.key:t for t in self.app.engine.tasks};width=self.canvas.winfo_width()
        for key in self.visible_keys():
            task=tasks.get(key)
            if not task:continue
            y=keys.index(key)*self.cell_height;data=self.item(key)
            rounded(self.canvas,3,y+3,width-8,132,14,fill='#f0f0f3' if self.app.selecting and key in chosen else 'white',outline=LINE)
            if data['image']:self.canvas.create_image(46,y+64,image=data['image'][0])
            title=self._lines(task.title if task.title else 'JM'+task.album_id,max(40,width-172),1)
            self.canvas.create_text(92,y+16,text=title,anchor='nw',font=('Microsoft YaHei UI',12,'bold'),fill=INK)
            self.canvas.create_text(width-28,y+18,text='⋯',anchor='ne',font=('Segoe UI',19),fill=MUTED)
            status=str(data['values'][2]);progress=str(data['values'][3])
            self.canvas.create_text(92,y+48,text=f'{status}  ·  {progress}',anchor='nw',fill=MUTED,font=self.tile_font)
            x1,x2=92,max(110,width-54);rounded(self.canvas,x1,y+75,x2-x1,7,3,fill=LINE,outline='')
            amount=percent(task.done,task.total,task.status)/100
            if amount:rounded(self.canvas,x1,y+75,max(1,(x2-x1)*amount),7,3,fill=ACCENT,outline='')
            detail=size_text(task.done,task.total,task.image_bytes,task.result_bytes,task.status)
            if task.status in ('running','resetting'):detail+=' · '+format_speed(task.speed)
            self.canvas.create_text(92,y+96,text=self._lines(detail,max(40,width-150),1),anchor='nw',fill=MUTED,font=self.tile_font)
            if self.app.selecting and key in chosen:self.canvas.create_text(width-23,y+73,text='✓',font=('Segoe UI',18,'bold'),fill=ACCENT)
        if not keys:self.canvas.create_text(width/2,95,text='还没有下载任务\n点击右下角 ＋ 添加漫画',justify='center',fill=MUTED,font=('Microsoft YaHei UI',12))

    def cancel_press(self,event=None):
        if self.press_job:self.after_cancel(self.press_job)
        self.press_job=None

    def press(self,event):
        self.cancel_press();self.pressed=(self.identify_at(event.x,event.y),event.x,event.y);self.held=False
        if self.pressed[0]:self.press_job=self.after(500,self.long_press)
        return 'break'

    def motion(self,event):
        if self.pressed and (abs(event.x-self.pressed[1])+abs(event.y-self.pressed[2])>12):self.cancel_press();self.pressed=None

    def long_press(self):
        self.press_job=None;self.held=True;self.app.selecting=True
        self.selection_add(self.pressed[0]);show_selection(self.app)

    def release(self,event):
        self.cancel_press()
        if not self.pressed or self.held:return 'break'
        key=self.pressed[0];self.pressed=None
        if not key or key!=self.identify_at(event.x,event.y):return 'break'
        if event.x>self.canvas.winfo_width()-60:task_menu(self.app,key,event.x_root,event.y_root);return 'break'
        if self.app.selecting:self.selection_toggle(key);show_selection(self.app);return 'break'
        self.selection_set(key);task=self.app.selected_task()
        if task.status in ('running','resetting'):self.app.engine.pause_one(key)
        elif task.status=='failed':self.app.retry()
        elif task.status=='done':self.app.open_selected()
        elif task.status in ('paused','cancelled'):self.app.retry()
        return 'break'

    def context(self,event):
        key=self.identify_at(event.x,event.y)
        if key:task_menu(self.app,key,event.x_root,event.y_root)


def build(app):
    install_styles(app.root)
    app.selecting=False;app.previous_states={};app.library_visible=False
    app.root.minsize(760,640);app.root.geometry('1000x850')
    outer=ttk.Frame(app.root,padding=22,style='Page.TFrame');outer.pack(fill='both',expand=True)
    header=ttk.Frame(outer,style='Page.TFrame');header.pack(fill='x',pady=(0,16))
    brand=ttk.Frame(header,style='Page.TFrame');brand.pack(side='left');ttk.Label(brand,text='JM Batch',font=('Segoe UI',26,'bold'),style='Page.TLabel').pack(anchor='w');ttk.Label(brand,text=f'ver {VERSION}',foreground=MUTED,style='Page.TLabel').pack(anchor='w')
    ttk.Button(header,text='⚙ 设置',command=app.settings_dialog).pack(side='right')
    app.update_button=ttk.Button(header);app.cleanup_button=ttk.Button(header)
    app.output_var=tk.StringVar(value=app.engine.settings.output);app.format_var=tk.StringVar(value=app.engine.settings.format)
    app.range_start=tk.StringVar();app.range_end=tk.StringVar()
    app.pages=ttk.Frame(outer);app.pages.pack(fill='both',expand=True)
    app.home_panel=ttk.Frame(app.pages);app.home_panel.place(x=0,y=0,relwidth=1,relheight=1)
    preview=Panel(app.home_panel,height=160);preview.pack(fill='x',pady=(0,12));ttk.Button(preview.body,text='漫画库  ↑',command=app.show_library).pack(anchor='w');app.preview_strip=ttk.Frame(preview.body);app.preview_strip.pack(fill='both',expand=True,pady=(10,0));ttk.Label(app.preview_strip,text='下载的漫画会显示在这里',foreground=MUTED).pack(expand=True)
    app.download_panel=Panel(app.home_panel);app.download_panel.pack(fill='both',expand=True);body=app.download_panel.body
    ttk.Label(body,text='下载页面',font=('Microsoft YaHei UI',20,'bold')).pack(anchor='w',pady=(0,12))
    bar=ttk.Frame(body);bar.pack(fill='x')
    app.start_button=ttk.Button(bar,text='开始全部',style='Accent.TButton',command=lambda:app.pause() if app.engine.running else app.start());app.start_button.pack(side='left')
    ttk.Button(bar,text='清除下载记录',command=lambda:clear_history(app)).pack(side='left',padx=10)
    app.pause_button=ttk.Button(bar);app.cancel_button=ttk.Button(bar)
    stats=ttk.Frame(body);stats.pack(fill='x',pady=12);app.summary=tk.StringVar();app.speed_text=tk.StringVar();ttk.Label(stats,textvariable=app.summary,foreground=MUTED).pack(side='left');ttk.Label(stats,textvariable=app.speed_text,foreground=MUTED).pack(side='right')
    holder=ttk.Frame(body);holder.pack(fill='both',expand=True)
    columns=('id','title','status','progress','size','format','resets');app.tree=DownloadList(holder,app,columns=columns,show='tree headings',selectmode='none')
    from download_covers import DownloadCovers
    app.download_covers=DownloadCovers(app.tree,app.home)
    scroll=ttk.Scrollbar(holder,command=app.tree.yview);scroll.pack(side='right',fill='y');app.tree.configure(yscrollcommand=scroll.set);app.tree.pack(fill='both',expand=True);app.tree.set_mode('tiles')
    fab=tk.Canvas(app.download_panel,width=62,height=62,bg='white',highlightthickness=0,takefocus=True,cursor='hand2')
    fab.create_oval(2,2,60,60,fill=ACCENT,outline=ACCENT);fab.create_text(31,30,text='＋',font=('Segoe UI',28),fill='white')
    fab.place(relx=1,rely=1,x=-26,y=-25,anchor='se');fab.bind('<Button-1>',lambda e:add_dialog(app));fab.bind('<Return>',lambda e:add_dialog(app));fab.bind('<space>',lambda e:add_dialog(app))
    app.task_sheet=ttk.Frame(app.download_panel,padding=24,style='Card.TFrame');app.selection_count=tk.StringVar();ttk.Label(app.task_sheet,textvariable=app.selection_count,anchor='center',font=('Microsoft YaHei UI',12,'bold')).pack(fill='x')
    actions(app.task_sheet,'删除任务','返回',lambda:remove_selected(app),lambda:exit_selection(app))
    # Keep existing diagnostic widgets as a model, accessed from the task menu.
    hidden=ttk.Frame(app.root);app.input=tk.Text(hidden);app.details=app._text_panel(hidden,4);app.logs=app._text_panel(hidden,4);app.progress_text=tk.StringVar();app.progressbar=ttk.Progressbar(hidden)
    app.root.bind('<Escape>',lambda e:hide_library(app) if app.library_visible else exit_selection(app))
    refresh_preview(app)


def add_dialog(app):
    window,body=modal(app.root,width=540)
    entry=tk.Text(body,height=3,wrap='word',bg=BG,fg=INK,relief='solid',bd=1,padx=12,pady=12,font=('Microsoft YaHei UI',11));entry.pack(fill='x');placeholder(entry,'请输入数字编号，多个编号请用空格隔开')
    row=ttk.Frame(body);row.pack(fill='x',pady=(18,0))
    for label,value in [('pdf','pdf'),('zip','zip'),('文件夹','images')]:ttk.Radiobutton(row,text=label,value=value,variable=app.format_var).pack(side='left',expand=True)
    def accept():
        if app._add(entry.get('1.0','end')):window.destroy();app.engine.running=True;app.engine.tick();app.render()
    actions(body,'添加','返回',accept,window.destroy)


def show_selection(app):
    app.selection_count.set(f'已选中{len(app.tree.selection())}项');app.task_sheet.place(x=2,relwidth=1,width=-4,rely=1,anchor='sw',y=-2);app.task_sheet.lift();app.tree._schedule()


def exit_selection(app):
    app.selecting=False;app.tree.selection_remove(app.tree.selection());app.task_sheet.place_forget();app.tree._schedule()


def remove_selected(app):
    keys=set(app.tree.selection())
    if any(t.key in keys and t.status in ('running','resetting','cancelling','cancel_failed') for t in app.engine.tasks):messagebox.showinfo('请先暂停','等待选中的任务停止后再删除记录。',parent=app.root);return
    def remove():
        app.engine.library.sync(app.engine.tasks);app.engine.tasks[:]=[t for t in app.engine.tasks if t.key not in keys];app.engine.save();exit_selection(app);app.render()
    if keys:confirm(app.root,'是否删除任务记录',remove)


def clear_history(app):
    keys=[t.key for t in app.engine.tasks if t.status in ('done','cancelled')]
    app.tree.selection_set(keys);remove_selected(app)


def task_menu(app,key,x,y):
    app.tree.selection_set(key);menu=tk.Menu(app.root,tearoff=False,bg='white',fg=INK)
    def information():
        app.update_details();window,body=modal(app.root,580);ttk.Label(body,text=app.details.get('1.0','end'),wraplength=530).pack();ttk.Button(body,text='返回',command=window.destroy).pack(pady=12)
    for label,action in [('任务信息',information),('重试',app.retry),('阅读',app.open_selected),('打开保存目录',app.open_output),('选择任务',lambda:(setattr(app,'selecting',True),show_selection(app)))]:menu.add_command(label=label,command=action)
    menu.tk_popup(x,y)


def refresh(app):
    app.start_button.configure(state='normal',text='暂停全部' if app.engine.running else '开始全部')
    for task in app.engine.tasks:
        old=app.previous_states.get(task.key);app.previous_states[task.key]=task.status
        if old and old!='done' and task.status=='done':notice(app.root,'下载完成');refresh_preview(app)
    if app.selecting:show_selection(app)
    app.tree._schedule()


def refresh_preview(app):
    import threading,queue
    results=queue.Queue()
    def load():
        from cover_cache import CoverCache
        cache=CoverCache(app.home);images=[]
        try:
            for key,item in app.engine.library.select('',False)[:5]:images.append(cache.load(item['path'],item['format']))
        except Exception:pass
        results.put(images)
    threading.Thread(target=load,daemon=True).start()
    def poll():
        try:images=results.get_nowait()
        except queue.Empty:app.root.after(80,poll);return
        if not images:return
        from PIL import ImageTk
        from covers import fit_cover
        for child in app.preview_strip.winfo_children():child.destroy()
        app.preview_images=[]
        for image in images:
            if image is None:continue
            photo=ImageTk.PhotoImage(fit_cover(image,(100,90)),master=app.root);app.preview_images.append(photo);label=ttk.Label(app.preview_strip,image=photo);label.pack(side='left',padx=7);label.bind('<Button-1>',lambda e:app.show_library())
    app.root.after(80,poll)


def show_library(app):
    from library_ui import LibraryWindow
    app.library_visible=True;app.home_panel.place_forget()
    existing=getattr(app,'library_window',None)
    if existing and existing.window.winfo_exists():existing.window.place(x=0,y=0,relwidth=1,relheight=1);existing.refresh()
    else:app.library_window=LibraryWindow(app,app.pages)
    panel=app.library_window.window
    def frame(step=0):
        if not app.library_visible:return
        panel.place(x=0,y=int(100*(1-step/12)**3),relwidth=1,relheight=1)
        if step<12:app.root.after(16,lambda:frame(step+1))
    frame()


def hide_library(app):
    existing=getattr(app,'library_window',None)
    if existing and existing.back():return
    app.library_visible=False
    if existing:existing.window.place_forget()
    app.home_panel.place(x=0,y=0,relwidth=1,relheight=1);refresh_preview(app)
