"""Reader gestures and clipped, reversible toolbar transitions on the Tk thread."""
import time


class TapGesture:
    def __init__(self, slop=8, timeout=.5):
        self.slop, self.timeout = slop, timeout
        self.start = None

    def down(self, x, y):
        self.start = (x, y, time.monotonic())

    def move(self, x, y):
        if self.start and max(abs(x-self.start[0]), abs(y-self.start[1])) > self.slop:
            self.start = None

    def up(self, x, y):
        self.move(x, y)
        start, self.start = self.start, None
        return start is not None and time.monotonic()-start[2] < self.timeout


class ReaderChrome:
    def __init__(self, host, top, bottom, content, viewport, changed):
        self.host, self.top, self.bottom = host, top, bottom
        self.content, self.changed = content, changed
        self.viewport = viewport
        self.visible = True
        self.fraction = 1.0
        self.timer = None
        self.animating = self.closed = False

    def toggle(self):
        self.show(not self.visible)

    def show(self, visible):
        if self.closed or (self.visible == visible and not self.animating):
            return
        if self.timer:
            self.host.after_cancel(self.timer)
        self.visible = visible
        self.animating = True
        start, end = self.fraction, float(visible)
        started = time.monotonic()
        # Contents keep their natural size while their parent clips the slide.
        heights = [frame.winfo_reqheight() for frame in self.content]
        self.top.pack_propagate(False)
        self.bottom.pack_propagate(False)
        self.top.pack(side='top', fill='x', before=self.viewport)
        self.bottom.pack(side='bottom', fill='x', before=self.viewport)
        for frame in self.content:
            frame.pack_forget()

        def frame():
            self.timer = None
            if self.closed:
                return
            progress = min(1, (time.monotonic()-started)/.22)
            self.fraction = start+(end-start)*(1-(1-progress)**3)
            for index, wrapper in enumerate((self.top, self.bottom)):
                height = heights[index]
                space = round(height*self.fraction)
                wrapper.configure(height=max(1, space))
                self.content[index].place(x=0, y=space-height if index == 0 else 0,
                                          relwidth=1, height=height)
            if progress < 1:
                self.timer = self.host.after(16, frame)
                return
            self.animating = False
            for wrapper, child in zip((self.top, self.bottom), self.content):
                child.place_forget()
                child.pack(fill='x')
                wrapper.pack_propagate(True)
                if not visible:
                    wrapper.pack_forget()
            self.changed()
        frame()

    def close(self):
        self.closed = True
        if self.timer:
            self.host.after_cancel(self.timer)
        self.timer = None
