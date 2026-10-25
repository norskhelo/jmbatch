"""Shared grayscale surfaces, anchored panels and short-lived notices."""
import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

BG, INK, MUTED, LINE, ACCENT, BLUE = '#f5f5f7', '#1d1f26', '#747780', '#dadce1', '#73757c', '#3363bd'


CONTROL_FONT = ('Microsoft YaHei UI', 12)
BUTTON_FONT = ('Microsoft YaHei UI', 14)
SMALL_ICON_FONT = ('Microsoft YaHei UI', 11)
ADD_ACTION_FONT = ('Segoe UI', 28)


def control_height(widget, font=CONTROL_FONT, ratio=2.25):
    face = tkfont.Font(root=widget, font=font)
    size = face.actual('size')
    pixels = size * float(widget.tk.call('tk', 'scaling')) if size > 0 else -size
    return max(math.ceil(pixels * ratio), face.metrics('linespace') + 2)


def install_styles(root):
    from PIL import Image, ImageDraw, ImageTk
    style = ttk.Style(root)
    root.option_add('*Font',('Microsoft YaHei UI',12))
    root._button_surfaces = []
    for name, fill, text in [('TButton', 'white', INK), ('Accent.TButton', ACCENT, 'white')]:
        pictures = []
        for color in (fill, '#e8e8ec' if fill == 'white' else '#62646c'):
            image = Image.new('RGBA', (16, 16))
            ImageDraw.Draw(image).rounded_rectangle((0, 0, 15, 15), radius=6, fill=color, outline=LINE if fill == 'white' else color)
            pictures.append(ImageTk.PhotoImage(image, master=root))
        root._button_surfaces.extend(pictures)
        element = name + '.round'
        style.element_create(element, 'image', pictures[0], ('active', pictures[1]), border=6, padding=0, sticky='nswe')
        style.layout(name, [(element, {'sticky': 'nswe', 'children': [('Button.padding', {'sticky': 'nswe', 'children': [('Button.label', {'sticky': 'nswe'})]})]})])
        extra = control_height(root, BUTTON_FONT) - tkfont.Font(root=root, font=BUTTON_FONT).metrics('linespace')
        style.configure(name, foreground=text, background='white', padding=(6, extra//2, 6, extra-extra//2),font=BUTTON_FONT,width=0)
        style.map(name, background=[('active','white'),('disabled','white')])
    style.configure('SmallIcon.TButton', font=SMALL_ICON_FONT)
    style.configure('Page.TFrame', background=BG)
    style.configure('Page.TLabel', background=BG)
    style.configure('TLabel',font=('Microsoft YaHei UI',12))
    style.configure('TSeparator',background=LINE)
    style.configure('Vertical.TScrollbar',arrowsize=0,width=8,background='#b6b8bf',troughcolor=BG,borderwidth=0)
    style.layout('Vertical.TScrollbar',[('Vertical.Scrollbar.trough',{'sticky':'ns','children':[('Vertical.Scrollbar.thumb',{'expand':1,'sticky':'nswe'})]})])
    for name in ('TRadiobutton', 'TCheckbutton'):
        style.configure(name, background='white', foreground=INK,font=('Microsoft YaHei UI',12))
        style.map(name, background=[('active', BG)])


def rounded(canvas, x, y, width_px, height, radius=16, **kwargs):
    width = width_px
    r = min(radius, width / 2, height / 2)
    points = [x+r,y,x+width-r,y,x+width,y,x+width,y+r,x+width,y+height-r,
              x+width,y+height,x+width-r,y+height,x+r,y+height,x,y+height,x,y+height-r,x,y+r,x,y]
    return canvas.create_polygon(points, smooth=True, splinesteps=20, **kwargs)


class Panel(tk.Canvas):
    def __init__(self, parent, padding=18, color='white', open_bottom=False, connected_top=False, **kwargs):
        super().__init__(parent, bg=BG, highlightthickness=0, **kwargs)
        self.body = ttk.Frame(self, style='Card.TFrame')
        self.padding, self.color = padding, color
        self.open_bottom=open_bottom
        self.connected_top=connected_top
        self.surface = rounded(self, 1, 1, 10, 10, fill=color, outline=LINE)
        self.item = self.create_window(padding, padding, window=self.body, anchor='nw')
        self.bind('<Configure>', self.resize)

    def lift(self,aboveThis=None):
        return tk.Misc.lift(self,aboveThis)

    def resize(self, event):
        if event.width<2 or event.height<2:return
        from PIL import Image,ImageDraw,ImageTk
        self.delete(self.surface)
        w,h=max(1,event.width),max(1,event.height)
        picture=Image.new('RGB',(w*2,h*2),self.cget('bg'));draw=ImageDraw.Draw(picture)
        if self.connected_top:
            # Continue the rear surface and its sides through the front page's top corners.
            draw.rectangle((1,0,w*2-2,min(h*2,40)),fill=self.color)
            draw.line((1,0,1,min(h*2,40)),fill=LINE,width=2)
            draw.line((w*2-2,0,w*2-2,min(h*2,40)),fill=LINE,width=2)
        draw.rounded_rectangle((1,1,w*2-2,h*2-2+(70 if self.open_bottom else 0)),radius=36,fill=self.color,outline=LINE,width=2)
        self.picture=ImageTk.PhotoImage(picture.resize((w,h),Image.Resampling.LANCZOS),master=self)
        self.surface=self.create_image(0,0,image=self.picture,anchor='nw')
        self.tag_lower(self.surface)
        self.itemconfigure(self.item, width=max(1,event.width-2*self.padding), height=max(1,getattr(self,'content_height',event.height)-2*self.padding))


class Input(tk.Canvas):
    """The concept's lightly filled rounded input, with a native editable interior."""
    def __init__(self,parent,textvariable=None,multiline=False,height=None,**kwargs):
        self.multiline=multiline
        self.base_height=control_height(parent)
        super().__init__(parent,height=height or self.base_height,highlightthickness=0,bg='white',**kwargs)
        options=dict(bg=BG,fg=INK,relief='flat',bd=0,highlightthickness=0,font=CONTROL_FONT)
        self.editor=tk.Text(self,wrap='word',height=1,padx=0,pady=0,**options) if multiline else tk.Entry(self,textvariable=textvariable,**options)
        self.inset=max(1,(self.base_height-tkfont.Font(root=self,font=CONTROL_FONT).metrics('linespace'))//2)
        self.item=self.create_window(12,self.inset,window=self.editor,anchor='nw')
        self.fit_job=None
        if multiline:
            self.editor.bind('<<Modified>>',self.content_changed)
            self.editor.bind('<Configure>',self.schedule_fit)
        self.bind('<Configure>',self.resize)
    def resize(self,event):
        super().delete('surface');rounded(self,1,1,event.width-2,event.height-2,8,fill=BG,outline=LINE,tags='surface');self.tag_lower('surface')
        self.itemconfigure(self.item,width=max(1,event.width-24),height=max(1,event.height-2*self.inset))
    def content_changed(self,event=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False);self.schedule_fit()
    def schedule_fit(self,event=None):
        if self.fit_job is None:self.fit_job=self.after_idle(self.fit_content)
    def fit_content(self):
        self.fit_job=None
        if not self.winfo_exists():return
        count=self.editor.count('1.0','end-1c','displaylines')
        lines=(count[0] if count else 0)+1
        line_height=tkfont.Font(root=self,font=self.editor.cget('font')).metrics('linespace')
        height=self.base_height+(lines-1)*line_height
        if int(self.cget('height'))!=height:
            self.configure(height=height)
            self.winfo_toplevel().event_generate('<<InputSizeChanged>>',when='tail')
    def get(self,*args):return self.editor.get(*args)
    def focus_set(self):return self.editor.focus_set()
    def insert(self,*args):return self.editor.insert(*args)
    def delete(self,*args):return self.editor.delete(*args)


def modal(owner, width=440, height=None, blur=False):
    host = owner.winfo_toplevel()
    shade = None
    if blur:
        try:
            from PIL import ImageGrab, ImageFilter, ImageTk
            host.update_idletasks()
            shot = ImageGrab.grab(window=host.winfo_id()).filter(ImageFilter.GaussianBlur(7))
            shade = tk.Label(host, borderwidth=0)
            shade.image = ImageTk.PhotoImage(shot, master=host)
            shade.configure(image=shade.image)
            shade.place(x=0, y=0, relwidth=1, relheight=1)
        except (OSError, tk.TclError):
            shade = None
    window = tk.Toplevel(host)
    window.withdraw(); window.transient(host); window.overrideredirect(True)
    window.configure(bg=LINE)
    body = ttk.Frame(window, padding=22, style='Card.TFrame')
    body.pack(fill='both', expand=True, padx=1, pady=1)
    def layout():
        window.update_idletasks()
        w, h = min(width,host.winfo_width()-32), height or body.winfo_reqheight()+2
        x = host.winfo_rootx()+(host.winfo_width()-w)//2
        y = host.winfo_rooty()+max(12,(host.winfo_height()-h)//2)
        window.geometry(f'{w}x{h}+{x}+{y}')
    clipped_size=[None]
    def clip(event):
        if event.widget is not window:return
        size=(event.width,event.height)
        if size==clipped_size[0]:return
        clipped_size[0]=size
        # Clip only this borderless Tk dialog to the rounded outline in the concept.
        try:
            import ctypes
            from ctypes import wintypes
            ctypes.windll.gdi32.CreateRoundRectRgn.restype=ctypes.c_void_p
            ctypes.windll.user32.GetParent.argtypes=[wintypes.HWND]
            ctypes.windll.user32.GetParent.restype=wintypes.HWND
            ctypes.windll.user32.SetWindowRgn.argtypes=[wintypes.HWND,ctypes.c_void_p,wintypes.BOOL]
            ctypes.windll.gdi32.DeleteObject.argtypes=[ctypes.c_void_p]
            region=ctypes.windll.gdi32.CreateRoundRectRgn(0,0,event.width+1,event.height+1,22,22)
            hwnd=ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
            if not ctypes.windll.user32.SetWindowRgn(hwnd,region,True):ctypes.windll.gdi32.DeleteObject(region)
        except (AttributeError,OSError):pass
    def show():
        layout()
        window.deiconify(); window.lift(); window.grab_set(); window.focus_set()
    def destroyed(event):
        if event.widget is window and shade is not None:
            shade.destroy()
    window.bind('<Destroy>',destroyed,add='+')
    window.bind('<Configure>',clip,add='+')
    window.bind('<Escape>',lambda e: window.destroy())
    window.bind('<<InputSizeChanged>>',lambda e:window.after_idle(layout))
    window.after_idle(show)
    return window, body


def actions(parent, left, right, accept, cancel):
    row=ttk.Frame(parent,style='Card.TFrame');row.pack(anchor='center',pady=(18,0))
    row.columnconfigure((0,1),weight=1,uniform='action')
    ttk.Button(row,text=left,style='Accent.TButton',command=accept).grid(row=0,column=0,sticky='ew',padx=(0,5))
    ttk.Button(row,text=right,command=cancel).grid(row=0,column=1,sticky='ew',padx=(5,0))
    return row


def slide_sheet(panel,step=0,bottom=None):
    if not panel.winfo_exists():return
    if step and panel.winfo_manager()!='place':return
    height=int(panel.cget('height'));offset=round(height*(1-step/12)**3)-1
    panel.place(x=1,rely=1 if bottom is None else 0,y=offset if bottom is None else bottom()+offset,relwidth=1,width=-2,anchor='sw');panel.lift()
    if step<12:panel.after(16,lambda:slide_sheet(panel,step+1,bottom))


def square_button(button, font=BUTTON_FONT, content_font=None):
    face=tkfont.Font(root=button,font=content_font or font)
    size=control_height(button,font)
    content=button.image.width() if hasattr(button,'image') else face.measure(button.cget('text'))
    content_height=button.image.height() if hasattr(button,'image') else face.metrics('linespace')
    horizontal=max(0,size-content);vertical=max(0,size-content_height)
    button.configure(width=0,padding=(horizontal//2,vertical//2,horizontal-horizontal//2,vertical-vertical//2))
    button.icon_only=True
    return button


def icon_button(parent, kind, text='', command=None, font=BUTTON_FONT, icon_ratio=None):
    """Small monochrome line icons drawn from the confirmed concept."""
    from PIL import Image,ImageDraw,ImageTk
    im=Image.new('RGBA',(72,72));d=ImageDraw.Draw(im);c=INK
    if kind=='trash':
        d.line((18,24,22,62,53,62,57,24),fill=c,width=5);d.line((12,20,62,20),fill=c,width=5);d.line((28,20,28,11,46,11,46,20),fill=c,width=5)
        d.line((31,31,31,53),fill=c,width=4);d.line((43,31,43,53),fill=c,width=4)
    elif kind=='folder':
        d.line((8,59,8,18,29,18,35,26,64,26,64,59,8,59),fill=c,width=4);d.line((36,33,36,51),fill=c,width=4);d.line((27,42,45,42),fill=c,width=4)
    elif kind=='share':
        d.line((18,34,18,62,56,62,56,34),fill=c,width=4);d.line((37,46,37,10),fill=c,width=4);d.line((23,24,37,10,51,24),fill=c,width=4)
    size=round(control_height(parent,font)*icon_ratio) if icon_ratio is not None else tkfont.Font(root=parent,font=font).metrics('linespace')
    picture=ImageTk.PhotoImage(im.resize((size,size),Image.Resampling.LANCZOS),master=parent)
    button=ttk.Button(parent,text=('  '+text if text else ''),image=picture,compound='left' if text else 'none',command=command);button.image=picture
    if not text:square_button(button,font)
    return button


def confirm(owner, text, yes, extra=None):
    window, body=modal(owner,blur=True)
    ttk.Label(body,text=text,anchor='center',justify='center',wraplength=380,font=('Microsoft YaHei UI',12,'bold')).pack(fill='x',pady=(18,18))
    if extra:extra(body)
    actions(body,'确认','取消',lambda:(window.destroy(),yes()),window.destroy)
    return window


def notice(owner, text):
    host=owner.winfo_toplevel()
    panel=ttk.Label(host,text='✓  '+text,padding=(20,12),background='white',foreground=INK,relief='solid',borderwidth=1)
    panel.place(relx=.5,y=16,anchor='n');panel.lift()
    host.after(3000,panel.destroy)


def placeholder(entry, text):
    if isinstance(entry,Input):entry=entry.editor
    label=ttk.Label(entry,text=text,foreground=MUTED,background=BG)
    label.place(x=1,y=0);label.bind('<Button-1>',lambda e: entry.focus_set())
    def refresh(*_):
        value=entry.get('1.0','end-1c') if isinstance(entry,tk.Text) else entry.get()
        if value or entry.focus_get() is entry:label.place_forget()
        else:label.place(x=1,y=0)
    entry.bind('<FocusIn>',refresh,add='+');entry.bind('<FocusOut>',refresh,add='+');entry.bind('<KeyRelease>',refresh,add='+')
    if isinstance(entry,tk.Text):entry.bind('<<Modified>>',refresh,add='+')
