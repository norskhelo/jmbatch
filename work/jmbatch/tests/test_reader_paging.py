import threading
import queue
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from reader import ReaderWorker
from reader_paging import CanvasPager


class Surface:
    def __init__(self):
        self.items = {}; self.timers = {}; self.now = 0.; self.serial = 0
    def create_image(self, *args, **kwargs):
        self.serial += 1; self.items[self.serial] = kwargs; return self.serial
    create_text = create_image
    def itemconfigure(self, item, **kwargs):
        self.items[item].update(kwargs)
    def coords(self, item, *coords):
        self.items[item]['coords'] = coords
    def winfo_width(self): return 800
    def winfo_height(self): return 1000
    def after(self, delay, callback):
        self.serial += 1; self.timers[self.serial] = (self.now + delay / 1000, callback); return self.serial
    def after_cancel(self, token): self.timers.pop(token, None)
    def advance(self, seconds):
        end = self.now + seconds
        while self.timers:
            token = min(self.timers, key=lambda t: self.timers[t][0])
            when, callback = self.timers[token]
            if when > end: break
            self.now = when; del self.timers[token]; callback()
        self.now = end


class PagingTests(unittest.TestCase):
    def setUp(self):
        self.ui = Surface(); self.photos = {0: object(), 1: object()}; self.commits = []; self.requests = []
        self.clock = patch('reader_paging.time.monotonic', lambda: self.ui.now); self.clock.start(); self.addCleanup(self.clock.stop)
        self.pager = CanvasPager(self.ui, self.ui, self.photos.get, lambda: self.requests.append(self.pager.target), self.commits.append)
        self.pager.activate(5, 0)
    def event(self, x, y=300): return SimpleNamespace(x=x, y=y)
    def test_miss_retains_image_and_committed_position(self):
        old = self.pager.photo; self.pager.go(2); self.ui.advance(.25)
        self.assertIs(self.pager.photo, old); self.assertEqual(self.pager.page, 0)
        self.assertIn('3', self.ui.items[self.pager.notice]['text'])
        self.assertEqual(self.commits, [0])
    def test_commit_only_after_animation_and_stable_items(self):
        items = set(self.ui.items); self.pager.go(1)
        self.ui.advance(.08); self.assertEqual(self.pager.page, 0)
        self.assertNotEqual(self.pager.dx, 0)
        self.ui.advance(.2); self.assertEqual(self.pager.page, 1)
        self.assertEqual(set(self.ui.items), items); self.assertEqual(self.commits, [0, 1])
    def test_late_obsolete_result_does_not_replace_latest(self):
        self.pager.go(2); self.pager.go(3); self.photos[2] = object(); self.pager.ready()
        self.assertEqual(self.pager.page, 0)
        self.photos[3] = object(); self.pager.ready(); self.ui.advance(.3)
        self.assertEqual(self.pager.page, 3); self.assertNotIn(2, self.commits)
    def test_animation_interrupted_by_reverse(self):
        self.pager.go(1); self.ui.advance(.05); self.pager.go(0); self.ui.advance(1)
        self.assertEqual(self.pager.page, 0); self.assertEqual(self.pager.dx, 0)
        self.assertEqual(self.commits, [0])
    def test_drag_follows_pointer_then_commits(self):
        self.pager.press(self.event(600)); self.ui.advance(.1); self.pager.move(self.event(300))
        self.assertEqual(self.pager.dx, -300); self.assertEqual(self.pager.page, 0)
        self.pager.release(self.event(300)); self.ui.advance(.3)
        self.assertEqual(self.pager.page, 1)
    def test_small_drag_bounces(self):
        self.pager.press(self.event(600)); self.ui.advance(1); self.pager.move(self.event(570)); self.pager.release(self.event(570)); self.ui.advance(.3)
        self.assertEqual(self.pager.page, 0); self.assertEqual(self.pager.dx, 0)
    def test_missing_neighbor_resists_and_waits_without_blank(self):
        del self.photos[1]; self.pager.press(self.event(600)); self.pager.move(self.event(50))
        self.assertLessEqual(abs(self.pager.dx), 96)
        self.pager.release(self.event(50)); self.ui.advance(.3)
        self.assertEqual(self.pager.page, 0); self.assertIsNotNone(self.pager.photo)
        self.photos[1] = object(); self.pager.ready(); self.ui.advance(.3); self.assertEqual(self.pager.page, 1)
    def test_boundary_and_vertical_drag_do_not_turn(self):
        self.pager.go(-1); self.pager.press(self.event(600)); self.pager.move(self.event(610, 600)); self.pager.release(self.event(610, 600)); self.ui.advance(.3)
        self.assertEqual(self.pager.page, 0)
    def test_failure_keeps_current_and_names_target(self):
        self.pager.go(2); self.pager.error('broken'); self.ui.advance(.3)
        self.assertIs(self.pager.photo, self.photos[0]); self.assertIn('3', self.ui.items[self.pager.notice]['text'])
        self.assertIn('broken', self.ui.items[self.pager.notice]['text'])
    def test_close_cancels_all_callbacks(self):
        self.pager.go(1); self.pager.close(); self.ui.advance(1)
        self.assertFalse(self.ui.timers); self.assertIsNone(self.pager.photo)
    def test_active_and_undelivered_jobs_not_queued_again(self):
        worker = ReaderWorker.__new__(ReaderWorker)
        worker.condition = threading.Condition(); worker.active = {(1, 0, 800, 1000)}
        worker.request([(1, 1, 800, 1000)]); worker.request([(1, 0, 800, 1000), (1, 0, 800, 1000)])
        self.assertEqual(worker.requests, [])
        worker.acknowledge(1, 0); worker.request([(1, 0, 800, 1000), (1, 0, 800, 1000)])
        self.assertEqual(len(worker.requests), 1)

    def test_real_worker_rapid_return_renders_once(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        class Source:
            pages = [dict(chapter=1, page=i+1) for i in range(3)]
            def __init__(self, path): pass
            def render(self, index, width, height):
                calls.append(index); entered.set(); release.wait(2)
                return SimpleNamespace(close=lambda: None)
            def close(self): pass
        with patch('reader.ReaderSource', Source):
            worker = ReaderWorker('fake')
            try:
                worker.results.get(timeout=2)
                worker.request([(1, 0, 800, 1000)]); self.assertTrue(entered.wait(2))
                worker.request([(1, 1, 800, 1000)]); worker.request([(1, 0, 800, 1000)])
                release.set(); result = worker.results.get(timeout=2)
                worker.request([(1, 0, 800, 1000)])
                with self.assertRaises(queue.Empty): worker.results.get(timeout=.1)
                self.assertEqual(calls, [0]); self.assertEqual(result[2], 0)
            finally:
                release.set(); worker.close()


if __name__ == '__main__': unittest.main()
