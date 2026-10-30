import unittest

from download_display import format_speed, percent, progress_text, size_text, eta_text, failure_text


class DownloadDisplayTests(unittest.TestCase):
    def test_failed_task_shows_stored_cause_and_recovers_without_stale_error(self):
        error = "网络请求超时。\nTimeoutError: timed out"
        self.assertEqual(failure_text("failed", error), "失败原因：网络请求超时。 TimeoutError: timed out")
        for status in ("queued", "running", "paused", "resetting", "done", "cancelled"):
            self.assertEqual(failure_text(status, error), "")

    def test_legacy_failure_and_generic_explanation(self):
        self.assertEqual(failure_text("failed", "", "自动重连失败"), "失败原因：自动重连失败")
        for phase in (None, "", "下载失败，点击任务查看原因"):
            self.assertIn("未记录具体原因", failure_text("failed", None, phase))
        self.assertEqual(failure_text("failed", "任务未完成。下方为具体原因；修正后可选中任务重试。\nOSError: 图片损坏"), "失败原因：图片损坏")
        self.assertEqual(failure_text("failed", "SocketTimeoutException: 网络请求超时"), "失败原因：网络请求超时")

    def test_speed_unit_boundaries(self):
        for value, expected in [(0, "0 B/s"), (1023, "1023 B/s"), (1024, "1.0 KB/s"),
                                (1024 ** 2, "1.0 MB/s"), (1024 ** 3, "1.0 GB/s"), (-1, "0 B/s")]:
            self.assertEqual(format_speed(value), expected)

    def test_completion_waits_for_verified_output(self):
        self.assertEqual(percent(1, 4, "running"), 25)
        self.assertEqual(percent(4, 4, "running"), 99.9)
        self.assertEqual(percent(4, 4, "failed"), 99.9)
        self.assertEqual(percent(4, 4, "done"), 100)
        self.assertIn("0.0%", progress_text(0, 0, "running"))

    def test_estimated_images_vs_actual_archive(self):
        self.assertEqual(size_text(2, 4, 2048, 0, "running"), "已下载图片 2.0 KB / 预计大小 4.0 KB")
        self.assertEqual(size_text(4, 4, 4096, 3000, "done"), "漫画大小 2.9 KB")
        self.assertIn("未知", size_text(4, 4, 0, 0, "done"))

    def test_eta_excludes_cached_pages_and_handles_inactive_states(self):
        # 5 pages remain; 5 freshly downloaded pages took 10s (10 cached).
        estimate = eta_text("running", "download", 15, 20, 10, 10, 2048, 0)
        self.assertIn("约剩 10 秒", estimate)
        self.assertIn("导出另计", estimate)
        for status in ("paused", "resetting", "failed", "cancelled", "done"):
            self.assertNotIn("约剩", eta_text(status, "download", 15, 20, 10, 10, 2048, 0))
        self.assertIn("计算中", eta_text("running", "download", 10, 20, 10, 1, 2048, 0))
        self.assertIn("计算中", eta_text("running", "download", 15, 20, 10, 10, 0, 0))
        self.assertIn("导出", eta_text("running", "export", 20, 20, 10, 10, 2048, 0))
        self.assertIn("重试", eta_text("running", "page_retry", 19, 20, 10, 10, 2048, 0))
        self.assertIn("校验已有图片", eta_text("running", "cache", 15, 20, 10, 10, 2048, 0))
        self.assertNotIn("约剩", eta_text("running", "cache", 15, 20, 10, 10, 2048, 0))
