"""Real Tk bookmark jumps with asynchronous decoding; frozen-build compatible."""
import json
import os
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from PIL import Image
from core import VERSION
from engine import Engine
from reader import ReaderState
from reader_ui import ReaderWindow


def run(directory):
    directory.mkdir(parents=True, exist_ok=True)
    os.environ['JM_BATCH_HOME'] = str(directory / 'home')
    root = tk.Tk()
    root.geometry('1000x820')
    readers, checks = [], []
    app = SimpleNamespace(root=root, home=directory / 'home', readers={})
    app.engine = Engine(app.home)

    def settle(reader):
        deadline = time.monotonic() + 12
        stable = None
        while time.monotonic() < deadline:
            root.update()
            if reader.pages and not reader.pending and reader.resize_timer is None and not reader.pager.animating:
                stable = stable or time.monotonic()
                if time.monotonic() - stable > .3:
                    return
            else:
                stable = None
            time.sleep(.01)
        raise AssertionError('Reader did not settle')

    def at(reader, page):
        settle(reader)
        assert reader.current == page, (page, reader.current)
        if reader.is_scroll():
            assert abs(reader.canvas.canvasy(0) - reader.offsets[page]) <= 1, (page, reader.canvas.canvasy(0), reader.offsets[page])
        else:
            assert reader.pager.page == page

    def bookmark(reader, page):
        reader.bookmarks()
        dialog = next(w for w in reader.window.winfo_children() if isinstance(w, tk.Toplevel))
        box = next(w for w in dialog.winfo_children() if isinstance(w, tk.Listbox))
        box.selection_set(sorted(reader.marks).index(page))
        next(w for w in dialog.winfo_children() if isinstance(w, ttk.Button) and w.cget('text') == '跳转').invoke()

    try:
        folder = directory / 'JM123-bookmarks-1234abcd'
        entries = []
        for index in range(61):
            chapter, page = index // 20 + 1, index % 20 + 1
            image = folder / f'{chapter:04d}/{page:05d}.jpg'
            image.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (400, (100, 700, 1400)[index % 3]), (100, index * 3, 80)).save(image)
            entries.append(dict(chapter=chapter, page=page, file=image.relative_to(folder).as_posix(), size=image.stat().st_size))
        (folder / '.jmbatch-album.json').write_text(json.dumps(dict(version=2, id='123', title='Synthetic bookmarks', entries=entries)), encoding='utf-8')
        key = app.engine.library.key(folder)
        app.engine.library.import_found([dict(id='123', title='Synthetic bookmarks', path=str(folder), root=str(folder.parent), format='images', favorite=False, added=0)])
        for split in (False, True):
            app.engine.settings.chapter_view_mode = 2 if split else 1
            state = ReaderState(app.home)
            state.put(key, 0, 'scroll', [3, 40, 58, 60])
            app.reader_state = state
            reader = ReaderWindow(app, key)
            readers.append(reader)
            app.readers[key] = reader
            settle(reader)
            for target in (40, 3, 58, 60, 3):
                bookmark(reader, target)
                at(reader, target)
            checks.append(f'split={split}: one-click cold, backward, near-end and last-page bookmarks')
            reader.go(40); reader.go(3); reader.go(58)
            at(reader, 58)
            reader.mode.set('左右翻页'); reader.relayout()
            bookmark(reader, 40); at(reader, 40)
            reader.mode.set('滚动阅读'); reader.relayout(); at(reader, 40)
            checks.append(f'split={split}: latest jump and mode switch preserve target')
            reader.close()
            reader = ReaderWindow(app, key)
            readers.append(reader); app.readers[key] = reader
            at(reader, 40)
            assert reader.marks == {3, 40, 58, 60}
            reader.close()
        result = dict(ok=True, version=VERSION, checks=checks, network_used=False)
        (directory / 'self-test.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
    finally:
        for reader in list(app.readers.values()):
            reader.close()
        root.destroy()
