import json
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from core import Settings, SpeedWatch, Task, explain_error, parse_ids, task_cache
from diagnostics import FixtureClient, FailingFixtureClient, fixture_worker, stalled_worker
from engine import Engine, WorkerState
from worker import parse_cookies, run_download


class ParseTests(unittest.TestCase):
    def test_ranges_and_dedup(self):
        self.assertEqual(parse_ids("JM123456，123457\n123456;123458 至 JM123460"), [str(n) for n in range(123456, 123461)])

    def test_invalid(self):
        for value in ("", "123456-123400", "foo", "1-9000000000", "123456-9000000000", "123456/drop", "000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_ids(value)

    def test_cookies_redacted(self):
        cookie = "AVS=abcdef12345; session=sekret987"
        self.assertEqual(parse_cookies(cookie)["AVS"], "abcdef12345")
        error = explain_error(TimeoutError("abcdef12345 https://host/?token=sekret987 timed out"), cookie)
        self.assertNotIn("abcdef12345", error)
        self.assertNotIn("sekret987", error)
        self.assertIn("超时", error)

    def test_speed_and_stall(self):
        settings = Settings(slow_kbps=30, slow_seconds=20, stall_seconds=100)
        slow = SpeedWatch(settings, 0)
        for n in range(1, 51):
            _, reason = slow.sample(n, n * 100)
        self.assertIn("平均落盘速度", reason)
        normal = SpeedWatch(settings, 0)
        for n in range(1, 81):
            _, reason = normal.sample(n, n * 100 * 1024)
            self.assertIsNone(reason)
        stall = SpeedWatch(Settings(slow_kbps=0, stall_seconds=30), 0)
        self.assertIn("没有完成", stall.sample(31, 0)[1])
        disabled = SpeedWatch(Settings(auto_reset=False), 0)
        self.assertIsNone(disabled.sample(9999, 0)[1])


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parent / "_tmp"
        temp_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def task(self, fmt="pdf"):
        return Task("123456", Settings(output=str(self.root / "out"), format=fmt, keep_images=True).__dict__).to_dict()

    def test_sizes_survive_cached_download_and_queue_restore(self):
        task = self.task("zip")
        events = []
        run_download(task, "", events.append, FixtureClient)
        progress = [event for event in events if event["type"] == "progress"]
        actual_images = sum(p.stat().st_size for p in (task_cache(task) / "images").rglob("*.jpg"))
        self.assertEqual(progress[-1]["image_bytes"], actual_images)
        self.assertEqual(progress[-1]["bytes"], actual_images)
        result = events[-1]
        self.assertEqual(result["message"], "下载完成")
        self.assertEqual(result["result_bytes"], Path(result["path"]).stat().st_size)
        restored = []
        run_download(task, "", restored.append, FixtureClient)
        self.assertEqual(restored[-1]["result_bytes"], result["result_bytes"])
        Path(result["path"]).unlink()
        resumed = []
        run_download(task, "", resumed.append, FixtureClient)
        cached = [event for event in resumed if event["type"] == "progress"][-1]
        self.assertEqual(cached["cached"], cached["total"])
        self.assertEqual(cached["bytes"], 0)
        self.assertEqual(cached["image_bytes"], actual_images)
        engine = Engine(self.root / "state")
        engine.tasks = [Task(**task)]
        state = WorkerState(engine.tasks[0])
        engine.active[state.task.key] = state
        from core import SpeedWatch
        state.watch = SpeedWatch(Settings(**task["settings"]), 0)
        engine._handle(state, cached, 1)
        engine._handle(state, resumed[-1], 2)
        loaded = Engine(self.root / "state").tasks[0]
        self.assertEqual(loaded.image_bytes, actual_images)
        self.assertEqual(loaded.result_bytes, resumed[-1]["result_bytes"])
        self.assertEqual(loaded.status, "done")

    def test_only_failed_page_is_retried(self):
        from collections import Counter
        attempts = Counter()
        class TransientPage(FixtureClient):
            def download_by_image_detail(self, image, path, decode_image=True):
                key = (image.from_photo.sort, image.index)
                attempts[key] += 1
                if key == (1, 2) and attempts[key] == 1:
                    Path(path).write_bytes(b"broken partial")
                    raise TimeoutError("transient page timeout")
                return super().download_by_image_detail(image, path, decode_image)
        events = []
        task = self.task("zip")
        run_download(task, "", events.append, TransientPage)
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["total"], 5)
        self.assertEqual(attempts[(1, 2)], 2)
        self.assertTrue(all(n == 1 for key, n in attempts.items() if key != (1, 2)))
        self.assertEqual(len([e for e in events if e.get("phase") == "page_retry"]), 1)
        self.assertFalse(list(task_cache(task).rglob("*.partial.jpg")))

    def test_single_page_retry_is_bounded_and_reports_position(self):
        from collections import Counter
        attempts = Counter()
        class PermanentPage(FixtureClient):
            def download_by_image_detail(self, image, path, decode_image=True):
                key=(image.from_photo.sort,image.index);attempts[key]+=1
                if key==(2,1):raise TimeoutError("still offline")
                return super().download_by_image_detail(image,path,decode_image)
        task=self.task("zip")
        with self.assertRaisesRegex(IOError,"第 2 章第 1 页"):
            run_download(task,"",lambda e:None,PermanentPage)
        self.assertEqual(attempts[(2,1)],3)
        self.assertTrue(all(n==1 for key,n in attempts.items() if key!=(2,1)))
        self.assertEqual(len(list((task_cache(task)/"images").rglob("*.jpg"))),4)
        self.assertFalse(list(Path(task["settings"]["output"]).glob("*.zip")))

    def test_multiple_failed_pages_do_not_trigger_single_page_recovery(self):
        from collections import Counter
        attempts=Counter()
        class ManyFailures(FixtureClient):
            def download_by_image_detail(self,image,path,decode_image=True):
                key=(image.from_photo.sort,image.index);attempts[key]+=1
                if image.index==2:raise TimeoutError("two pages offline")
                return super().download_by_image_detail(image,path,decode_image)
        with self.assertRaisesRegex(IOError,"2 页下载失败"):
            run_download(self.task("zip"),"",lambda e:None,ManyFailures)
        self.assertEqual(len(attempts),5)
        self.assertTrue(all(n==1 for n in attempts.values()))

    def test_worker_multi_chapter_exports_and_recovery(self):
        from pypdf import PdfReader
        import zipfile
        for fmt in ("pdf", "zip"):
            task = self.task(fmt)
            events = []
            run_download(task, "", events.append, FixtureClient)
            result = Path(events[-1]["path"])
            self.assertEqual(events[-1]["total"], 5)
            if fmt == "pdf":
                with result.open("rb") as stream:
                    self.assertEqual(len(PdfReader(stream).pages), 5)
            else:
                with zipfile.ZipFile(result) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(archive.namelist()[:5], ["0001/00001.jpg", "0001/00002.jpg", "0001/00003.jpg", "0002/00001.jpg", "0002/00002.jpg"])
            events.clear()
            run_download(task, "", events.append, lambda: self.fail("Completed task should not access client"))
            self.assertEqual(events[-1]["path"], str(result))

    def test_optional_export_layouts_and_collision(self):
        import zipfile
        for numeric in (False, True):
            for flat in (False, True):
                task = self.task("zip")
                task["settings"].update(numeric_filename=numeric, flat_zip=flat)
                task["settings"]["output"] = str(self.root / f"out-{numeric}-{flat}")
                events = []
                run_download(task, "", events.append, FixtureClient)
                result = Path(events[-1]["path"])
                self.assertEqual(result.name == "123456.zip", numeric)
                with zipfile.ZipFile(result) as archive:
                    expected = [
                        "0001/00001.jpg", "0001/00002.jpg", "0001/00003.jpg",
                        "0002/00001.jpg", "0002/00002.jpg"] + ([] if flat else ["下载信息.json"])
                    self.assertEqual(archive.namelist(), expected)
                    self.assertIsNone(archive.testzip())
                events.clear()
                run_download(task, "", events.append, lambda: self.fail("Recovery must not use network"))
                self.assertEqual(events[-1]["path"], str(result))
                if numeric:
                    saved = result.read_bytes()
                    second = self.task("zip")
                    second["settings"] = dict(task["settings"])
                    with self.assertRaises(FileExistsError):
                        run_download(second, "", lambda event: None, FixtureClient)
                    self.assertEqual(result.read_bytes(), saved)
        task = self.task("pdf")
        task["settings"].update(numeric_filename=True, flat_zip=True)
        events = []
        run_download(task, "", events.append, FixtureClient)
        self.assertEqual(Path(events[-1]["path"]).name, "123456.pdf")

    def test_single_chapter_flat_zip_and_legacy_marker(self):
        import zipfile
        import jmcomic
        class SingleChapter(FixtureClient):
            def get_album_detail(self, album_id):
                return jmcomic.JmAlbumDetail(album_id, "220980", "Single chapter", [("800001", "1", "Chapter one")],
                                            3, "2026-01-01", "2026-01-01", "0", "0", 0, [], [], [], [])
        for flat in (False, True):
            task = self.task("zip")
            task["settings"].update(flat_zip=flat, keep_images=True)
            events = []
            run_download(task, "", events.append, SingleChapter)
            result = Path(events[-1]["path"])
            expected = [f"{i:05d}.jpg" for i in range(1,4)] if flat else [f"0001/{i:05d}.jpg" for i in range(1,4)] + ["下载信息.json"]
            with zipfile.ZipFile(result) as archive:
                self.assertEqual(archive.namelist(), expected)
                self.assertIsNone(archive.testzip())
            if flat:
                marker = task_cache(task) / "completed.json"
                data = json.loads(marker.read_text(encoding="utf-8"))
                data.pop("zip_layout_version")
                marker.write_text(json.dumps(data),encoding="utf-8")
                saved = result.read_bytes()
                events.clear()
                run_download(task, "", events.append, SingleChapter)
                self.assertNotEqual(events[-1]["path"],str(result))
                self.assertEqual(result.read_bytes(),saved)
                self.assertEqual([e for e in events if e["type"]=="progress"][-1]["cached"],3)

    def test_export_preferences_persist_and_old_settings_default(self):
        self.assertFalse(Settings().numeric_filename)
        self.assertFalse(Settings().flat_zip)
        from core import atomic_json
        path = self.root / "settings.json"
        atomic_json(path, Settings(numeric_filename=True, flat_zip=True).__dict__)
        loaded = Settings(**json.loads(path.read_text(encoding="utf-8")))
        self.assertTrue(loaded.numeric_filename and loaded.flat_zip)

    def test_real_client_session_and_stage_metrics_without_network(self):
        import jmcomic
        from common.postman.postman_impl import CurlCffiSessionPostman
        fixture = FixtureClient()
        observed = []

        def local_image(client, image, path, decode_image=True):
            self.assertIsInstance(client.postman, CurlCffiSessionPostman)
            observed.append(id(client.postman.session))
            fixture.download_by_image_detail(image, path, decode_image)

        with patch.object(jmcomic.JmModuleConfig, "FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN", False), \
             patch.object(jmcomic.JmModuleConfig, "FLAG_API_CLIENT_REQUIRE_COOKIES", False), \
             patch.object(jmcomic.JmApiClient, "get_album_detail", lambda client, album_id: fixture.get_album_detail(album_id)), \
             patch.object(jmcomic.JmApiClient, "check_photo", lambda client, photo: fixture.check_photo(photo)), \
             patch.object(jmcomic.JmApiClient, "download_by_image_detail", local_image):
            events = []
            run_download(self.task(), "", events.append)
        self.assertEqual(len(observed), 5)
        self.assertEqual(len(set(observed)), 1)
        metrics = next(event["metrics"] for event in events if event["type"] == "metrics")
        self.assertEqual(set(metrics["stages"]), {"startup", "metadata", "download", "verify", "export"})
        self.assertGreater(metrics["total_seconds"], 0)
        self.assertGreater(metrics["downloaded_image_bytes"], 0)

    def test_failed_download_has_no_output_and_resumes_valid_cache(self):
        task = self.task()
        events = []
        with self.assertRaises(Exception):
            run_download(task, "", events.append, FailingFixtureClient)
        self.assertFalse(list((self.root / "out").glob("*.pdf")))
        cached = list((task_cache(task) / "images").rglob("*.jpg"))
        self.assertTrue(cached)
        # Invalid cache must be redownloaded, not counted as success.
        cached[0].write_bytes(b"truncated-image")
        events.clear()
        run_download(task, "", events.append, FixtureClient)
        self.assertEqual(events[-1]["total"], 5)
        progress = [e for e in events if e["type"] == "progress"]
        self.assertLess(progress[-1]["cached"], 5)
        self.assertGreater(progress[-1]["bytes"], 0)

    def test_queue_snapshot_and_cookie_not_saved(self):
        engine = Engine(self.root / "state")
        settings = Settings(output=str(self.root / "out"))
        engine.cookie = "secret-cookie"
        self.assertEqual(engine.add(["123456", "123456"], settings), 1)
        engine.tasks[0].status = "running"
        engine.save()
        recovered = Engine(self.root / "state")
        self.assertEqual(recovered.tasks[0].status, "paused")
        self.assertNotIn("secret-cookie", (self.root / "state" / "queue.json").read_text(encoding="utf-8"))

    def test_subprocess_pause_resume(self):
        engine = Engine(self.root / "state", worker_target=stalled_worker)
        engine.add(["123456"], Settings(output=str(self.root / "out")))
        engine.start()
        engine.tick()
        self.assertTrue(engine.active[engine.tasks[0].key].process.is_alive())
        engine.pause()
        self.assertFalse(any(s.process for s in engine.active.values()))
        self.assertEqual(engine.tasks[0].status, "paused")
        engine.worker_target = fixture_worker
        engine.start()
        deadline = time.monotonic() + 30
        while engine.running and time.monotonic() < deadline:
            engine.tick()
            time.sleep(.05)
        try:
            self.assertEqual(engine.tasks[0].status, "done", engine.tasks[0].error)
        finally:
            engine.close()

    def test_bounded_reset_terminates_real_worker(self):
        engine = Engine(self.root / "state", worker_target=stalled_worker)
        settings = Settings(output=str(self.root / "out"), slow_kbps=0, stall_seconds=30, max_resets=1)
        engine.add(["123456"], settings)
        engine.start()
        engine.tick()
        deadline = time.monotonic() + 10
        while engine.active[engine.tasks[0].key].phase != "download" and time.monotonic() < deadline:
            engine.tick()
            time.sleep(.05)
        try:
            self.assertEqual(engine.active[engine.tasks[0].key].phase, "download")
            engine.active[engine.tasks[0].key].watch.last_progress = time.monotonic() - 31
            engine.tick()
            self.assertEqual(engine.tasks[0].status, "resetting")
            self.assertFalse(any(s.process for s in engine.active.values()))
            engine.active[engine.tasks[0].key].next_start = 0
            engine.tick()
            deadline = time.monotonic() + 10
            while engine.active[engine.tasks[0].key].phase != "download" and time.monotonic() < deadline:
                engine.tick()
                time.sleep(.05)
            engine.active[engine.tasks[0].key].watch.last_progress = time.monotonic() - 31
            engine.tick()
            self.assertEqual(engine.tasks[0].status, "failed")
            self.assertIn("上限 1 次", engine.tasks[0].error)
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
