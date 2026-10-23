"""Shared grayscale surfaces, anchored panels and short-lived notices."""
import tkinter as tk
from tkinter import ttk

BG, INK, MUTED, LINE, ACCENT, BLUE = '#f5f5f7', '#1d1f26', '#747780', '#dadce1', '#73757c', '#3363bd'


def install_styles(root):
    from PIL import Image, ImageDraw, ImageTk
    style = ttk.Style(root)
    root._button_surfaces = []
    for name, fill, text in [('TButton', 'white', INK), ('Accent.TButton', ACCENT, 'white')]:
        pictures = []
        for color in (fill, '#e8e8ec' if fill == 'white' else '#62646c'):
            image = Image.new('RGBA', (40, 40))
            ImageDraw.Draw(image).rounded_rectangle((0, 0, 39, 39), radius=9, fill=color, outline=LINE if fill == 'white' else color)
            pictures.append(ImageTk.PhotoImage(image, master=root))
        root._button_surfaces.extend(pictures)
        element = name + '.round'
        style.element_create(element, 'image', pictures[0], ('active', pictures[1]), border=10, sticky='nswe')
        style.layout(name, [(element, {'sticky': 'nswe', 'children': [('Button.padding', {'sticky': 'nswe', 'children': [('Button.label', {'sticky': 'nswe'})]})]})])
        style.configure(name, foreground=text, padding=(15, 10))
    style.configure('Page.TFrame', background=BG)
    style.configure('Page.TLabel', background=BG)
    for name in ('TRadiobutton', 'TCheckbutton'):
        style.configure(name, background='white', foreground=INK)
        style.map(name, background=[('active', BG)])


def rounded(canvas, x, y, width, height, radius=16, **kwargs):
    r = min(radius, width / 2, height / 2)
    points = [x+r,y,x+width-r,y,x+width,y,x+width,y+r,x+width,y+height-r,
              x+width,y+height,x+width-r,y+height,x+r,y+height,x,y+height,x,y+height-r,x,y+r,x,y]
    return canvas.create_polygon(points, smooth=True, splinesteps=20, **kwargs)


class Panel(tk.Canvas):
    def __init__(self, parent, padding=18, color='white', **kwargs):
        super().__init__(parent, bg=BG, highlightthickness=0, **kwargs)
        self.body = ttk.Frame(self, style='Card.TFrame')
        self.padding, self.color = padding, color
        self.surface = rounded(self, 1, 1, 10, 10, fill=color, outline=LINE)
        self.item = self.create_window(padding, padding, window=self.body, anchor='nw')
        self.bind('<Configure>', self.resize)

    def resize(self, event):
        self.delete(self.surface)
        self.surface = rounded(self, 1, 1, max(1,event.width-2), max(1,event.height-2), fill=self.color, outline=LINE)
        self.tag_lower(self.surface)
        self.itemconfigure(self.item, width=max(1,event.width-2*self.padding), height=max(1,event.height-2*self.padding))


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
    def show():
        window.update_idletasks()
        w, h = min(width,host.winfo_width()-32), height or body.winfo_reqheight()+2
        x = host.winfo_rootx()+(host.winfo_width()-w)//2
        y = host.winfo_rooty()+max(12,(host.winfo_height()-h)//2)
        window.geometry(f'{w}x{h}+{x}+{y}')
        window.deiconify(); window.lift(); window.grab_set(); window.focus_set()
    def destroyed(event):
        if event.widget is window and shade is not None:
            shade.destroy()
    window.bind('<Destroy>',destroyed,add='+')
    window.bind('<Escape>',lambda e: window.destroy())
    window.after_idle(show)
    return window, body


def actions(parent, left, right, accept, cancel):
    row=ttk.Frame(parent,style='Card.TFrame');row.pack(fill='x',pady=(18,0))
    row.columnconfigure((0,1),weight=1,uniform='action')
    ttk.Button(row,text=left,style='Accent.TButton',command=accept).grid(row=0,column=0,sticky='ew',padx=(0,5))
    ttk.Button(row,text=right,command=cancel).grid(row=0,column=1,sticky='ew',padx=(5,0))
    return row


def confirm(owner, text, yes, extra=None):
    window, body=modal(owner,blur=True)
    ttk.Label(body,text=text,anchor='center',justify='center',wraplength=380,font=('Microsoft YaHei UI',12,'bold')).pack(fill='x')
    if extra:extra(body)
    actions(body,'确认','取消',lambda:(window.destroy(),yes()),window.destroy)
    return window


def notice(owner, text):
    host=owner.winfo_toplevel()
    panel=ttk.Label(host,text='✓  '+text,padding=(20,12),background='white',foreground=INK,relief='solid',borderwidth=1)
    panel.place(relx=.5,y=16,anchor='n');panel.lift()
    host.after(3000,panel.destroy)


def placeholder(entry, text):
    label=ttk.Label(entry,text=text,foreground=MUTED,background=BG)
    label.place(x=10,y=10);label.bind('<Button-1>',lambda e: entry.focus_set())
    def refresh(*_):
        value=entry.get('1.0','end-1c') if isinstance(entry,tk.Text) else entry.get()
        if value or entry.focus_get() is entry:label.place_forget()
        else:label.place(x=10,y=10)
    entry.bind('<FocusIn>',refresh,add='+');entry.bind('<FocusOut>',refresh,add='+');entry.bind('<KeyRelease>',refresh,add='+')
