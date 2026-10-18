"""Real Tk events against the production library, with an isolated catalogue."""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from library import Library
from library_ui import LibraryWindow


class LibraryInteractionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        library = Library(self.temp.name)
        for n in range(3):
            path = str(Path(self.temp.name) / f'{n}.zip')
            library.entries[path] = dict(path=path, root=self.temp.name, id=str(n),
                                        title=f'Comic {n}', format='zip', favorite=False)
        self.root = tk.Tk()
        app = SimpleNamespace(root=self.root, engine=SimpleNamespace(library=library, tasks=[]), read_comic=Mock())
        self.ui = LibraryWindow(app)
        self.root.update()
        self.keys = self.ui.tree.get_children()

    def tearDown(self):
        self.root.destroy()
        self.temp.cleanup()

    def event(self, name, index=0, dx=0, dy=0):
        x, y, width, height = self.ui.tree.bbox(self.keys[index])
        self.ui.tree.event_generate(name, x=x+30+dx, y=y+height//2+dy)
        self.root.update()

    def click(self, index=0):
        # Ensure separate gestures are not interpreted as a system double click.
        self.ui.tree.event_generate('<Leave>')
        self.event('<ButtonPress-1>', index)
        self.event('<ButtonRelease-1>', index)

    def test_click_reads_without_selecting(self):
        self.assertFalse(self.ui.batch_mode)
        self.assertFalse(self.ui.batch_rows[0].winfo_ismapped())
        self.click()
        self.ui.app.read_comic.assert_called_once_with(self.keys[0])
        self.assertFalse(self.ui.tree.selection())

    def test_long_press_selects_and_release_does_not_read(self):
        self.event('<ButtonPress-1>')
        end = time.monotonic()+.56
        while time.monotonic()<end:
            self.root.update()
            time.sleep(.01)
        self.event('<ButtonRelease-1>')
        self.assertTrue(self.ui.batch_mode)
        self.assertEqual(self.ui.tree.selection(), (self.keys[0],))
        self.ui.app.read_comic.assert_not_called()
        self.assertTrue(self.ui.batch_rows[0].winfo_ismapped())
        self.click(1)
        self.assertEqual(set(self.ui.tree.selection()), set(self.keys[:2]))
        self.assertEqual(str(self.ui.action_buttons['export']['state']), 'disabled')

    def test_motion_cancels_both_click_and_hold(self):
        self.event('<ButtonPress-1>')
        self.event('<B1-Motion>', dx=25)
        self.ui.long_press()
        self.event('<ButtonRelease-1>', dx=25)
        self.assertFalse(self.ui.batch_mode)
        self.ui.app.read_comic.assert_not_called()

    def test_scroll_filter_and_busy_cancel_pending_press(self):
        for cancel in ('scroll', 'filter', 'busy'):
            self.ui.busy = False
            self.ui.query.set('')
            self.event('<ButtonPress-1>')
            if cancel == 'scroll':
                self.ui.tree.event_generate('<MouseWheel>', delta=-120)
            elif cancel == 'filter':
                self.ui.query.set('Comic')
            else:
                self.ui.busy = True
            self.ui.long_press()
            self.event('<ButtonRelease-1>')
            self.assertFalse(self.ui.batch_mode)
        self.ui.busy = False
        self.ui.app.read_comic.assert_not_called()

    def test_batch_exit_selection_refresh_and_shortcuts(self):
        self.ui.enter_batch(self.keys[0])
        self.ui.select('all')
        self.assertEqual(len(self.ui.tree.selection()), 3)
        self.ui.select('invert')
        self.assertFalse(self.ui.tree.selection())
        self.ui.tree.focus(self.keys[1])
        self.ui.keyboard_activate()
        self.assertEqual(self.ui.tree.selection(), (self.keys[1],))
        self.ui.render()
        self.assertEqual(self.ui.tree.selection(), (self.keys[1],))
        self.ui.query.set('Comic 0')
        self.assertFalse(self.ui.tree.selection())
        self.ui.exit_batch()
        self.root.update()
        self.assertFalse(self.ui.batch_mode)
        self.assertFalse(self.ui.batch_rows[0].winfo_ismapped())
        self.ui.app.read_comic.assert_not_called()

    def test_repeat_long_press_preserves_other_selections(self):
        self.ui.enter_batch(self.keys[0])
        self.ui.enter_batch(self.keys[1])
        self.ui.enter_batch(self.keys[0])
        self.assertEqual(set(self.ui.tree.selection()), set(self.keys[:2]))
        self.ui.exit_batch()
        self.ui.tree.focus(self.keys[0])
        self.ui.keyboard_activate()
        self.ui.app.read_comic.assert_called_once_with(self.keys[0])

    def test_double_click_only_opens_once(self):
        self.event('<ButtonPress-1>')
        self.event('<ButtonRelease-1>')
        self.event('<ButtonPress-1>')
        self.event('<ButtonRelease-1>')
        self.ui.app.read_comic.assert_called_once_with(self.keys[0])

    def test_rapid_batch_clicks_each_toggle(self):
        self.ui.enter_batch()
        self.event('<ButtonPress-1>')
        self.event('<ButtonRelease-1>')
        self.assertEqual(self.ui.tree.selection(), (self.keys[0],))
        self.event('<ButtonPress-1>')
        self.event('<ButtonRelease-1>')
        self.assertFalse(self.ui.tree.selection())
        self.ui.app.read_comic.assert_not_called()

    def test_column_resize_remains_available(self):
        tree = self.ui.tree
        x = tree.column('#0', 'width') + tree.column('favorite', 'width')
        before = tree.column('favorite', 'width')
        for name, offset in (('<ButtonPress-1>', 0), ('<B1-Motion>', 30), ('<ButtonRelease-1>', 30)):
            tree.event_generate(name, x=x+offset, y=10)
            self.root.update()
        self.assertGreater(tree.column('favorite', 'width'), before)
        self.assertFalse(self.ui.batch_mode)
        self.ui.app.read_comic.assert_not_called()


if __name__ == '__main__':
    unittest.main()
