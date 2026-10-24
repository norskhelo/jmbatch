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
        self.tile_font.configure(size=12)
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
        self.selection_effects.begin(self.app.selecting)
        tasks={t.key:t for t in self.app.engine.tasks};width=self.canvas.winfo_width();pictures={}
        for key in self.visible_keys():
            task=tasks.get(key)
            if not task:continue
            y=keys.index(key)*self.cell_height;data=self.item(key)
            if self.app.selecting and key in chosen:rounded(self.canvas,3,y+3,width-8,132,10,fill='#f0f0f3',outline='')
            if keys.index(key):self.canvas.create_line(4,y+1,width-8,y+1,fill=LINE)
            if data['image']:
                from PIL import ImageTk,Image
                name=data['image'][0];picture=getattr(self,'row_images',{}).get(name)
                if picture is None:
                    source=tk.PhotoImage(master=self);self.tk.call(str(source),'copy',name);picture=ImageTk.PhotoImage(ImageTk.getimage(source).resize((80,100),Image.Resampling.LANCZOS),master=self)
                pictures[name]=picture;self.canvas.create_image(44,y+66,image=picture)
            title=self._lines(task.title if task.title else 'JM'+task.album_id,max(40,width-172),1)
            self.canvas.create_text(108,y+16,text=title,anchor='nw',font=('Microsoft YaHei UI',12,'bold'),fill=INK)
            self.canvas.create_text(width-28,y+18,text='⋯',anchor='ne',font=('Segoe UI',19),fill=MUTED)
            status=str(data['values'][2]);progress=f'{task.done}/{task.total}' if task.total else ''
            self.canvas.create_text(108,y+48,text=f'{status}'+('  ·  '+progress if task.status!='done' and progress else ''),anchor='nw',fill=MUTED,font=self.tile_font)
            edge=width-(44 if self.app.selecting else 12)
            self.canvas.create_text(edge,y+48,text=f'{percent(task.done,task.total,task.status):.0f}%',anchor='ne',fill=MUTED,font=self.tile_font)
            x1,x2=108,max(110,edge);rounded(self.canvas,x1,y+75,x2-x1,9,4,fill=LINE,outline='')
            amount=percent(task.done,task.total,task.status)/100
            if amount:rounded(self.canvas,x1,y+75,max(1,(x2-x1)*amount),9,4,fill=ACCENT,outline='')
            from download_display import format_size
            total=task.result_bytes if task.status=='done' and task.result_bytes else round(task.image_bytes*task.total/task.done) if task.done and task.total else 0
            detail=f'{format_size(task.result_bytes if task.status=="done" and task.result_bytes else task.image_bytes)} / {format_size(total) if total else "—"}'
            if task.status in ('running','resetting'):detail+=' · '+format_speed(task.speed)
            self.canvas.create_text(108,y+96,text=self._lines(detail,max(40,width-150),1),anchor='nw',fill=MUTED,font=self.tile_font)
            if self.app.selecting:self.selection_effects.draw(self.canvas,key,width-33,y+63,key in chosen)
        self.row_images=pictures
        if self.selection_effects.end() and self.paint_timer is None:self.paint_timer=self.after(16,self._paint)

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
        if self.app.selecting:self.selection_toggle(key);show_selection(self.app);return 'break'
        if event.x>self.canvas.winfo_width()-60:task_menu(self.app,key,event.x_root,event.y_root);return 'break'
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
    height=min(940,app.root.winfo_screenheight()-100);app.root.minsize(480,640);app.root.geometry(f'{int(height*.735)}x{height}')
    outer=app.main_page=ttk.Frame(app.root,padding=12,style='Page.TFrame');outer.pack(fill='both',expand=True)
    header=ttk.Frame(outer,style='Page.TFrame');header.pack(fill='x',pady=(0,16))
    brand=ttk.Frame(header,style='Page.TFrame');brand.pack(side='left');ttk.Label(brand,text='JM Batch',font=('Segoe UI',26,'bold'),style='Page.TLabel').pack(anchor='w');ttk.Label(brand,text=f'ver {VERSION}',foreground=MUTED,style='Page.TLabel').pack(anchor='w')
    app.settings_button=square_button(ttk.Button(header,text='⚙',command=app.settings_dialog));app.settings_button.pack(side='right',anchor='s')
    app.update_button=ttk.Button(header);app.cleanup_button=ttk.Button(header)
    app.output_var=tk.StringVar(value=app.engine.settings.output);app.format_var=tk.StringVar(value=app.engine.settings.format)
    app.range_start=tk.StringVar();app.range_end=tk.StringVar()
    app.pages=ttk.Frame(outer);app.pages.pack(fill='both',expand=True)
    app.pages.bind('<Configure>',lambda e:align_page_exchange(app))
    app.root.bind('<Configure>',lambda e:align_page_exchange(app) if e.widget==app.root else None,add='+')
    app.page_offset=int(height*.23)
    app.download_panel=Panel(app.pages,connected_top=True);body=app.download_panel.body
    ttk.Label(body,text='下载页面',font=('Microsoft YaHei UI',20,'bold')).pack(anchor='w',pady=(0,12))
    bar=app.download_toolbar=ttk.Frame(body);bar.pack(fill='x')
    app.start_button=ttk.Button(bar,text='开始全部',style='Accent.TButton',command=lambda:app.pause() if app.engine.running else app.start());app.start_button.pack(side='left')
    icon_button(bar,'trash','清除下载记录',lambda:clear_history(app)).pack(side='left',padx=10)
    app.pause_button=ttk.Button(bar);app.cancel_button=ttk.Button(bar)
    app.summary=tk.StringVar();app.speed_text=tk.StringVar()
    list_panel=Panel(body,padding=22);list_panel.configure(bg='white');list_panel.pack(fill='both',expand=True,pady=(18,12));ttk.Label(list_panel.body,text='下载列表',font=('Microsoft YaHei UI',14,'bold')).pack(anchor='w',pady=(0,12))
    footer=ttk.Frame(list_panel.body);footer.pack(side='bottom',fill='x',pady=(8,14));hint=ttk.Label(footer,text='点击任务停止 · 长按批量操作',foreground=MUTED,anchor='center',justify='center');hint.pack(fill='x',ipady=16);hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(1,e.width)))
    holder=ttk.Frame(list_panel.body);holder.pack(fill='both',expand=True)
    columns=('id','title','status','progress','size','format','resets');app.tree=DownloadList(holder,app,columns=columns,show='tree headings',selectmode='none')
    from download_covers import DownloadCovers
    app.download_covers=DownloadCovers(app.tree,app.home)
    scroll=ttk.Scrollbar(holder,command=app.tree.yview)
    def scrolled(first,last):
        scroll.set(first,last)
        if float(first)>0 or float(last)<1:scroll.pack(side='right',fill='y')
        else:scroll.pack_forget()
    app.tree.configure(yscrollcommand=scrolled);app.tree.pack(fill='both',expand=True);app.tree.set_mode('tiles')
    fab_size=control_height(list_panel,ADD_ACTION_FONT)
    footer.pack_configure(padx=(0,fab_size+12))
    fab_width=fab_size
    fab=tk.Canvas(list_panel,width=fab_width,height=fab_size,bg='white',highlightthickness=0,takefocus=True,cursor='hand2')
    fab.create_oval(1,1,fab_width-1,fab_size-1,fill=ACCENT,outline=ACCENT);fab.create_text(fab_width/2,fab_size/2,text='＋',font=ADD_ACTION_FONT,fill='white');app.add_button=fab
    fab.place(relx=1,rely=1,x=-26,y=-25,anchor='se');fab.bind('<Button-1>',lambda e:add_dialog(app));fab.bind('<Return>',lambda e:add_dialog(app));fab.bind('<space>',lambda e:add_dialog(app))
    app.task_sheet=Panel(app.download_panel,padding=20,height=160);app.selection_count=tk.StringVar();ttk.Label(app.task_sheet.body,textvariable=app.selection_count,anchor='center',font=('Microsoft YaHei UI',12,'bold')).pack(fill='x')
    actions(app.task_sheet.body,'删除任务','返回',lambda:remove_selected(app),lambda:exit_selection(app))
    # Keep existing diagnostic widgets as a model, accessed from the task menu.
    hidden=ttk.Frame(app.root);app.input=tk.Text(hidden);app.details=app._text_panel(hidden,4);app.logs=app._text_panel(hidden,4);app.progress_text=tk.StringVar();app.progressbar=ttk.Progressbar(hidden)
    app.root.bind('<Escape>',lambda e:back(app))
    from library_ui import LibraryWindow
    app.library_window=LibraryWindow(app,app.pages)
    app.page_exchange=None;app.page_animation=None
    app.seam_canvas=tk.Canvas(app.pages,highlightthickness=0,bg='white',cursor='hand2')
    app.seam_canvas.bind('<ButtonRelease-1>',lambda e:show_library(app) if not app.library_visible else hide_library(app,back=False))
    bind_page_switch(app,app.download_panel,False)
    bind_page_switch(app,app.library_window.window,True)
    app.library_window.sort_button.master.bind('<Configure>',lambda e:align_page_exchange(app))
    app.download_toolbar.bind('<Configure>',lambda e:align_page_exchange(app))
    app.root.after_idle(lambda:layout_live_pages(app))


def back(app):
    if getattr(app,'settings_page',None) is not None:app.close_settings()
    elif getattr(app,'page_exchange',None) is None:
        if app.library_visible:hide_library(app)
        else:exit_selection(app)
    return 'break'


def add_dialog(app):
    window,body=modal(app.root,width=540)
    entry=Input(body,multiline=True);entry.pack(fill='x',pady=(10,8));placeholder(entry,'请输入数字编号，多个编号请用空格隔开')
    row=ttk.Frame(body);row.pack(fill='x',pady=(18,18))
    for label,value in [('pdf','pdf'),('zip','zip'),('文件夹','images')]:ttk.Radiobutton(row,text=label,value=value,variable=app.format_var).pack(side='left',expand=True)
    def accept():
        if app._add(entry.get('1.0','end')):window.destroy();app.engine.running=True;app.engine.tick();app.render()
    actions(body,'添加','返回',accept,window.destroy)


def show_selection(app):
    app.selection_count.set(f'已选中{len(app.tree.selection())}项')
    if not app.task_sheet.winfo_ismapped():slide_sheet(app.task_sheet)
    app.tree._schedule()


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
    app.start_button.configure(state='normal',text='Ⅱ  暂停全部' if app.engine.running else '▶  开始全部')
    for task in app.engine.tasks:
        old=app.previous_states.get(task.key);app.previous_states[task.key]=task.status
        if old and old!='done' and task.status=='done':notice(app.root,'下载完成');refresh_preview(app)
    if app.selecting:show_selection(app)
    app.tree._schedule()


def refresh_preview(app):
    # Refresh data without replacing either persistent page or its viewport.
    view=getattr(app,'library_window',None)
    if view is not None:view.refresh()
    if getattr(app,'page_exchange',None) is None:app.root.after_idle(lambda:paint_live_seam(app))


def native_page_alpha(widget,alpha):
    """Apply opacity to the actual Windows child window and all of its controls."""
    import ctypes
    from ctypes import wintypes
    alpha=round(max(0,min(1,alpha))*255)
    if getattr(widget,'_page_alpha',255)==alpha:return
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int];user.GetWindowLongW.restype=ctypes.c_long
    user.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_long];user.SetWindowLongW.restype=ctypes.c_long
    user.SetLayeredWindowAttributes.argtypes=[wintypes.HWND,wintypes.COLORREF,wintypes.BYTE,wintypes.DWORD]
    hwnd=widget.winfo_id()
    if not hasattr(widget,'_page_style'):widget._page_style=user.GetWindowLongW(hwnd,-20)
    user.SetWindowLongW(hwnd,-20,widget._page_style|0x80000)
    if not user.SetLayeredWindowAttributes(hwnd,0,alpha,2):raise ctypes.WinError(ctypes.get_last_error())
    if alpha==255:user.SetWindowLongW(hwnd,-20,widget._page_style)
    widget._page_alpha=alpha


def page_header_bottom(app, library):
    page=app.library_window.window if library else app.download_panel
    toolbar=app.library_window.sort_button.master if library else app.download_toolbar
    return toolbar.winfo_rooty()-page.winfo_rooty()+toolbar.winfo_reqheight()


def layout_live_pages(app):
    if not hasattr(app,'library_window'):return
    width,height=app.pages.winfo_width(),app.pages.winfo_height()
    if width<2 or height<2:return
    header=max(page_header_bottom(app,True),page_header_bottom(app,False))
    app.page_offset=min(max(int(app.root.winfo_height()*.18),header+16),height//2)
    app.page_size=(width,height)
    for page,surface in ((app.download_panel,app.download_panel),(app.library_window.window,app.library_window.surface)):
        page.place(x=0,width=width,height=height+28,relwidth=0,relheight=0)
        surface.content_height=height-app.page_offset
        surface.itemconfigure(surface.item,height=max(1,surface.content_height-2*surface.padding))
    app.library_window.page_content_height=height-app.page_offset
    # Clip the persistent child pages at the common viewport, including its lower corners.
    import ctypes
    from ctypes import wintypes
    gdi=ctypes.windll.gdi32;user=ctypes.windll.user32
    gdi.CreateRoundRectRgn.restype=ctypes.c_void_p;gdi.DeleteObject.argtypes=[ctypes.c_void_p]
    user.SetWindowRgn.argtypes=[wintypes.HWND,ctypes.c_void_p,wintypes.BOOL]
    region=gdi.CreateRoundRectRgn(0,0,width+1,height+1,36,36)
    if not user.SetWindowRgn(app.pages.winfo_id(),region,True):gdi.DeleteObject(region)
    settle_live_pages(app)


def settle_live_pages(app):
    front=app.library_window.window if app.library_visible else app.download_panel
    rear=app.download_panel if app.library_visible else app.library_window.window
    for page,y in ((rear,0),(front,app.page_offset)):
        native_page_alpha(page,1);page.place_configure(y=y)
    front.lift();app.root.after_idle(lambda:paint_live_seam(app))


def paint_live_seam(app):
    # Fit the seam below the rear toolbar so compact spacing keeps its icons clear.
    if not hasattr(app,'seam_canvas') or getattr(app,'page_exchange',None) is not None:return
    # Keep the last valid seam while the home page is offscreen behind settings.
    if getattr(app,'settings_page',None) is not None:return
    from PIL import Image,ImageGrab,ImageFilter,ImageTk,ImageDraw
    app.seam_canvas.place_forget();app.root.update_idletasks()
    if getattr(app,'page_exchange',None) is not None:return
    width,height=app.pages.winfo_width(),app.pages.winfo_height()
    if width<30 or height<60:return
    rear=app.download_panel if app.library_visible else app.library_window.window
    band=max(0,min(54,app.page_offset-page_header_bottom(app,not app.library_visible)-4));top=app.page_offset-band
    if band<1:return
    picture=ImageGrab.grab(window=rear.winfo_id()).crop((14,top,width-14,app.page_offset)).convert('RGB')
    mask=Image.new('L',picture.size);draw=ImageDraw.Draw(mask)
    for y in range(band):draw.line((0,y,picture.width,y),fill=round(255*y/max(1,band-1)))
    softened=Image.composite(picture.filter(ImageFilter.GaussianBlur(1.8)),picture,mask)
    fade=mask.point(lambda value:max(0,value*2-255));picture=Image.composite(Image.new('RGB',picture.size,'white'),softened,fade)
    app.seam_image=ImageTk.PhotoImage(picture,master=app.root);app.seam_canvas.delete('all');app.seam_canvas.create_image(0,0,image=app.seam_image,anchor='nw')
    app.seam_canvas.place(x=14,y=top,width=width-28,height=band);tk.Misc.lift(app.seam_canvas)


def show_library(app,animate=True):set_front_page(app,True,animate)


def hide_library(app,back=True,animate=True):
    if getattr(app,'page_exchange',None) is not None:return
    if back and getattr(app,'page_exchange',None) is None and app.library_window.back():return
    set_front_page(app,False,animate)


def set_front_page(app,library,animate=True):
    if getattr(app,'page_exchange',None) is not None:return
    if app.library_visible==library:return
    source=app.library_visible;app.library_visible=library
    if not animate:settle_live_pages(app);return
    import time
    from types import SimpleNamespace
    outgoing=app.library_window.window if source else app.download_panel
    incoming=app.download_panel if source else app.library_window.window
    app.seam_canvas.place_forget()
    app.root.focus_set()
    state=app.page_exchange=SimpleNamespace(source_library=source,outgoing=outgoing,incoming=incoming,progress=0.,direction=1,last_frame=time.monotonic(),incoming_on_top=False)
    def ease(t):return t*t*(3-2*t)
    def frame():
        if app.page_exchange is not state:return
        now=time.monotonic();state.progress=max(0,min(1,state.progress+state.direction*(now-state.last_frame)/0.99));state.last_frame=now
        top=state.progress>=1/3
        if top!=state.incoming_on_top:
            state.incoming_on_top=top;(incoming if top else outgoing).lift()
        if not top:
            t=ease(state.progress/(1/3));incoming.place_configure(y=round(-28*t));native_page_alpha(incoming,1);outgoing.place_configure(y=app.page_offset);native_page_alpha(outgoing,1-t)
        else:
            t=ease((state.progress-1/3)/(2/3));incoming.place_configure(y=round(-28+(app.page_offset+28)*t));native_page_alpha(incoming,1);outgoing.place_configure(y=round(app.page_offset*(1-t)));native_page_alpha(outgoing,t)
        if state.direction>0 and state.progress>=1 or state.direction<0 and state.progress<=0:finish_page_exchange(app)
        else:app.page_animation=app.root.after(16,frame)
    frame()


def finish_page_exchange(app):
    job=getattr(app,'page_animation',None)
    if job:app.root.after_cancel(job)
    app.page_animation=None;state=getattr(app,'page_exchange',None);app.page_exchange=None
    if state is not None:app.library_visible=state.source_library if state.direction<0 else not state.source_library
    if hasattr(app,'library_window'):settle_live_pages(app)


def align_page_exchange(app):
    if not hasattr(app,'library_window'):return
    size=(app.pages.winfo_width(),app.pages.winfo_height())
    header=max(page_header_bottom(app,True),page_header_bottom(app,False))
    offset=min(max(int(app.root.winfo_height()*.18),header+16),size[1]//2)
    if size!=getattr(app,'page_size',None) or offset!=app.page_offset:
        finish_page_exchange(app);layout_live_pages(app)


def bind_page_switch(app,panel,to_library):
    tag=f'PageSwitch:{panel}';pressed=None
    def handle(event):
        nonlocal pressed
        moving=getattr(app,'page_exchange',None) is not None
        if moving:pressed=None;return 'break'
        if not moving and app.library_visible==to_library:return
        if event.type==tk.EventType.ButtonPress:pressed=(event.x_root,event.y_root)
        elif event.type==tk.EventType.Motion:
            if pressed and abs(event.x_root-pressed[0])+abs(event.y_root-pressed[1])>12:pressed=None
        elif event.type==tk.EventType.ButtonRelease:
            clicked=pressed is not None;pressed=None
            if clicked:set_front_page(app,to_library)
        return 'break'
    for event in ('<ButtonPress>','<Double-ButtonPress-1>','<ButtonRelease>','<Motion>','<MouseWheel>','<KeyPress>','<KeyRelease>'):app.root.bind_class(tag,event,handle)
    def bind(widget):
        widget.bindtags((tag,)+widget.bindtags())
        for child in widget.winfo_children():bind(child)
    bind(panel)
