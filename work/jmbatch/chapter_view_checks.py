"""Offline real-Tk chapter viewing checks, also runnable in the frozen build."""
import json
import os
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from pathlib import Path
from PIL import Image
from core import Settings, VERSION
from engine import Engine
from reader import ReaderState
from reader_ui import ReaderWindow


def run(directory):
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["JM_BATCH_HOME"] = str(directory / "home")
    root = tk.Tk()
    root.geometry("1000x820")
    checks = []
    # Keep closed Tk owners alive until all synthetic reader work has finished.
    readers = []
    app = SimpleNamespace(root=root, home=directory / "home", readers={})
    app.engine = Engine(app.home)

    def wait(predicate):
        deadline = time.monotonic() + 12
        while not predicate() and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert predicate(), "Reader timed out"

    def open_reader(key):
        reader = ReaderWindow(app, key)
        readers.append(reader)
        app.readers[key] = reader
        wait(lambda: reader.scope_end > 0 and bool(reader.images))
        wait(lambda: reader.resize_timer is None)
        return reader

    try:
        assert Settings().chapter_view_mode == 1
        for invalid in (0, 3, "2"):
            try:
                Settings(chapter_view_mode=invalid).validate()
                raise AssertionError("Invalid mode accepted")
            except ValueError:
                pass
        # Exercise the production settings dialog, including actual disk reload.
        from app import App
        app.current_settings = lambda: app.engine.settings
        app.log = lambda value: None
        App.settings_dialog(app)
        dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
        frame = dialog.winfo_children()[0]
        combo = next(w for w in frame.winfo_children() if isinstance(w, ttk.Combobox))
        assert combo.get() == "1 多章节合一"
        combo.current(1)
        next(w for w in frame.winfo_children() if isinstance(w, ttk.Button) and w.cget("text") == "保存设置").invoke()
        assert Engine(app.home).settings.chapter_view_mode == 2
        checks.append("Legacy default, validation, settings UI and persistent selection")
        folder = directory / "JM123-chapters-1234abcd"
        entries = []
        for chapter, count in ((2, 3), (5, 2), (9, 1)):
            target = folder / f"{chapter:04d}"
            target.mkdir(parents=True, exist_ok=True)
            for page in range(count):
                image = target / f"{page+1:05d}.jpg"
                Image.new("RGB", (400, 700), (chapter * 20, page * 40, 80)).save(image)
                entries.append(dict(chapter=chapter, page=page+1, file=image.relative_to(folder).as_posix(), size=image.stat().st_size))
        (folder / ".jmbatch-album.json").write_text(json.dumps(dict(version=2, id="123", title="Synthetic", entries=entries)), encoding="utf-8")
        from albums import export_album
        archive = export_album(folder, directory / "zip", "zip")[0]
        pdf = export_album(folder, directory / "pdf", "pdf")[0]
        for source, fmt in ((folder, "images"), (archive, "zip"), (pdf, "pdf")):
            key = app.engine.library.key(source)
            app.engine.library.import_found([dict(id="123", title="Synthetic chapters", path=str(source),
                root=str(source.parent), format=fmt, favorite=False, added=0)])
            state = ReaderState(app.home)
            state.put(key, 4, "scroll", [0, 4, 5])
            app.reader_state = state
            reader = open_reader(key)
            expected = (0, 6) if fmt == "pdf" else (3, 5)
            assert (reader.scope_start, reader.scope_end) == expected
            assert reader.current == 4 and reader.marks == {0, 4, 5}
            for mode in ("滚动阅读", "左右翻页"):
                reader.mode.set(mode)
                reader.relayout()
                reader.go(expected[0])
                wait(lambda: reader.current == expected[0])
                reader.step(-1)
                root.update()
                assert reader.current == expected[0]
                reader.go(expected[1] - 1)
                wait(lambda: reader.current == expected[1] - 1)
                reader.step(1)
                root.update()
                assert reader.current == expected[1] - 1
                if mode == "左右翻页":
                    reader.pager.go(999)
                    assert reader.pager.target == expected[1] - 1
                    reader.pager.go(-1)
                    wait(lambda: reader.current == expected[0])
                else:
                    reader.canvas.yview_moveto(1)
                    root.update()
                    assert reader.current < expected[1]
                assert all(expected[0] <= i < expected[1] for i in reader.images)
            checks.append(f"{fmt}: restored chapter, scroll/page boundaries and bounded decoding")
            if fmt != "pdf":
                reader.chapter_step(1)
                wait(lambda: reader.current == 5)
                assert (reader.scope_start, reader.scope_end) == (5, 6)
                reader.go(0)  # Same path used by cross-chapter bookmarks.
                wait(lambda: reader.current == 0)
                assert (reader.scope_start, reader.scope_end) == (0, 3)
                reader.jump.set("5")
                reader.jump_page()
                wait(lambda: reader.current == 4)
                assert (reader.scope_start, reader.scope_end) == (3, 5)
                reader.close()
                app.engine.settings.chapter_view_mode = 1
                reader = open_reader(key)
                assert reader.current == 4 and reader.marks == {0, 4, 5}
                assert (reader.scope_start, reader.scope_end) == (0, 6)
                reader.step(1)
                wait(lambda: reader.current == 5)
                checks.append(f"{fmt}: chapter switching, cross-chapter jumps and merged-mode history")
                app.engine.settings.chapter_view_mode = 2
            reader.close()
        result = dict(ok=True, version=VERSION, checks=checks, network_used=False)
        (directory / "self-test.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        for reader in list(app.readers.values()):
            reader.close()
        root.destroy()
