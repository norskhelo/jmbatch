import unittest
from unittest.mock import patch

from reader_chrome import TapGesture


class TapTests(unittest.TestCase):
    def test_short_tap_and_small_jitter(self):
        with patch('reader_chrome.time.monotonic', side_effect=[1, 1.1]):
            tap = TapGesture(); tap.down(40, 50)
            self.assertTrue(tap.up(44, 53))
        self.assertFalse(tap.up(44, 53))

    def test_drag_out_and_back_is_not_a_tap(self):
        tap = TapGesture(); tap.down(40, 50); tap.move(80, 50)
        self.assertFalse(tap.up(40, 50))

    def test_vertical_motion_is_not_a_tap(self):
        tap = TapGesture(); tap.down(40, 50); tap.move(40, 80)
        self.assertFalse(tap.up(40, 50))

    def test_long_press_is_not_a_tap(self):
        with patch('reader_chrome.time.monotonic', side_effect=[1, 1.6]):
            tap = TapGesture(); tap.down(40, 50)
            self.assertFalse(tap.up(40, 50))
