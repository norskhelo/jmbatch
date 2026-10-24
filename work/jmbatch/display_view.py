"""A shared Treeview model with a virtual, responsive cover-tile presentation."""
import json
import math
import time
import tkinter as tk
from tkinter import ttk, font
from PIL import ImageTk
from covers import fit_cover
from core import atomic_json
from ui_selection import SelectionEffects


def load_mode(home, key):
    try:
        data = json.loads((home / 'display.json').read_text(encoding='utf-8'))
        return 'tiles' if data.get(key) == 'tiles' else 'list'
    except (OSError, ValueError, AttributeError):
        return 'list'


def save_mode(home, key, mode):
    try:
        data = json.loads((home / 'display.json').read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[key] = mode
    atomic_json(home / 'display.json', data)


def mode_buttons(parent, variable, command):
    bar = ttk.Frame(parent)
    ttk.Label(bar, text='显示方式').pack(side='left', padx=(0, 6))
    for value, label in (('list', '列表'), ('tiles', '平铺')):
        ttk.Radiobutton(bar, text=label, value=value, variable=variable,
                        command=command).pack(side='left', padx=3)
    return bar


class _MarqueeTitle(tk.Canvas):
    """A clipped single line; the parent owns timing and card interaction."""
    def __init__(self, parent):
        super().__init__(parent, highlightthickness=0, borderwidth=0, takefocus=False)
        self.text_item = self.create_text(0, 0, anchor='nw', fill='#1d1f26')
        self.signature = None
        self.started = time.monotonic()
        self.overflow = 0
        for sequence in ('<ButtonPress-1>', '<ButtonRelease-1>', '<B1-Motion>',
                         '<MouseWheel>', '<Leave>'):
            self.bind(sequence, lambda event, seq=sequence: self._forward(parent, seq, event))

    def _forward(self, parent, sequence, event):
        options = dict(x=event.x_root-parent.winfo_rootx(),
                       y=event.y_root-parent.winfo_rooty(), state=event.state, time=event.time)
        if sequence == '<MouseWheel>':
            options['delta'] = event.delta
        parent.event_generate(sequence, **options)
        return 'break'

    def show(self, text, width, text_font, background):
        text = ' '.join(str(text).splitlines()).replace('\t', ' ')
        width = max(1, int(width))
        signature = (text, width, tuple(sorted(text_font.actual().items())))
        self.configure(width=width, height=text_font.metrics('linespace'), background=background)
        if signature != self.signature:
            self.signature = signature
            self.itemconfigure(self.text_item, text=text, font=text_font)
            self.overflow = max(0, text_font.measure(text)+2-width)
            self.started = time.monotonic()
        self.animate(time.monotonic())

    def animate(self, now):
        # Pause at both ends so the beginning and final characters are readable.
        distance = self.overflow
        duration = distance/30 if distance else 0
        phase = (now-self.started) % (duration+2)
        offset = min(distance, max(0, (phase-1)*30)) if distance else 0
        self.coords(self.text_item, 1-offset, 0)


class DisplayView(ttk.Treeview):
    """Selection, order and images stay in one Treeview when presentation changes.

    Only visible cards and clipped title viewports are created. Existing list
    gestures are also forwarded from the title viewports to the tile canvas.
    """
    def __init__(self, master, *, kind, **kwargs):
        super().__init__(master, **kwargs)
        self.kind, self.mode = kind, 'list'
        self.canvas = tk.Canvas(master, background='#ffffff', highlightthickness=0,
                                takefocus=True, yscrollincrement=1)
        self.columns, self.cell_width, self.cell_height = 1, 210, 238 if kind == 'library' else 270
        self.paint_timer = None
        self.marquee_timer = None
        self.title_views = {}
        self.tile_images = {}
        self.selecting = False
        self.selection_effects = SelectionEffects()
        self.extent = None
        self.scroll_callback = None
        self.tile_font = font.Font(self, family='Microsoft YaHei UI', size=10 if kind == 'library' else 11)
        self.number_font = font.Font(self, family='Microsoft YaHei UI', size=9)
        self.canvas.configure(yscrollcommand=self._scrolled)
        self.canvas.bind('<Configure>', self._resize)
        self.canvas.bind('<Map>', lambda event: self._schedule())
        self.canvas.bind('<Unmap>', lambda event: self._stop_marquee())
        self.canvas.bind('<MouseWheel>', self._wheel)
        self.canvas.bind('<ButtonPress-1>', self._select_tile)
        for key, step in (('Left', -1), ('Right', 1), ('Up', -1), ('Down', 1)):
            self.canvas.bind('<'+key+'>', lambda e, k=key, s=step: self._navigate(k, s))
        super().bind('<<TreeviewSelect>>', lambda e: self._schedule(), add='+')
        super().bind('<Destroy>', self._destroy, add='+')

    def bind(self, sequence=None, func=None, add=None):
        result = super().bind(sequence, func, add)
        if hasattr(self, 'canvas') and sequence and sequence not in ('<Destroy>', '<<TreeviewSelect>>'):
            self.canvas.bind(sequence, func, add)
        return result

    def configure(self, cnf=None, **kw):
        if 'yscrollcommand' in kw and hasattr(self, 'canvas'):
            self.scroll_callback = kw['yscrollcommand']
            kw['yscrollcommand'] = self._list_scrolled
        return super().configure(cnf, **kw)

    def _list_scrolled(self, first, last):
        if self.mode == 'list' and callable(self.scroll_callback):
            self.scroll_callback(first, last)

    def _destroy(self, event):
        if event.widget == self:
            if self.paint_timer:
                self.after_cancel(self.paint_timer)
            self._clear_titles()
            self.canvas.destroy()
            self.tile_images.clear()

    def set_mode(self, mode):
        mode = 'tiles' if mode == 'tiles' else 'list'
        if mode == self.mode:
            return
        position = self.item_position()
        active = self.canvas if self.mode == 'tiles' else self
        placement = active.pack_info()
        active.pack_forget()
        self.mode = mode
        if mode == 'list':
            self._clear_titles()
            self.canvas.delete('all')
            self.tile_images.clear()
        (self.canvas if mode == 'tiles' else self).pack(**placement)
        self.update_idletasks()
        if mode == 'tiles':
            self._resize()
        self.move_to_index(position)
        self._schedule()

    def _schedule(self):
        if self.mode == 'tiles' and self.paint_timer is None:
            self.paint_timer = self.after_idle(self._paint)

    def _stop_marquee(self):
        if self.marquee_timer is not None:
            self.after_cancel(self.marquee_timer)
            self.marquee_timer = None

    def _clear_titles(self):
        self._stop_marquee()
        for title in self.title_views.values():
            title.destroy()
        self.title_views.clear()

    def _animate_titles(self):
        self.marquee_timer = None
        if self.mode != 'tiles' or not self.canvas.winfo_ismapped():
            return
        active = [title for title in self.title_views.values() if title.overflow]
        now = time.monotonic()
        for title in active:
            title.animate(now)
        if active:
            self.marquee_timer = self.after(33, self._animate_titles)

    def _scrolled(self, first, last):
        if self.mode == 'tiles' and callable(self.scroll_callback):
            self.scroll_callback(first, last)
        self._schedule()

    def _resize(self, event=None):
        position = self.item_position()
        width = max(1, self.canvas.winfo_width())
        self.columns = 4
        self.cell_width = width / self.columns
        if self.kind == 'library':
            self.cover_width = max(1, int(self.cell_width-22))
            self.cover_height = max(1, round(self.cover_width*4/3))
            self.cell_height = self.cover_height + self.tile_font.metrics('linespace') + self.number_font.metrics('linespace') + 32
        self._extent()
        self.move_to_index(position)
        self._schedule()

    def _extent(self):
        height = math.ceil(len(self.get_children()) / self.columns) * self.cell_height
        extent = (0, 0, max(1, self.canvas.winfo_width()), max(1, height))
        if extent != self.extent:
            self.extent = extent
            self.canvas.configure(scrollregion=extent)

    def item_position(self):
        if self.mode == 'tiles':
            row = max(0, self.canvas.canvasy(0) / self.cell_height)
            return int(row) * self.columns + row - int(row)
        return super().yview()[0] * len(self.get_children())

    def move_to_index(self, position):
        count = len(self.get_children())
        if self.mode == 'tiles':
            rows = max(1, math.ceil(count / self.columns))
            self.canvas.yview_moveto((int(position) // self.columns) / rows)
        else:
            super().yview_moveto(position / max(1, count))

    def yview(self, *args):
        if self.mode == 'tiles':
            if len(args) == 3 and args[0] == 'scroll' and args[2] == 'units':
                args = ('scroll', int(args[1])*36, 'units')
            return self.canvas.yview(*args)
        return super().yview(*args)

    def yview_moveto(self, fraction):
        return self.yview('moveto', fraction)

    def yview_scroll(self, number, what):
        return self.yview('scroll', number, what)

    def _wheel(self, event):
        self.yview_scroll(-int(event.delta / 120) or (-1 if event.delta > 0 else 1), 'units')
        # Let additional gesture bindings cancel a pending long press.

    def identify_at(self, x, y):
        if self.mode == 'list':
            return super().identify_row(y)
        col = int(x / self.cell_width)
        if not 0 <= col < self.columns or y < 0:
            return ''
        index = int(self.canvas.canvasy(y) // self.cell_height) * self.columns + col
        keys = self.get_children()
        return keys[index] if 0 <= index < len(keys) else ''

    def identify_region(self, x, y):
        if self.mode == 'tiles':
            return 'cell' if self.identify_at(x, y) else 'nothing'
        return super().identify_region(x, y)

    def visible_keys(self):
        if self.mode == 'list':
            return list(dict.fromkeys(super(DisplayView, self).identify_row(y)
                        for y in range(0, self.winfo_height(), 20)))
        first = max(0, int(self.canvas.canvasy(0) // self.cell_height)) * self.columns
        last = (int(self.canvas.canvasy(self.canvas.winfo_height()) // self.cell_height)+1)*self.columns
        return self.get_children()[first:last]

    def bbox(self, item, column=None):
        if self.mode == 'list':
            return super().bbox(item, column)
        keys = self.get_children()
        if item not in keys:
            return ()
        n = keys.index(item)
        return (int(n % self.columns*self.cell_width), int(n//self.columns*self.cell_height-self.canvas.canvasy(0)),
                int(self.cell_width), self.cell_height)

    def see(self, item):
        if self.mode == 'list':
            return super().see(item)
        box = self.bbox(item)
        if box and (box[1] < 0 or box[1]+box[3] > self.canvas.winfo_height()):
            self.move_to_index(self.get_children().index(item))

    def focus_set(self):
        return self.canvas.focus_set() if self.mode == 'tiles' else super().focus_set()

    def focus(self, item=None):
        result = super().focus(item)
        if item is not None:
            self._schedule()
        return result

    def _selection(self, operation, items):
        result = super()._selection(operation, items)
        self._schedule()
        return result

    def event_generate(self, sequence, **kw):
        if self.mode == 'tiles' and not sequence.startswith('<<'):
            return self.canvas.event_generate(sequence, **kw)
        return super().event_generate(sequence, **kw)

    def _select_tile(self, event):
        key = self.identify_at(event.x, event.y)
        self.focus_set()
        if not key or str(self['selectmode']) == 'none':
            return
        keys = self.get_children()
        if event.state & 1 and self.focus():
            a, b = sorted((keys.index(self.focus()), keys.index(key)))
            self.selection_set(keys[a:b+1])
        elif event.state & 4:
            self.selection_toggle(key)
        else:
            self.selection_set(key)
        self.focus(key)
        self._schedule()

    def _navigate(self, key, step):
        keys = self.get_children()
        if keys:
            current = keys.index(self.focus()) if self.focus() in keys else 0
            index = min(len(keys)-1, max(0, current+step*(self.columns if key in ('Up','Down') else 1)))
            self.focus(keys[index])
            if str(self['selectmode']) != 'none':
                self.selection_set(keys[index])
            self.see(keys[index])
            self._schedule()
        return 'break'

    def item(self, item, option=None, **kw):
        result = super().item(item, option, **kw)
        if kw:
            self._schedule()
        return result

    def insert(self, parent, index, iid=None, **kw):
        result = super().insert(parent, index, iid, **kw)
        self._schedule()
        return result

    def delete(self, *items):
        result = super().delete(*items)
        self._schedule()
        return result

    def move(self, item, parent, index):
        super().move(item, parent, index)
        self._schedule()

    def _lines(self, text, width, maximum):
        lines, line = [], ''
        for character in str(text):
            if character == '\n' or self.tile_font.measure(line+character) > width:
                lines.append(line)
                line = '' if character == '\n' else character
            else:
                line += character
        lines.append(line)
        if len(lines) > maximum:
            lines = lines[:maximum]
            while lines[-1] and self.tile_font.measure(lines[-1]+'…') > width:
                lines[-1] = lines[-1][:-1]
            lines[-1] += '…'
        return '\n'.join(lines)

    def _paint(self):
        self.paint_timer = None
        if self.mode != 'tiles':
            return
        if self.kind == 'library' and not hasattr(self, 'cover_width'):
            self._resize()
            return
        self._extent()
        self.canvas.delete('all')
        keys = self.get_children()
        selected = set(self.selection())
        self.selection_effects.begin(self.selecting)
        painted_images = {}
        visible = self.visible_keys()
        for key in tuple(self.title_views):
            if key not in visible:
                self.title_views.pop(key).destroy()
        for key in visible:
            n = keys.index(key)
            x, y = (n % self.columns)*self.cell_width+5, (n//self.columns)*self.cell_height+5
            width = self.cell_width-10
            chosen = key in selected
            highlighted = chosen and self.kind != 'library'
            __import__('ui_common').rounded(self.canvas,x,y,width,self.cell_height-10,8,fill='#eeeef1' if highlighted else 'white',
                outline='#73757c' if highlighted else '#dadce1', width=2 if highlighted else 1)
            data = super().item(key)
            picture = data['image']
            if self.kind == 'library':
                self.canvas.create_rectangle(x+6,y+6,x+6+self.cover_width,y+6+self.cover_height,
                                             fill='#e8edf1',outline='')
                if picture:
                    cache_key = (picture[0], self.cover_width, self.cover_height)
                    photo = painted_images.get(cache_key) or self.tile_images.get(cache_key)
                    if photo is None:
                        # Copy the existing local thumbnail; keep the list image unchanged.
                        source = tk.PhotoImage(master=self)
                        self.tk.call(str(source), 'copy', picture[0])
                        image = fit_cover(ImageTk.getimage(source), (self.cover_width, self.cover_height))
                        photo = ImageTk.PhotoImage(image, master=self)
                    painted_images[cache_key] = photo
                    self.canvas.create_image(x+6+self.cover_width/2,y+6+self.cover_height/2,image=photo)
            elif picture:
                self.canvas.create_image(x+width/2,y+58,image=picture[0])
            values = [str(v) for v in data['values']]
            if self.kind == 'library':
                favorite, number, title, fmt = values
                subtitle = '' if fmt == '收藏夹' else number
                if favorite:
                    self.canvas.create_text(x+width-(38 if self.selecting and fmt != '收藏夹' else 16),y+12,anchor='ne',text='★',fill='#d6a039',font=('Segoe UI',22))
            else:
                number,title,status,progress,size,fmt,resets = values
                text = self._lines(title or number,width-20,2)+'\n'+self._lines(f'{number} · {fmt}',width-20,1)
                text += '\n'+status+'\n'+self._lines(progress,width-20,1)+'\n'+self._lines(size,width-20,1)
            text_top = self.cover_height+12 if self.kind == 'library' else 115
            if self.kind == 'library':
                if key not in self.title_views:
                    self.title_views[key] = _MarqueeTitle(self.canvas)
                viewport = self.title_views[key]
                viewport.show(title, width-12, self.tile_font, 'white')
                self.canvas.create_window(x+6,y+text_top,anchor='nw',window=viewport)
                self.canvas.create_text(x+6,y+text_top+self.tile_font.metrics('linespace')+3,anchor='nw',text=self._lines(subtitle,width-12,1),font=self.number_font,fill='#747780')
            else:
                self.canvas.create_text(x+10,y+text_top,anchor='nw',text=text,font=self.tile_font,fill='#1d1f26')
            if self.kind == 'library' and self.selecting and fmt != '收藏夹':
                self.selection_effects.draw(self.canvas,key,x+width-30,y+10,chosen)
            elif chosen and self.kind != 'library':
                self.canvas.create_text(x+width-10,y+8,anchor='ne',text='✓',fill='#73757c',font=self.tile_font)
        self.tile_images = painted_images
        if self.selection_effects.end() and self.paint_timer is None:
            self.paint_timer = self.after(16, self._paint)
        if self.marquee_timer is None:
            self._animate_titles()
