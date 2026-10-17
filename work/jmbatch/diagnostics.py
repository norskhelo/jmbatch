"""Offline integration diagnostics: generated test pages, no site requests."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

from core import Settings, Task, atomic_json, explain_error
from chapters import ChapterChoiceRequired
from worker import run_download


class FixtureClient:
    def get_album_detail(self, album_id):
        import jmcomic
        return jmcomic.JmAlbumDetail(album_id, "220980", "Offline test pages", [
            ("800001", "1", "Chapter one"), ("800002", "2", "Chapter two")],
            5, "2026-01-01", "2026-01-01", "0", "0", 0, [], [], [], [])

    def check_photo(self, photo):
        count = 3 if photo.sort == 1 else 2
        photo.page_arr = [f"{i:05d}.jpg" for i in range(1, count + 1)]
        photo.data_original_domain = "offline.invalid"

    def download_by_image_detail(self, image, path, decode_image=True):
        from PIL import Image, ImageDraw
        page = Image.new("RGB", (600, 800), "#eff4f6")
        draw = ImageDraw.Draw(page)
        draw.rectangle((30, 30, 570, 120), fill="#087f8c")
        draw.text((50, 60), "JM BATCH / OFFLINE TEST", fill="white", font_size=26)
        draw.text((50, 180), f"Chapter {image.from_photo.sort} / Page {image.index}", fill="#172c3e", font_size=28)
        draw.text((50, 250), "Generated locally. No network requests.", fill="#617387", font_size=18)
        page.save(path, "JPEG", quality=90)


class FailingFixtureClient(FixtureClient):
    def download_by_image_detail(self, image, path, decode_image=True):
        if image.index == 2:
            raise TimeoutError("offline fixture: image request timed out")
        return super().download_by_image_detail(image, path, decode_image)


def fixture_worker(task, cookie, channel):
    try:
        run_download(task, cookie, channel.put, client_factory=FixtureClient)
    except ChapterChoiceRequired as choice:
        channel.put({"type": "chapters", "chapters": choice.chapters})
    except Exception as exc:
        channel.put({"type": "error", "error": explain_error(exc, cookie)})


def stalled_worker(task, cookie, channel):
    channel.put({"type": "phase", "phase": "download", "total": 5, "message": "Offline stalled fixture"})
    time.sleep(120)


def cover_fixture_worker(task, cookie, channel):
    from core import task_cache
    class SlowPages(FixtureClient):
        def download_by_image_detail(self, image, path, decode_image=True):
            if image.from_photo.sort != 1 or image.index != 1:
                deadline = time.monotonic() + 60
                while not (task_cache(task) / "continue-cover-test").exists():
                    if time.monotonic() > deadline:
                        raise TimeoutError("Offline cover fixture was not released")
                    time.sleep(.05)
            super().download_by_image_detail(image, path, decode_image)
    try:
        run_download(task, cookie, channel.put, client_factory=SlowPages)
    except Exception as exc:
        channel.put({"type": "error", "error": explain_error(exc, cookie)})


def check_download_covers_ui(application, directory):
    """Actual queue and child downloads: show covers before allowing remaining pages."""
    from core import task_cache
    from engine import Engine
    old_engine, root = application.engine, application.root
    engine = Engine(directory / "live-cover-state", worker_target=cover_fixture_worker)
    application.engine = engine
    def wait(predicate):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            engine.tick()
            application.render()
            root.update()
            if predicate():
                return
            time.sleep(.05)
        raise AssertionError("Live download cover UI timed out: " + str([t.to_dict() for t in engine.tasks]))
    try:
        for fmt in ("pdf", "zip", "images"):
            engine.add(["123456"], Settings(download_all_chapters=True, output=str(directory / "live-cover-output"), format=fmt, threads=1, concurrent_tasks=3))
        tasks = list(engine.tasks)
        engine.start()
        # At minimum height, scroll to each row while its download remains blocked.
        root.geometry("1020x780")
        for task in tasks:
            wait(lambda: application.tree.exists(task.key))
            application.tree.see(task.key)
            wait(lambda: task.done == 1 and application.download_covers.images.get(task.key, (None, False))[1])
            assert task.status == "running" and task.done < task.total and not task.result
            x, y, width, height = application.tree.bbox(task.key, "#0")
            assert width >= 54 and y + height <= application.tree.winfo_height(), (y, height, application.tree.winfo_height())
            assert application.tree.item(task.key, "image")
        engine.pause()
        for task in tasks:
            assert task.status == "paused"
            assert application.download_covers.images[task.key][1]
            (task_cache(task.to_dict()) / "continue-cover-test").touch()
        engine.start()
        wait(lambda: not engine.running and all(t.status == "done" for t in tasks))
        for task in tasks:
            assert not (task_cache(task.to_dict()) / "images").exists()
            application.tree.see(task.key)
            wait(lambda: application.download_covers.images.get(task.key, (None, False))[1]
                 and application.download_covers.images[task.key][0][1] == task.settings["format"])
        engine.tasks = []
        application.render()
        assert not application.tree.get_children() and not application.download_covers.images
    finally:
        engine.pause()
        application.engine = old_engine
        application.render()


def check_update_history_ui(root, directory):
    """Exercise real announcement widgets before/after a multi-version upgrade."""
    import core
    import tkinter as tk
    from tkinter import ttk
    from types import SimpleNamespace
    from unittest.mock import patch
    from updates import UpdateUI, select_release
    current = core.VERSION
    home = directory / "history-profile"
    home.mkdir(parents=True, exist_ok=True)
    button = ttk.Button(root)
    app = SimpleNamespace(root=root, home=home, update_button=button)
    rows = []
    for number, body in (("0.0.2", "Intermediate upgrade notes"), (current, "Installed upgrade notes")):
        name = f"JMBatch-{number}-Windows-x64.zip"
        rows.append(dict(body=body, assets=[dict(name=name, size=100, state="uploaded",
                        browser_download_url=f"https://github.com/norskhelo/jmbatch/releases/download/test/{name}")]))
    cached = select_release(rows, "norskhelo/jmbatch", "0.0.1", True)
    with patch.object(core, "VERSION", "0.0.1"):
        before = UpdateUI(app)
        before.automatic = False
        before.show()
        before.show_notes()
        popup = before.notes_window
        before.show_notes()
        assert before.notes_window is popup  # Reuse, rather than retain stale duplicate popups.
        root.update()
        before.checked_repo = before.repo
        before.checker = SimpleNamespace(poll=lambda: ("ok", cached))
        before.poll()
        root.update()
        for area in (before.announcement_area, before.notes_area):
            text = area.get("1.0", "end")
            assert all(row["body"] in text for row in rows)
        assert current in before.notes_status_var.get()
        before.seen_path.write_text("0.0.1", encoding="utf-8")
        before.notes_window.destroy()
        before.dialog.destroy()
    # New process/version: migrate the old seen marker and preserve its cached range.
    after = UpdateUI(app)
    after.automatic = False
    assert after.upgrade_from == "0.0.1"
    after.startup()
    root.update()
    text = after.notes_area.get("1.0", "end")
    assert "本次升级" in text and all(row["body"] in text for row in rows)
    assert after.seen_path.read_text(encoding="utf-8") == current
    after.checked_repo = after.repo
    after.checker = SimpleNamespace(poll=lambda: ("ok", cached))
    after.poll()  # A same-version successful recheck must not shrink the range.
    assert all(row["body"] in after.notes_area.get("1.0", "end") for row in rows)
    after.checker = SimpleNamespace(poll=lambda: ("skipped", None))
    after.poll()
    assert "未能取得完整" in after.notes_status_var.get()
    assert all(row["body"] in after.notes_area.get("1.0", "end") for row in rows)
    after.notes_window.destroy()
    after.poll()  # Closing a popup while a check completes must remain safe.
    reopened = UpdateUI(app)
    assert reopened.upgrade_from == "0.0.1"
    reopened.show_notes()
    assert all(row["body"] in reopened.notes_area.get("1.0", "end") for row in rows)
    reopened.notes_window.destroy()
    button.destroy()


def check_manual_update_ui(application, directory):
    """Click real entry points; mock only the public network response."""
    import json
    import threading
    from unittest.mock import patch
    from core import VERSION, atomic_json
    from updates import select_release
    root, ui = application.root, application.updates
    ui.automatic = False
    atomic_json(ui.path, {"repository": ui.repo, "automatic": False, "repository_default_v1": True})
    saved_settings = ui.path.read_bytes()
    ui.seen_path.write_text(VERSION, encoding="utf-8")
    gate = threading.Event()
    calls = []
    name = "JMBatch-9.0.0-Windows-x64.zip"
    answer = select_release([dict(body="manual check full announcement", assets=[dict(
        name=name, size=100, state="uploaded", browser_download_url=
        "https://github.com/norskhelo/jmbatch/releases/download/test/" + name)])], ui.repo, VERSION, True)
    def fetch(repo, current):
        calls.append((repo, current))
        gate.wait(5)
        return answer
    def wait_done():
        deadline = time.monotonic() + 3
        while ui.checking and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert not ui.checking, "Manual update check did not complete"
    try:
        with patch("updates.fetch_bulletin", side_effect=fetch):
            ui.startup()
            assert not calls  # Turning automatic checks off is respected.
            application.update_button.invoke()
            assert ui.checking and ui.dialog.winfo_exists()
            application.update_button.invoke()
            ui.check_button.invoke()
            root.update()
            assert str(ui.check_button["state"]) == "disabled"
            assert ui.check_button["text"] == "检查中…"
            assert "正在后台检查" in ui.status_var.get()
            assert str(ui.download_button["state"]) == "disabled"
            gate.set()
            wait_done()
            assert len(calls) == 1, calls
            assert "9.0.0" in ui.status_var.get()
            assert "manual check full announcement" in ui.announcement_area.get("1.0", "end")
            assert str(ui.download_button["state"]) == "normal"
            assert ui.path.read_bytes() == saved_settings and not ui.automatic
            # Window layout is usable at the app's minimum size.
            application.root.geometry("1020x820")
            root.update()
            for widget, window in ((application.update_button, root), (ui.check_button, ui.dialog)):
                assert widget.winfo_ismapped()
                assert widget.winfo_rootx() + widget.winfo_width() <= window.winfo_rootx() + window.winfo_width()
            ui.show_notes()
            root.update()
            assert ui.notes_check_button.winfo_ismapped()
        with patch("updates.fetch_bulletin", side_effect=OSError("offline")):
            ui.notes_check_button.invoke()
            wait_done()
            assert "保留离线公告" in ui.status and "重试" in ui.status
            assert "manual check full announcement" in ui.notes_area.get("1.0", "end")
            assert str(ui.check_button["state"]) == "normal"
            assert str(ui.download_button["state"]) == "disabled"
        with patch("updates.fetch_bulletin", return_value=None) as network:
            ui.check_button.invoke()
            wait_done()
            assert network.call_count == 1 and "当前已是" in ui.status
            assert str(ui.notes_check_button["state"]) == "normal"
        gate.clear()
        with patch("updates.fetch_bulletin", side_effect=fetch):
            ui.check_button.invoke()
            deadline, channel = ui.checker.pending
            ui.checker.pending = (time.monotonic() - 1, channel)
            wait_done()
            assert "重试" in ui.status and str(ui.check_button["state"]) == "normal"
            ui.check_button.invoke()
            assert "仍在结束中" in ui.status and not ui.checking
            gate.set()
            ui.checker.thread.join(1)
            assert not ui.checker.thread.is_alive()
        with patch("updates.fetch_bulletin", return_value=None):
            ui.check_button.invoke()
            ui.dialog.destroy()
            ui.notes_window.destroy()
            wait_done()
            ui.show()
            assert "当前已是" in ui.status_var.get()
        repo = ui.repo
        ui.repo = ""
        with patch("updates.fetch_bulletin") as network:
            ui.check_button.invoke()
            assert not network.called and "请先填写" in ui.status
        ui.repo = repo
        with patch("updates.fetch_bulletin") as network:
            ui.downloading = True
            application.update_button.invoke()
            assert not network.called
            ui.downloading = False
            ui.ready = object()
            application.update_button.invoke()
            assert not network.called
            ui.ready = None
        assert json.loads(ui.path.read_text(encoding="utf-8"))["automatic"] is False
    finally:
        gate.set()
        ui.downloading, ui.ready = False, None
        if ui.notes_window is not None and ui.notes_window.winfo_exists():
            ui.notes_window.destroy()
        if ui.dialog is not None and ui.dialog.winfo_exists():
            ui.dialog.destroy()


def run_self_test(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    report = {"ok": False, "network_used": False, "checks": []}
    try:
        from engine import Engine, WorkerState
        from pypdf import PdfReader
        import zipfile
        import curl_cffi
        import jmcomic
        from Crypto.Cipher import AES
        with curl_cffi.requests.Session() as session:
            assert session is not None
        assert AES.new(b"0" * 16, AES.MODE_ECB).encrypt(b"0" * 16)
        report["checks"].append("native HTTP session and AES initialized without network")
        from chapter_metadata_checks import check_metadata_resume
        check_metadata_resume(directory / 'chapter-metadata')
        report["checks"].append("Bounded chapter metadata: four workers, persisted records, restart reuses all 12 chapters without detail requests")
        check_metadata_resume(directory / 'chapter-metadata-eight', workers=8)
        report["checks"].append("Configurable chapter metadata: eight workers, bounded requests and restart cache reuse")
        from network_routes import run_routes, RoutesExhausted
        route_calls = []
        def simulated_connection(host):
            route_calls.append(host)
            if host == "bad.example":
                raise ConnectionError("Failed to connect to bad.example/[::]:443 cookie=PRIVATE")
            return "connected"
        assert run_routes(["bad.example", "good.example"], 2, "接口", simulated_connection) == "connected"
        assert route_calls == ["bad.example", "good.example"]
        try:
            run_routes(["bad.example"], 2, "接口", simulated_connection)
            raise AssertionError("Expected routes exhausted")
        except RoutesExhausted as error:
            assert "未指定地址" in str(error) and "PRIVATE" not in str(error)
        report["checks"].append("packaged connection failover and redacted diagnostics")
        report["jmcomic"] = jmcomic.__version__
        engine = Engine(directory / "state", worker_target=fixture_worker)
        for fmt in ("pdf", "zip"):
            engine.add(["123456"], Settings(download_all_chapters=True, output=str(directory / "artifacts"), format=fmt))
        engine.start()
        engine.tick()
        assert len(engine.active) == 2, "Two independent workers must overlap"
        report["checks"].append("two concurrent download processes admitted with independent task state")
        deadline = time.monotonic() + 90
        while engine.running and time.monotonic() < deadline:
            engine.tick()
            time.sleep(.1)
        assert not engine.running, "Offline process exceeded 90 seconds"
        assert len(engine.tasks) == 2 and all(t.status == "done" for t in engine.tasks), [t.to_dict() for t in engine.tasks]
        for task in engine.tasks:
            path = Path(task.result)
            assert path.exists(), str(path)
            if path.suffix == ".pdf":
                with path.open("rb") as stream:
                    assert len(PdfReader(stream).pages) == 5
            else:
                with zipfile.ZipFile(path) as archive:
                    assert archive.testzip() is None
                    assert archive.namelist()[:5] == ["0001/00001.jpg", "0001/00002.jpg", "0001/00003.jpg", "0002/00001.jpg", "0002/00002.jpg"]
        report["checks"].extend(["spawn worker + jmcomic hooks", "5-page PDF", "ordered multi-chapter ZIP", "atomic exports", "queue persistence"])
        engine.close()
        # Exercise Tk without a network download or desktop screen capture.
        import tkinter as tk
        from app import App
        root = tk.Tk()
        application = App(root, directory / "gui-state")
        from core import VERSION
        application.updates.automatic = False
        application.updates.seen_path.parent.mkdir(parents=True, exist_ok=True)
        application.updates.seen_path.write_text(VERSION, encoding="utf-8")
        application.engine.tasks = engine.tasks
        application.render()
        root.update()
        assert root.winfo_width() >= 1020
        report["checks"].append("Tk desktop UI constructed and rendered")
        from chapter_checks import check_chapter_ui
        check_chapter_ui(application, directory)
        report["checks"].append("Chapter picker: three real metadata workers release slots; ordered dialogs, empty selection, postpone/resume, second-chapter-only PDF/ZIP/folder, minimum layout and persisted setting")
        check_download_covers_ui(application, directory)
        report["checks"].append("Live queue covers appear before completion in three concurrent real worker downloads at minimum window size")
        report["checks"].append("Paused/resumed queue covers survive image-cache cleanup and load PDF/ZIP/folder results; removed rows release images")
        from core import Task
        display_task = Task("123456", dict(engine.tasks[0].settings), status="running", done=15, total=20,
                            cached=10, image_bytes=1024 ** 2, speed=2 * 1024 ** 2, phase="正在下载图片")
        application.engine.tasks = [display_task]
        display_state = WorkerState(display_task, phase="download", download_started=time.monotonic() - 10)
        application.engine.active[display_task.key] = display_state
        application.render()
        for geometry in ("1160x850", "1020x780"):
            root.geometry(geometry)
            root.update()
            assert "75.0%" in application.tree.set(display_task.key, "progress")
            assert "MB/s" in application.speed_text.get()
            assert "预计完成" in application.progress_text.get() and "预计大小" in application.progress_text.get()
            assert application.tree.winfo_height() >= 70, (geometry, application.tree.winfo_height())
            for widget in (application.progress_label, application.progressbar, application.start_button, application.pause_button):
                assert widget.winfo_ismapped()
                assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width()
                assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height()
        second_task = Task("123457", dict(display_task.settings), status="running", done=2, total=5,
                           image_bytes=1024 ** 2, speed=1024 ** 2, phase="第二本下载中")
        application.engine.tasks.append(second_task)
        application.engine.active[second_task.key] = WorkerState(second_task, phase="download", download_started=time.monotonic() - 20)
        application.render()
        application.tree.selection_set(second_task.key)
        application.render()
        assert "同时下载 2 本" in application.speed_text.get() and "3.0 MB/s" in application.speed_text.get()
        assert "JM123457" in application.progress_text.get() and "40.0%" in application.progress_text.get()
        assert "1.0 MB/s" in application.progress_text.get()
        application.engine.active.pop(second_task.key)
        application.engine.tasks.remove(second_task)
        application.tree.selection_set(display_task.key)
        report["checks"].append("concurrent UI sums speeds and selects each task's own progress and ETA")
        display_task.done = display_task.total
        display_state.phase = "export"
        application.render()
        assert "99.9%" in application.progress_text.get() and "导出" in application.progress_text.get()
        display_task.status = "done"
        display_task.result_bytes = 2 * 1024 ** 2
        application.engine.active.clear()
        application.render()
        assert application.tree.set(display_task.key, "status") == "下载完成"
        assert application.tree.set(display_task.key, "size") == "2.0 MB"
        assert "100.0%" in application.progress_text.get()
        application.engine.tasks = engine.tasks
        application.render()
        root.geometry("1160x850")
        root.update()
        report["checks"].append("Download percentage, ETA, adaptive speed and size rendered at default/minimum sizes; export waits for completion")
        application.show_library()
        root.update()
        library_ui = application.library_window
        assert len(library_ui.tree.get_children()) == 2
        deadline = time.monotonic() + 10
        while len(library_ui.cover_images) < 2 and time.monotonic() < deadline:
            root.update()
            time.sleep(0.05)
        assert len(library_ui.cover_images) == 2
        assert all(photo != library_ui.cover_placeholder for photo in library_ui.cover_images.values())
        report["checks"].append("First-page PDF/ZIP covers load asynchronously in the actual library UI")
        selected = library_ui.tree.get_children()[0]
        library_ui.tree.selection_set(selected)
        library_ui.action("favorite")
        library_ui.only_favorites.set(True)
        library_ui.render()
        assert len(library_ui.tree.get_children()) == 1
        from library import Library
        assert Library(directory / "gui-state").entries[selected]["favorite"]
        library_ui.query.set("not-a-matching-title")
        root.update()
        assert len(library_ui.tree.get_children()) == 0
        library_ui.query.set("")
        library_ui.only_favorites.set(False)
        library_ui.render()
        library_ui.select("all")
        assert len(library_ui.tree.selection()) == 2
        library_ui.action("favorite_on")
        assert len(application.engine.library.select(favorites=True)) == 2
        library_ui.select("invert")
        assert not library_ui.tree.selection()
        library_ui.select("all")
        library_ui.action("favorite_off")
        assert not application.engine.library.select(favorites=True)
        # A finished file whose queue record was cleared must be discoverable.
        import shutil
        from unittest.mock import patch
        orphan = directory / "artifacts" / "999999_old-export.zip"
        shutil.copyfile(next(Path(t.result) for t in engine.tasks if t.settings["format"] == "zip"), orphan)
        application.output_var.set(str(directory / "artifacts"))
        with patch.object(library_ui.messagebox, "askyesno", return_value=True):
            library_ui.scan()
        deadline = time.monotonic() + 10
        while library_ui.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(.02)
        assert not library_ui.busy and len(library_ui.tree.get_children()) == 3
        assert len(application.engine.library.select("999999")) == 1
        for geometry in ("1000x640", "850x520", "1000x540"):
            library_ui.window.geometry(geometry)
            library_ui.path_text.set("C:/" + "very-long-directory/" * 40 + "999999.zip")
            root.update()
            assert library_ui.tree.winfo_height() >= 80
            for button in library_ui.action_buttons.values():
                x = button.winfo_rootx() - library_ui.window.winfo_rootx()
                y = button.winfo_rooty() - library_ui.window.winfo_rooty()
                assert button.winfo_ismapped() and button.winfo_height() >= button.winfo_reqheight()
                assert x >= 0 and y >= 0 and x + button.winfo_width() <= library_ui.window.winfo_width()
                assert y + button.winfo_height() <= library_ui.window.winfo_height()
        library_ui.select("all")
        library_ui.action_buttons["favorite_on"].invoke()
        assert len(application.engine.library.select(favorites=True)) == 3
        library_ui.action_buttons["favorite_off"].invoke()
        assert not application.engine.library.select(favorites=True)
        report["checks"].append("Library action buttons fully visible and invokable at default/minimum sizes with long paths")
        library_ui.window.destroy()
        # Exercise the new default download and the actual export dialog/worker.
        from worker import run_download
        image_task = Task("123459", Settings(download_all_chapters=True, output=str(directory / "image-artifacts")).__dict__)
        events = []
        run_download(image_task.to_dict(), "", events.append, FixtureClient)
        image_task.status = "done"
        image_task.result = events[-1]["path"]
        image_task.result_bytes = events[-1]["result_bytes"]
        image_task.done = image_task.total = events[-1]["total"]
        application.engine.tasks.append(image_task)
        application.render()
        assert application.current_settings().format == "images"
        for selected_format in ("pdf", "zip", "images"):
            application.format_var.set(selected_format)
            application.save_format()
            assert application.current_settings().format == selected_format
            assert Engine(application.home).settings.format == selected_format
        report["checks"].append("Three download formats persist across restart")
        application.show_library()
        image_library = application.library_window
        key = image_library.library.key(image_task.result)
        image_library.tree.selection_set(key)
        from export_ui import show_export
        export_dialog = show_export(image_library, key)
        root.update()
        controls = export_dialog.winfo_children()[0].winfo_children()
        choices = [w.cget("text") for w in controls if "text" in w.keys()]
        assert any("分章节" in value for value in choices)
        next(w for w in controls if "text" in w.keys() and w.cget("text") == "开始导出").invoke()
        deadline = time.monotonic() + 15
        while image_library.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(.02)
        assert not image_library.busy
        exports = list(Path(image_task.result).parent.glob("*.pdf"))
        assert len(exports) == 1 and len(PdfReader(exports[0]).pages) == 5
        assert Path(image_task.result).is_dir()
        from albums import export_album, read_album
        zipped = export_album(image_task.result, directory / "conversion-zip", "zip")[0]
        for source in (zipped, exports[0]):
            converted = export_album(source, directory / ("converted-" + source.suffix[1:]), "images")[0]
            assert len(read_album(converted, verify=True)[1]) == 5
            other_format = "pdf" if source.suffix == ".zip" else "zip"
            assert export_album(source, directory / ("converted-to-" + other_format), other_format)[0].is_file()
        report["checks"].append("All six folder/ZIP/PDF conversion directions succeed offline and retain sources")
        # Exercise the shipped reader on real folder, ZIP and PDF fixtures.
        from reader import ReaderState
        def reader_wait(predicate):
            deadline = time.monotonic() + 15
            while not predicate() and time.monotonic() < deadline:
                root.update()
                time.sleep(.025)
            assert predicate(), "Reader operation timed out"
        for source, fmt in ((Path(image_task.result), "images"), (zipped, "zip"), (exports[0], "pdf")):
            reader_key = application.engine.library.key(source)
            if reader_key not in application.engine.library.entries:
                application.engine.library.import_found([dict(id="123459", title="Reader fixture", path=str(source), root=str(source.parent), format=fmt, favorite=False, added=0)])
            reader = application.read_comic(reader_key)
            reader_wait(lambda: len(reader.pages) == 5 and bool(reader.images))
            assert application.read_comic(reader_key) is reader
            reader.mode.set("左右翻页")
            reader.relayout()
            reader.go(3)
            reader_wait(lambda: 3 in reader.images and reader.current == 3)
            assert reader.current == 3 and "4/5" in reader.status.get()
            if fmt != "pdf":
                assert len(reader.starts) == 2
                reader.chapter_step(-1)
                reader_wait(lambda: reader.current == 0)
                assert reader.current == 0
                reader.chapter_step(1)
                reader_wait(lambda: reader.current == reader.starts[1])
                assert reader.current == reader.starts[1]
                reader.go(3)
                reader_wait(lambda: reader.current == 3)
            else:
                assert len(reader.starts) == 1
            reader.mark()
            assert 3 in reader.marks
            reader.favorite()
            assert Library(application.home).entries[reader_key]["favorite"]
            reader_wait(lambda: 2 in reader.images and 4 in reader.images)
            old_photo = reader.pager.photo
            reader.go(4)
            assert reader.current == 3 and reader.pager.photo is old_photo
            reader_wait(lambda: reader.current == 4)
            # Real Tk events exercise follow-pointer movement and release settling.
            width = reader.canvas.winfo_width()
            reader.canvas.event_generate('<ButtonPress-1>', x=width // 3, y=100)
            reader.canvas.event_generate('<B1-Motion>', x=width * 2 // 3, y=100)
            assert reader.pager.dx > 0 and reader.current == 4
            reader.canvas.event_generate('<ButtonRelease-1>', x=width * 2 // 3, y=100)
            reader_wait(lambda: reader.current == 3)
            assert len(reader.canvas.find_all()) == 3
            if fmt == 'images':
                from reader_checks import check_paging
                report['reader_paging'] = check_paging(reader, root, reader_wait)
            for geometry in ("1000x820", "740x520"):
                reader.window.geometry(geometry)
                root.update()
                for control in (reader.chapter_box, reader.favorite_button, reader.mark_button, reader.canvas):
                    assert control.winfo_ismapped()
                    assert control.winfo_rootx() + control.winfo_width() <= reader.window.winfo_rootx() + reader.window.winfo_width()
            reader.close()
            assert ReaderState(application.home).get(reader_key, 5) == dict(page=3, mode="paged", bookmarks=[3])
            reader = application.read_comic(reader_key)
            reader_wait(lambda: len(reader.pages) == 5 and 3 in reader.images)
            assert reader.current == 3 and 3 in reader.marks and not reader.is_scroll()
            reader.mode.set("滚动阅读")
            reader.relayout()
            from reader_checks import check_scroll
            report.setdefault('reader_scroll_seams', {})[fmt] = check_scroll(reader, root, reader_wait)
            reader.go(4)
            reader_wait(lambda: 4 in reader.images)
            reader_wait(lambda: reader.current == 4)
            assert len(reader.images) <= 6
            reader.close()
        report["checks"].append("Internal folder/ZIP/PDF reader: render, chapters, page count, favorite, bookmark and restart restore")
        report["checks"].append("Reader scroll/paged switching, last-page navigation, single-window reuse and controls at minimum size")
        report["checks"].append("Reader adjacent predecode, persistent two-layer animation and real Tk drag preserve displayed page until commit")
        report["checks"].append("Reader 100 transitions, gated slow decode and unreadable page retain pixels and bound cache without new canvas items")
        report["checks"].append("Reader scroll images touch with zero gap across folder/ZIP/PDF pages, chapter boundaries and window sizes")
        image_library.window.destroy()
        report["checks"].append("Default ordered-image download, library recognition and explicit PDF export dialog preserve originals")
        report["checks"].append("Library UI: scan orphan export, select all/invert, batch favorite/unfavorite, search and persistence")
        # The announcement must remain readable without a newer release or network.
        from core import VERSION
        from unittest.mock import patch
        application.updates.automatic = False
        application.updates.show()
        root.update()
        announcement = application.updates.announcement_area.get("1.0", "end")
        from updates import CURRENT_NOTES
        assert VERSION in announcement and announcement.strip() == CURRENT_NOTES.strip()
        assert str(application.updates.download_button["state"]) == "disabled"
        with patch.object(application.updates, "show_notes") as shown:
            application.updates.seen_path.unlink(missing_ok=True)
            application.updates.startup()
            application.updates.startup()
            assert shown.call_count == 1
        report["checks"].append("Full offline announcement rendered; first-start notice shown once")
        check_update_history_ui(root, directory)
        report["checks"].append("Open full announcement refreshes with async check; repeated open reuses window")
        report["checks"].append("Multi-version upgrade startup and restart retain every cached release after successful recheck")
        report["checks"].append("Failed checks preserve upgrade notes and refresh status; closed popup is safe")
        check_manual_update_ui(application, directory)
        report["checks"].append("Manual check works from main/update/announcement buttons with automatic checks off and settings unchanged")
        report["checks"].append("Manual check coalesces clicks, shows async result, preserves offline notes and allows failure retry")
        report["checks"].append("Check controls fit minimum window; empty repo and update install/download prevent requests")
        from cleanup_checks import check_cleanup_ui
        check_cleanup_ui(application, directory)
        report["checks"].append("cache cleanup UI: real button, background work, accurate result, resume protection and start exclusion")
        from cancellation_checks import check_cancel_ui
        check_cancel_ui(application, directory)
        report["checks"].append("Cancel button: background file deletion, row removal, persisted queue and minimum window layout")
        from update_download_checks import check_update_download
        check_update_download(directory)
        report["checks"].append("Update downloads: GitHub/GHFast/GH-Proxy fallback resets partial bytes and progress; cancellation and SHA-256 rejection retained")
        root.destroy()
        report["ok"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    atomic_json(directory / "self-test.json", report)
    if not report["ok"]:
        raise RuntimeError(report.get("error", "Self-test failed"))
