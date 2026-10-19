"""Real Tk tests: both presentations act on the same comic/task identities."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from PIL import Image, ImageTk
from display_view import DisplayView, load_mode, save_mode
from tests import test_library_interaction as interaction


class TileLibraryInteractionTest(interaction.LibraryInteractionTest):
    def setUp(self):
        super().setUp()
        self.ui.display_mode.set('tiles')
        self.ui.change_display()
        self.root.update()

    def test_column_resize_remains_available(self):
        for width in (680, 980, 1400):
            self.ui.window.geometry(f'{width}x640')
            self.root.update()
            self.assertEqual(self.ui.tree.columns, 4)
            boxes = [self.ui.tree.bbox(key) for key in self.keys]
            self.assertEqual(len({box[1] for box in boxes}), 1)
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
        self.view = DisplayView(self.root, kind='library', columns=tuple('abcd'), selectmode='extended')
        self.view.pack(fill='both', expand=True)
        for n in range(100):
            self.view.insert('', 'end', iid=str(n), values=('', str(n), '长标题'*60, 'ZIP'))
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
        self.view.item('40', values=('★', '40', 'Updated', 'ZIP'))
        self.root.update()
        painted=[self.view.canvas.itemcget(item, 'text') for item in self.view.canvas.find_all() if self.view.canvas.type(item)=='text']
        self.assertTrue(any('Updated' in text and 'JM40' in text for text in painted))
        self.view.set_mode('list')
        self.root.update()
        self.assertEqual(self.view.focus(), '43')
        self.assertEqual(self.view.selection(), ('40', '43'))
        self.assertIn('40', self.view.visible_keys())

    def test_second_column_hit_ctrl_select_and_delete(self):
        self.view.set_mode('tiles')
        self.root.update()
        self.assertEqual(self.view.columns, 4)
        self.assertEqual(self.view.bbox('0')[1], self.view.bbox('3')[1])
        self.assertGreater(self.view.bbox('4')[1], self.view.bbox('0')[1])
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
        self.view.insert('', 'end', iid='new', values=('','new','New','ZIP'))
        self.root.update()
        self.assertEqual(positions[-1],self.view.canvas.yview())
        self.view._list_scrolled('0','0.01')
        self.assertEqual(positions[-1],self.view.canvas.yview())

    def test_covers_fill_resized_cards_and_reuse_only_visible_images(self):
        pictures = [ImageTk.PhotoImage(Image.new('RGB', size, color), master=self.root)
                    for size, color in (((72,96), 'red'), ((72,36), 'green'), ((24,96), 'blue'))]
        for n, picture in enumerate(pictures):
            self.view.item(str(n), image=picture)
        self.view.set_mode('tiles')
        for width in (360, 900, 1400, 360):
            self.root.geometry(f'{width}x550')
            self.root.update()
            self.assertEqual(self.view.columns, 4)
            self.assertAlmostEqual(self.view.cover_height/self.view.cover_width, 4/3, delta=.02)
            painted = [i for i in self.view.canvas.find_all() if self.view.canvas.type(i) == 'image']
            self.assertEqual(len(painted), 3)
            for n, item in enumerate(painted):
                left, top, right, bottom = self.view.canvas.bbox(item)
                x,y,w,h = self.view.bbox(str(n))
                self.assertGreaterEqual(left, x+14)
                self.assertLessEqual(right, x+w-14)
                self.assertGreaterEqual(top, y+14)
                self.assertLessEqual(bottom, y+16+self.view.cover_height)
                self.assertEqual((right-left,bottom-top), (self.view.cover_width,self.view.cover_height))
            cached = dict(self.view.tile_images)
            self.view.item('0', values=('', '0', 'Refreshed', 'ZIP'))
            self.root.update()
            self.assertEqual(cached, self.view.tile_images)
        self.view.yview_moveto(.8)
        self.root.update()
        self.assertFalse(self.view.tile_images)
        self.view.set_mode('list')
        self.root.update()
        self.assertEqual(self.view.item('0', 'image'), (str(pictures[0]),))
        self.assertEqual((pictures[0].width(), pictures[0].height()), (72,96))

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

    def test_comic_and_collection_tiles_use_same_center_fill(self):
        image = Image.new('RGB', (240, 96), 'red')
        image.paste('green', (84, 0, 156, 96))
        image.paste('blue', (156, 0, 240, 96))
        picture = ImageTk.PhotoImage(image, master=self.root)
        self.view.item('0', image=picture)
        self.view.item('1', image=picture, values=('', '1', 'Folder', '收藏夹'))
        self.view.set_mode('tiles')
        self.root.update()
        painted = [i for i in self.view.canvas.find_all() if self.view.canvas.type(i) == 'image']
        photos = {str(photo): ImageTk.getimage(photo) for photo in self.view.tile_images.values()}
        comic, folder = [photos[self.view.canvas.itemcget(i, 'image')] for i in painted]
        self.assertEqual(comic.getpixel((comic.width//2,comic.height//2))[:3], (0,128,0))
        self.assertEqual(comic.size, (self.view.cover_width,self.view.cover_height))
        self.assertEqual(folder.size,comic.size)
        self.assertEqual(folder.tobytes(),comic.tobytes())
