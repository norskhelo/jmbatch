import io
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from reader import ReaderSource, ReaderState, ReaderWorker


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.raw = io.BytesIO()
        Image.new("RGB", (600, 900), "red").save(self.raw, "JPEG")

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, names):
        path = self.root / "12345.zip"
        with zipfile.ZipFile(path, "w") as out:
            for name in names:
                out.writestr(name, self.raw.getvalue())
        return path

    def test_zip_natural_chapters_lazy_and_fit(self):
        path = self.archive(["chapter10/10.jpg", "chapter2/10.jpg", "chapter2/2.jpg"])
        source = ReaderSource(path)
        self.assertEqual([(p["chapter"], p["page"]) for p in source.pages], [(1, 1), (1, 2), (2, 1)])
        self.assertEqual(source.pages[0]["entry"].filename, "chapter2/2.jpg")
        self.assertEqual(list(self.root.iterdir()), [path])
        with source.render(0, 300) as image:
            self.assertEqual(image.size, (300, 450))
        with source.render(2, 300, 200) as image:
            self.assertLessEqual(image.height, 200)
        source.close()
        path.unlink()

    def test_folder_chapter_switching(self):
        path = self.root / "JM12345-reader-deadbeef"
        for chapter, count in ((1, 2), (2, 1)):
            folder = path / f"{chapter:04d}"
            folder.mkdir(parents=True)
            for page in range(1, count + 1):
                (folder / f"{page:05d}.jpg").write_bytes(self.raw.getvalue())
        source = ReaderSource(path)
        self.assertEqual([p["chapter"] for p in source.pages], [1, 1, 2])
        with source.render(2, 200) as image:
            self.assertEqual(image.width, 200)
        source.close()

    def test_pdf_single_chapter_render_and_close(self):
        path = self.root / "12345.pdf"
        Image.new("RGB", (240, 400), "blue").save(path, "PDF", save_all=True, append_images=[Image.new("RGB", (400, 240), "green")])
        source = ReaderSource(path)
        self.assertEqual([(p["chapter"], p["page"]) for p in source.pages], [(1, 1), (1, 2)])
        with source.render(1, 200, 300) as image:
            self.assertLessEqual(image.width, 200)
        source.close()
        path.unlink()

    def test_unsafe_zip_rejected_and_closed(self):
        path = self.archive(["../1.jpg"])
        with self.assertRaises(ValueError):
            ReaderSource(path)
        path.unlink()

    def test_bad_page_does_not_block_other_pages(self):
        path = self.archive(["1.jpg", "2.jpg"])
        with zipfile.ZipFile(path, "a") as out:
            out.writestr("3.jpg", b"bad")
        source = ReaderSource(path)
        with self.assertRaises(Exception):
            source.render(2, 200)
        with source.render(0, 200) as image:
            self.assertEqual(image.width, 200)
        source.close()

    def test_state_survives_restart_clamps_and_separates_books(self):
        state = ReaderState(self.root)
        state.put("a", 9, "paged", {2, 9})
        state.put("b", 1, "scroll", {1})
        loaded = ReaderState(self.root)
        self.assertEqual(loaded.get("a", 20), dict(page=9, mode="paged", bookmarks=[2, 9]))
        self.assertEqual(loaded.get("a", 5), dict(page=4, mode="paged", bookmarks=[2]))
        self.assertEqual(loaded.get("b", 20)["bookmarks"], [1])
        loaded.put("a", 3, "scroll", set())
        self.assertEqual(ReaderState(self.root).get("a", 20)["bookmarks"], [])

    def test_corrupt_state_preserved(self):
        path = self.root / "reader.json"
        path.write_text("broken", encoding="utf-8")
        state = ReaderState(self.root)
        with self.assertRaises(OSError):
            state.put("a", 0, "scroll", set())
        self.assertEqual(path.read_text(), "broken")

    def test_worker_renders_requested_page_and_releases_file(self):
        path = self.archive(["1.jpg", "2.jpg"])
        worker = ReaderWorker(path)
        self.assertEqual(worker.results.get(timeout=5)[0], "ready")
        worker.request([(7, 1, 200, 300)])
        kind, token, index, image = worker.results.get(timeout=5)
        self.assertEqual((kind, token, index), ("image", 7, 1))
        image.close()
        worker.close()
        for _ in range(50):
            try:
                path.unlink()
                break
            except PermissionError:
                time.sleep(.02)
        self.assertFalse(path.exists())

    def test_long_book_metadata_does_not_decode_all_pages(self):
        path = self.root / "long.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for index in range(7227):
                archive.writestr(f"{index+1:05d}.jpg", b"not-decoded-at-open")
        source = ReaderSource(path)
        self.assertEqual(len(source.pages), 7227)
        source.close()


if __name__ == "__main__":
    unittest.main()
