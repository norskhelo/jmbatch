"""Persistent two-image canvas pager; all methods run on the Tk UI thread."""
import time


class CanvasPager:
    def __init__(self, canvas, host, lookup, requested, committed):
        self.canvas, self.host = canvas, host
        self.lookup, self.requested, self.committed = lookup, requested, committed
        self.front = canvas.create_image(0, 0, anchor='center', state='hidden')
        self.back = canvas.create_image(0, 0, anchor='center', state='hidden')
        self.notice = canvas.create_text(0, 0, fill='white', anchor='s', width=600)
        self.photo = self.next_photo = None
        self.page = self.target = -1
        self.total = 0
        self.direction = 1
        self.timer = self.loading_timer = None
        self.drag = None
        self.dx = 0
        self.animating = False
        self.enabled = True
        self.closed = False

    def place(self, offset=0, incoming=None):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.dx = offset
        self.canvas.coords(self.front, width / 2 + offset, height / 2)
        if incoming is not None:
            self.canvas.coords(self.back, width / 2 + incoming, height / 2)
        self.canvas.coords(self.notice, width / 2, height - 12)

    def cancel(self):
        if self.timer:
            self.host.after_cancel(self.timer)
        self.timer = None
        self.animating = False
        self.next_photo = None
        self.canvas.itemconfigure(self.back, image='', state='hidden')
        self.place()

    def activate(self, total, target):
        self.enabled, self.total = True, total
        self.cancel()
        self.canvas.itemconfigure(self.front, state='normal' if self.photo else 'hidden')
        self.canvas.itemconfigure(self.notice, state='normal')
        self.go(target, animate=False)

    def hide(self):
        self.enabled = False
        self.cancel()
        if self.loading_timer:
            self.host.after_cancel(self.loading_timer)
            self.loading_timer = None
        for item in (self.front, self.back):
            self.canvas.itemconfigure(item, image='', state='hidden')
        self.canvas.itemconfigure(self.notice, state='hidden')
        self.photo = None
        self.page = self.target = -1

    def go(self, target, animate=True):
        if self.closed or not self.enabled or not self.total:
            return
        target = max(0, min(self.total - 1, target))
        self.cancel()
        self.drag = None
        if target != self.target:
            self.direction = 1 if target > self.target else -1
        self.target = target
        self.canvas.itemconfigure(self.notice, text='')
        if self.loading_timer:
            self.host.after_cancel(self.loading_timer)
        def loading():
            self.loading_timer = None
            if self.enabled and self.lookup(self.target) is None:
                self.canvas.itemconfigure(self.notice, text=f'正在加载第 {self.target + 1} 页…')
        self.loading_timer = self.host.after(180, loading)
        self.ready(animate)
        self.requested()

    def ready(self, animate=True):
        if self.closed or not self.enabled or self.drag or self.animating:
            return
        photo = self.lookup(self.target)
        if photo is None:
            return
        if self.loading_timer:
            self.host.after_cancel(self.loading_timer)
            self.loading_timer = None
        self.canvas.itemconfigure(self.notice, text='')
        if photo is self.photo and self.page == self.target:
            return
        if not animate or self.photo is None or self.page == self.target:
            self.photo, self.page = photo, self.target
            self.canvas.itemconfigure(self.front, image=photo, state='normal')
            self.place()
            self.committed(self.page)
        else:
            self.next_photo = photo
            self.canvas.itemconfigure(self.back, image=photo, state='normal')
            direction = 1 if self.target > self.page else -1
            self.settle(direction, commit=True)

    def settle(self, direction, commit):
        width = self.canvas.winfo_width()
        start = self.dx
        end = -direction * width if commit else 0
        started = time.monotonic()
        duration = max(.06, .16 * abs(end - start) / max(1, width))
        target = self.target
        self.animating = True
        def frame():
            self.timer = None
            if self.closed or not self.enabled:
                return
            fraction = min(1, (time.monotonic() - started) / duration)
            offset = start + (end - start) * (1 - (1 - fraction) ** 3)
            self.place(offset, offset + direction * width)
            if fraction < 1:
                self.timer = self.host.after(16, frame)
                return
            self.animating = False
            if commit:
                self.front, self.back = self.back, self.front
                self.photo, self.next_photo = self.next_photo, None
                self.page = target
            self.canvas.itemconfigure(self.back, image='', state='hidden')
            self.place()
            if commit:
                self.committed(self.page)
            self.ready()
            self.requested()
        frame()

    def press(self, event):
        if not self.enabled or self.page < 0:
            return
        self.cancel()
        self.target = self.page
        self.drag = (event.x, event.y, time.monotonic(), False)
        self.requested()

    def move(self, event):
        if not self.drag:
            return
        x, y, started, moved = self.drag
        dx, dy = event.x - x, event.y - y
        if not moved and (abs(dx) < 8 or abs(dx) <= abs(dy)):
            return
        self.drag = (x, y, started, True)
        direction = 1 if dx < 0 else -1
        photo = self.lookup(self.page + direction)
        self.next_photo = photo
        self.canvas.itemconfigure(self.back, image=photo or '', state='normal' if photo else 'hidden')
        width = self.canvas.winfo_width()
        offset = max(-width, min(width, dx)) if photo else max(-width * .12, min(width * .12, dx * .22))
        self.place(offset, offset + direction * width)

    def release(self, event):
        if not self.drag:
            return
        x, y, started, moved = self.drag
        self.drag = None
        if not moved:
            self.ready()
            return
        dx = event.x - x
        direction = 1 if dx < 0 else -1
        velocity = abs(dx) / max(.01, time.monotonic() - started)
        commit = abs(dx) > self.canvas.winfo_width() * .22 or (abs(dx) > 35 and velocity > 550)
        target = max(0, min(self.total - 1, self.page + direction))
        self.target = target if commit else self.page
        self.direction = direction
        if commit and target != self.page and self.next_photo:
            self.settle(direction, True)
        else:
            self.settle(direction, False)
        self.requested()

    def error(self, text):
        if self.loading_timer:
            self.host.after_cancel(self.loading_timer)
            self.loading_timer = None
        self.canvas.itemconfigure(self.notice, text=f'第 {self.target + 1} 页读取失败，可继续翻页：{text}')

    def close(self):
        self.closed = True
        self.hide()
