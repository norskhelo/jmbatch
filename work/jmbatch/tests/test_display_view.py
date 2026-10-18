"""Real Tk tests: both presentations act on the same comic/task identities."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from display_view import DisplayView, load_mode, save_mode
from tests import test_library_interaction as interaction


class TileLibraryInteractionTest(interaction.LibraryInteractionTest):
    def setUp(self):
        super().setUp()
        self.ui.display_mode.set('tiles')
        self.ui.change_display()
        self.root.update()

    def test_column_resize_remains_available(self):
        # Tile columns reflow with the viewport; list header resize is tested by the base class.
        self.assertGreater(self.ui.tree.columns, 1)
        self.ui.window.geometry('1400x640')
        self.root.update()
        self.assertGreaterEqual(self.ui.tree.columns, 5)
        self.assertEqual(self.ui.tree.get_children(), self.keys)

    def test_toggle_preserves_filters_choices_and_read_target(self):
        self.ui.enter_batch(self.keys[1])
        self.ui.query.set('Comic')
        self.ui.enter_batch(self.keys[1])
        for mode in ('list', 'tiles', 'list', 'tiles'):
            self.ui.display_mode.set(mode)
            self.ui.change_display()
            self.root.update()
            self.assertTrue(self.ui.batch_mode)
            self.assertEqual(self.ui.tree.selection(), (self.keys[1],))
            self.assertEqual(self.ui.query.get(), 'Comic')
        self.ui.exit_batch()
        self.root.update()
        self.click(1)
        self.ui.app.read_comic.assert_called_once_with(self.keys[1])


class DisplayViewTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('900x550')
        self.view = DisplayView(self.root, kind='downloads', columns=tuple('abcdefg'), selectmode='extended')
        self.view.pack(fill='both', expand=True)
        for n in range(100):
            self.view.insert('', 'end', iid=str(n), values=(f'JM{n}', '长标题'*60, '下载中', '25% · 1/4', '12 MiB', 'ZIP', '0'))
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_anchor_selection_updates_and_virtualization(self):
        self.view.yview_moveto(.4)
        self.view.selection_set(('40', '43'))
        self.view.focus('43')
        self.view.set_mode('tiles')
        self.root.update()
        self.assertIn('40', self.view.visible_keys())
        self.assertEqual(self.view.selection(), ('40', '43'))
        self.assertLess(len(self.view.canvas.find_all()), 120)
        self.view.item('40', values=('JM40', 'Updated', '下载完成', '100%', '48 MiB', 'ZIP', '0'))
        self.root.update()
        painted=[self.view.canvas.itemcget(item, 'text') for item in self.view.canvas.find_all() if self.view.canvas.type(item)=='text']
        self.assertTrue(any('Updated' in text and '100%' in text for text in painted))
        self.view.set_mode('list')
        self.root.update()
        self.assertEqual(self.view.focus(), '43')
        self.assertEqual(self.view.selection(), ('40', '43'))
        self.assertIn('40', self.view.visible_keys())

    def test_second_column_hit_ctrl_select_and_delete(self):
        self.view.set_mode('tiles')
        self.root.update()
        for key, state in (('0', 0), ('1', 4)):
            x,y,w,h=self.view.bbox(key)
            self.view.event_generate('<ButtonPress-1>', x=x+20, y=y+20, state=state)
            self.root.update()
        self.assertEqual(self.view.selection(), ('0','1'))
        self.assertEqual(self.view.identify_at(self.view.cell_width+20, 20), '1')
        self.view.delete(*self.view.get_children())
        self.root.update()
        self.assertFalse(self.view.visible_keys())
        self.assertEqual(self.view.identify_at(20,20), '')

    def test_hidden_list_cannot_replace_tile_scrollbar_position(self):
        positions=[]
        self.view.configure(yscrollcommand=lambda a,b:positions.append((float(a),float(b))))
        self.view.set_mode('tiles')
        self.view.yview_moveto(.4)
        self.root.update()
        self.view.insert('', 'end', iid='new', values=('JMnew','New','等待','0%','—','ZIP','0'))
        self.root.update()
        self.assertEqual(positions[-1],self.view.canvas.yview())
        self.view._list_scrolled('0','0.01')
        self.assertEqual(positions[-1],self.view.canvas.yview())

    def test_preferences_are_independent_and_invalid_values_default(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            self.assertEqual(load_mode(home,'library'), 'list')
            save_mode(home,'library','tiles')
            save_mode(home,'downloads','list')
            self.assertEqual(load_mode(home,'library'),'tiles')
            self.assertEqual(load_mode(home,'downloads'),'list')
            (home/'display.json').write_text('broken',encoding='utf-8')
            self.assertEqual(load_mode(home,'library'),'list')
