"""Offline production library interaction check, including the frozen executable."""
import json
import os
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
from core import Settings, Task, VERSION
from engine import Engine
from library_ui import LibraryWindow
import chapter_updates


def run(directory):
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["JM_BATCH_HOME"] = str(directory / "home")
    root = tk.Tk()
    engine = Engine(directory / "home")
    settings = Settings(output=str(directory / "out"))
    catalog = [dict(id=str(800001+i), number=i+1, title=f"Chapter {i+1}") for i in range(3)]
    old = Task("123456", settings.__dict__, status="done", result=str(directory / "old.zip"),
               chapter_options=catalog[:2], selected_chapters=catalog[:2])
    engine.tasks.append(old)
    engine.library.sync(engine.tasks)
    app = SimpleNamespace(root=root, engine=engine, current_settings=lambda: settings, render=lambda: None)
    window = LibraryWindow(app)
    original = chapter_updates.fetch_catalog
    checks = []
    answers = []
    class Messages:
        accept = False
        def askyesno(self, *args, **kwargs):
            answers.append(args);return self.accept
        def showinfo(self, *args, **kwargs):
            answers.append(args)
        def showerror(self, *args, **kwargs):
            raise AssertionError(args)
    messages = Messages()
    window.messagebox = messages
    def check():
        window.action_buttons["updates"].invoke()
        end = time.monotonic()+10
        while window.busy and time.monotonic()<end:
            root.update();time.sleep(.01)
        assert not window.busy
    try:
        root.update()
        key = engine.library.key(old.result)
        window.enter_batch(key)
        root.update()
        assert str(window.action_buttons["updates"]["state"]) == "normal"
        chapter_updates.fetch_catalog = lambda *args: catalog
        check()
        assert len(engine.tasks) == 1 and "发现 1" in answers[-1][1]
        checks.append("Library button checks metadata and decline creates no download")
        check()
        assert "发现 1" in answers[-1][1]
        checks.append("Declined updates remain available")
        messages.accept = True
        check()
        assert len(engine.tasks) == 2 and engine.tasks[-1].selected_chapters == catalog[2:]
        assert engine.running and engine.tasks[-1].settings == settings.__dict__
        checks.append("Confirmation creates one normal queued task with current settings")
        engine.tasks[-1].status = "done"
        engine.tasks[-1].result = str(directory / "new.zip")
        engine.library.sync(engine.tasks)
        check()
        assert "暂无新章节" in answers[-1][1]
        checks.append("Successful download persists known IDs and suppresses repeat updates")
        data = dict(ok=True, version=VERSION, checks=checks, network_used=False)
        (directory / "self-test.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(data, ensure_ascii=False))
    finally:
        chapter_updates.fetch_catalog = original
        window.close()
        root.destroy()
