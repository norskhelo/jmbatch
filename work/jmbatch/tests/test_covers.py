import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import img2pdf
from PIL import Image
from covers import load_cover, image_entry, page_key, CoverWorker


class CoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pages = []
        for name, color in [('red', (240, 20, 20)), ('blue', (20, 20, 240))]:
            path = self.root / (name + '.jpg')
            Image.new('RGB', (600, 800), color).save(path)
            self.pages.append(path)

    def tearDown(self):
        self.temp.cleanup()

    def assertRed(self, image):
        self.assertIsNotNone(image)
        self.assertLessEqual(image.width, 72)
        self.assertLessEqual(image.height, 96)
        r, g, b = image.getpixel((image.width//2, image.height//2))
        self.assertGreater(r, 200)
        self.assertLess(b, 50)

    def test_first_page_of_flat_directory(self):
        folder = self.root / 'JM123456-Test-a1b2c3d4'
        folder.mkdir()
        (folder/'00002.jpg').write_bytes(self.pages[1].read_bytes())
        (folder/'00001.jpg').write_bytes(self.pages[0].read_bytes())
        self.assertRed(load_cover(folder, 'images'))
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ['00001.jpg', '00002.jpg'])

    def test_first_chapter_legacy_unsorted_manifest(self):
        folder = self.root / 'old';folder.mkdir()
        entries = []
        for chapter, page in [(2, self.pages[1]), (1, self.pages[0])]:
            target=folder/f'{chapter:04d}/00001.jpg';target.parent.mkdir();target.write_bytes(page.read_bytes())
            entries.append(dict(chapter=chapter, page=1, file=f'{chapter:04d}/00001.jpg', size=target.stat().st_size))
        (folder/'.jmbatch-album.json').write_text(json.dumps(dict(version=1, id='123456', title='Test', entries=entries)))
        self.assertRed(load_cover(folder, 'images'))

    def test_zip_uses_natural_page_order_and_skips_metadata(self):
        path=self.root/'test.zip'
        with zipfile.ZipFile(path,'w') as archive:
            for name, source in [('10/1.jpg',self.pages[1]), ('2/10.jpg',self.pages[1]), ('2/2.jpg',self.pages[0]), ('__MACOSX/1.jpg',self.pages[1]), ('../1.jpg',self.pages[1])]:
                archive.write(source,name)
        self.assertRed(load_cover(path,'zip'))

    def test_pdf_renders_first_page_and_releases_file(self):
        path=self.root/'test.pdf';path.write_bytes(img2pdf.convert(*map(str,self.pages)))
        self.assertRed(load_cover(path,'pdf'))
        path.unlink()
        self.assertFalse(path.exists())

    def test_corrupt_first_page_is_not_replaced_with_later_page(self):
        path=self.root/'test.zip'
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('1.jpg',b'broken');archive.write(self.pages[0],'2.jpg')
        self.assertIsNone(load_cover(path,'zip'))

    def test_missing_empty_and_corrupt_files_fall_back(self):
        self.assertIsNone(load_cover(self.root/'missing','images'))
        for fmt in ('zip','pdf'):
            path=self.root/('bad.'+fmt);path.write_bytes(b'broken')
            self.assertIsNone(load_cover(path,fmt))
        path=self.root/'empty.zip'
        with zipfile.ZipFile(path,'w'):pass
        self.assertIsNone(load_cover(path,'zip'))

    def test_zip_path_filter_and_large_numbers(self):
        for path in ('../1.jpg','/1.jpg','.hidden/1.jpg','__MACOSX/1.jpg','notes.json'):
            self.assertFalse(image_entry(path))
        self.assertTrue(image_entry('chapter/001.JPG'))
        self.assertLess(page_key('1/2.jpg'),page_key('1/100000000000000000000.jpg'))

    def test_worker_finishes_and_stops(self):
        path=self.root/'test.pdf';path.write_bytes(img2pdf.convert(str(self.pages[0])))
        worker=CoverWorker()
        try:
            worker.jobs.put((7,'key',path,'pdf'))
            generation,key,result=worker.results.get(timeout=10)
            self.assertEqual((generation,key),(7,'key'));self.assertRed(result)
        finally:worker.close()
        self.assertTrue(worker.closed.is_set())
