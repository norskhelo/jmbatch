"""Offline end-to-end picker check, also run from the frozen application."""
import time
from pathlib import Path
from unittest.mock import patch
from core import Settings, task_cache
from engine import Engine
from chapter_ui import poll_chapters

def check_chapter_ui(app, directory):
    from diagnostics import fixture_worker
    previous = app.engine
    engine = Engine(directory / 'chapter-state', worker_target=fixture_worker)
    app.engine = engine
    def wait(predicate):
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            engine.tick(); app.root.update(); poll_chapters(app)
            if predicate(): return
            time.sleep(.05)
        raise AssertionError([(t.status,t.error) for t in engine.tasks])
    def controls(widget):
        for child in widget.winfo_children():
            yield child
            yield from controls(child)
    try:
        for fmt in ('pdf','zip','images'):
            engine.add(['123456'],Settings(output=str(directory/'chapter-output'),format=fmt,concurrent_tasks=3))
        engine.start()
        wait(lambda: all(t.status=='selecting' for t in engine.tasks))
        assert not engine.active
        assert all(not (task_cache(t.to_dict())/'images').exists() for t in engine.tasks)
        picker=app.chapter_picker
        picker.window.geometry('520x340');app.root.update()
        for button in controls(picker.window):
            if button.winfo_class()=='TButton':
                assert button.winfo_rootx()+button.winfo_width() <= picker.window.winfo_rootx()+picker.window.winfo_width()
                assert button.winfo_rooty()+button.winfo_height() <= picker.window.winfo_rooty()+picker.window.winfo_height()
        picker.list.selection_clear(0,'end')
        with patch('chapter_ui.messagebox.showerror') as error:
            picker.confirm();assert error.called and picker.task.status=='selecting'
        picker.postpone();assert engine.tasks[0].status=='paused'
        engine.start();poll_chapters(app)
        for _ in range(3):
            wait(lambda: getattr(app,'chapter_picker',None) and app.chapter_picker.window.winfo_exists())
            picker=app.chapter_picker
            picker.list.selection_clear(0,'end');picker.list.selection_set(1)
            next(w for w in controls(picker.window) if w.winfo_class()=='TButton' and w.cget('text')=='下载所选章节').invoke()
        wait(lambda: all(t.status=='done' for t in engine.tasks))
        assert all(t.total==2 and t.selected_chapters[0]['number']==2 for t in engine.tasks)
        restored=Engine(engine.home)
        assert all(t.selected_chapters==engine.tasks[i].selected_chapters for i,t in enumerate(restored.tasks))
        app.settings_dialog();app.root.update()
        settings=next(w for w in app.root.winfo_children() if w.winfo_class()=='Toplevel' and w.title()=='下载设置')
        toggle=next(w for w in controls(settings) if w.winfo_class()=='TCheckbutton' and '默认下载全章节' in w.cget('text'))
        toggle.invoke()
        next(w for w in controls(settings) if w.winfo_class()=='TButton' and w.cget('text')=='保存设置').invoke()
        assert Engine(engine.home).settings.download_all_chapters
    finally:
        engine.close()
        picker=getattr(app,'chapter_picker',None)
        if picker and picker.window.winfo_exists():picker.window.destroy()
        app.engine=previous
