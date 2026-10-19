"""Pixel checks for center cropping and the actual library's cached list covers."""
import io
import tempfile
import time
import tkinter as tk
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageTk
from covers import fit_cover
from cover_cache import CoverCache
from collection_covers import load_collection_cover
from library import Library
from library_ui import LibraryWindow


def landscape():
    image=Image.new('RGB',(240,96),'red')
    image.paste('green',(72,0,168,96))
    image.paste('blue',(168,0,240,96))
    return image


class CoverPresentationTests(unittest.TestCase):
    def test_every_slot_fills_proportionally_from_center_and_preserves_source(self):
        for size in ((240,96),(48,192),(72,96)):
            image=landscape() if size[0]>size[1] else Image.new('RGB',size,'green')
            original=image.tobytes()
            for slot in ((54,72),(72,96),(56,70),(227,303)):
                result=fit_cover(image,slot)
                self.assertEqual(result.size,slot)
                self.assertEqual(result.getpixel((slot[0]//2,slot[1]//2)),(0,128,0))
                self.assertEqual(image.tobytes(),original)

    def test_collection_cells_fill_without_covering_neighbors_or_gaps(self):
        sources=[landscape(),Image.new('RGB',(48,192),'blue'),None,landscape()]
        preview=load_collection_cover([(n,'image') for n in range(4)],lambda n,fmt:sources[n])
        for xy in ((8,17),(31,47),(20,30),(40,55),(62,85)):
            # The composite is finally downsampled; allow its small filter halo.
            for actual,expected in zip(preview.getpixel(xy),(0,128,0)):
                self.assertAlmostEqual(actual,expected,delta=3)
        self.assertEqual(preview.getpixel((50,30)),(0,0,255))
        self.assertEqual(preview.getpixel((20,70)),(245,247,250))
        for actual,expected in zip(preview.getpixel((36,40)),(217,230,239)):
            self.assertAlmostEqual(actual,expected,delta=4)

    def test_library_list_uses_existing_uncropped_disk_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);path=home/'first.zip'
            data=io.BytesIO();landscape().save(data,format='PNG')
            with zipfile.ZipFile(path,'w') as archive:archive.writestr('00001.png',data.getvalue())
            cache=CoverCache(home);raw=cache.load(path,'zip')
            self.assertGreater(raw.width/raw.height,2)
            cached=cache.file(path,'zip').read_bytes()
            library=Library(home);key=library.key(path)
            library.entries[key]=dict(path=str(path),root=str(home),id='1',title='Landscape',format='zip',favorite=False)
            root=tk.Tk();root.withdraw()
            try:
                app=SimpleNamespace(root=root,engine=SimpleNamespace(library=library,tasks=[]),read_comic=lambda key:None)
                ui=LibraryWindow(app)
                until=time.monotonic()+5
                while (key not in ui.cover_images or ui.cover_images[key] is ui.cover_placeholder) and time.monotonic()<until:
                    root.update();time.sleep(.01)
                image=ImageTk.getimage(ui.cover_images[key])
                self.assertEqual(image.size,(72,96))
                for xy in ((4,4),(36,48),(67,91)):
                    self.assertEqual(image.getpixel(xy)[:3],(0,128,0))
                self.assertEqual(cache.file(path,'zip').read_bytes(),cached)
            finally:
                root.destroy()
