"""Offline integration diagnostics: generated test pages, no site requests."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

from core import Settings, Task, atomic_json, explain_error
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
    except Exception as exc:
        channel.put({"type": "error", "error": explain_error(exc, cookie)})


def stalled_worker(task, cookie, channel):
    channel.put({"type": "phase", "phase": "download", "total": 5, "message": "Offline stalled fixture"})
    time.sleep(120)


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
            engine.add(["123456"], Settings(output=str(directory / "artifacts"), format=fmt))
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
        image_task = Task("123459", Settings(output=str(directory / "image-artifacts")).__dict__)
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
        root.destroy()
        report["ok"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    atomic_json(directory / "self-test.json", report)
    if not report["ok"]:
        raise RuntimeError(report.get("error", "Self-test failed"))
