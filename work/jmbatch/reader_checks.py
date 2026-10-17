"""Real Tk integration checks for cold, failed and repeated page transitions."""
import threading
import time
from unittest.mock import patch


def check_scroll(reader, root, wait):
    """Check actual Tk image edges across sizes and the fixture's chapter boundary."""
    seams = []
    for geometry in ('1000x820', '740x520'):
        reader.window.geometry(geometry)
        root.update()
        wait(lambda: reader.resize_timer is None)
        for first in (0, 2, 3):
            reader.go(first)
            wait(lambda: first in reader.images and first + 1 in reader.images)
            reader.draw()
            items = {reader.canvas.itemcget(item, 'image'): item
                     for item in reader.canvas.find_withtag('scroll')
                     if reader.canvas.type(item) == 'image'}
            above = reader.canvas.bbox(items[str(reader.images[first])])
            below = reader.canvas.bbox(items[str(reader.images[first + 1])])
            assert above[3] == below[1], (geometry, first, above, below)
            assert reader.heights[first] == reader.images[first].height()
            assert not any(reader.canvas.itemcget(item, 'text').startswith('第 ')
                           for item in reader.canvas.find_withtag('scroll')
                           if reader.canvas.type(item) == 'text')
            seams.append(dict(geometry=geometry, page=first + 1, gap=below[1] - above[3]))
    return seams


def check_paging(reader, root, wait):
    from reader import ReaderSource
    # Exercise 100 complete transitions without rebuilding the canvas items.
    elapsed = []
    for i in range(100):
        target = (reader.current + 1) % len(reader.pages)
        old = reader.pager.photo
        started = time.monotonic()
        reader.go(target)
        assert reader.pager.photo is old
        wait(lambda: reader.current == target)
        elapsed.append(round((time.monotonic() - started) * 1000, 2))
        assert len(reader.canvas.find_all()) == 3
        assert sum(p.width() * p.height() * 4 for p in reader.images.values()) <= 32 * 1024 * 1024
    wait(lambda: not reader.pending)
    target = (reader.current + 1) % len(reader.pages)
    reader.images.pop(target, None)
    entered, release = threading.Event(), threading.Event()
    original = ReaderSource.render
    def slow(source, index, width, height=0):
        if index == target:
            entered.set()
            if not release.wait(5): raise RuntimeError('test gate timed out')
        return original(source, index, width, height)
    old_page, old_photo = reader.current, reader.pager.photo
    with patch.object(ReaderSource, 'render', slow):
        try:
            reader.go(target)
            wait(entered.is_set)
            deadline = time.monotonic() + .25
            while time.monotonic() < deadline:
                root.update(); time.sleep(.005)
                assert reader.current == old_page and reader.pager.photo is old_photo
                assert reader.canvas.itemcget(reader.pager.front, 'image')
        finally:
            release.set()
        wait(lambda: reader.current == target)
    wait(lambda: not reader.pending)
    bad = (reader.current + 1) % len(reader.pages)
    reader.images.pop(bad, None)
    def broken(source, index, width, height=0):
        if index == bad: raise ValueError('isolated unreadable page')
        return original(source, index, width, height)
    old_page, old_photo = reader.current, reader.pager.photo
    with patch.object(ReaderSource, 'render', broken):
        reader.go(bad)
        wait(lambda: bad in reader.errors)
        assert reader.current == old_page and reader.pager.photo is old_photo
        assert str(bad + 1) in reader.canvas.itemcget(reader.pager.notice, 'text')
        reader.go((bad + 1) % len(reader.pages))
        wait(lambda: reader.current == (bad + 1) % len(reader.pages))
    reader.errors.pop(bad, None)
    reader.go(3); wait(lambda: reader.current == 3)
    return dict(transitions=100, cold_hold_ms=250, failure_retains_display=True,
                canvas_items=3, cache_budget_bytes=32*1024*1024,
                transition_ms=elapsed, measured='Tk event-loop completion including intentional animation; not frame-time or Android data')
