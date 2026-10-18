"""Batch exports against real folder/ZIP/PDF fixtures and the persistent library."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pypdf import PdfReader
from albums import export_album, read_album
from batch_export import export_many
from core import Settings, Task
from diagnostics import FixtureClient
from library import Library
from worker import run_download


class BatchExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, JM_BATCH_HOME=str(self.root/'state'))
        self.env.start()
        self.library = Library(self.root/'state')
        self.folders = []
        for identifier in ('123456', '123457'):
            task = Task(identifier, Settings(download_all_chapters=True, output=str(self.root/'sources')).__dict__)
            events = []
            run_download(task.to_dict(), '', events.append, FixtureClient)
            self.folders.append(Path(events[-1]['path']))
        self.library.import_found(self.library.discover(self.root/'sources')[0])
        self.keys = [self.library.key(p) for p in self.folders]
        self.output = self.root/'exports'
        self.originals = self.digest()

    def tearDown(self):
        self.assertEqual(self.digest(), self.originals)
        self.env.stop()
        self.temp.cleanup()

    def digest(self):
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in self.folders for p in folder.rglob('*') if p.is_file()}

    def mixed(self):
        files = [self.folders[0], export_album(self.folders[0], self.root/'zip', 'zip')[0],
                 export_album(self.folders[1], self.root/'pdf', 'pdf')[0]]
        for parent in (self.root/'zip', self.root/'pdf'):
            self.library.import_found(self.library.discover(parent)[0])
        return [self.library.key(p) for p in files]

    def test_mixed_formats_to_each_format_and_split_pdf(self):
        keys = self.mixed()
        for fmt, expected in (('pdf', [3, 2, 3, 2, 5]), ('zip', [5, 5, 5]), ('images', [5, 5, 5])):
            with self.subTest(fmt=fmt):
                messages = []
                result = export_many(self.library, keys, self.output/fmt, fmt, split_pdf=True, progress=messages.append)
                self.assertEqual((result.succeeded, result.failed, result.unprocessed), (3, 0, 0))
                self.assertFalse(result.errors or result.warnings)
                sizes = []
                for p in result.paths:
                    self.assertIn(self.library.key(p), Library(self.root/'state').entries)
                    if fmt == 'pdf': sizes.append(len(PdfReader(p).pages))
                    elif fmt == 'images': sizes.append(len(read_album(p, verify=True)[1]))
                    else:
                        with zipfile.ZipFile(p) as z:
                            self.assertIsNone(z.testzip())
                            sizes.append(len(z.namelist()))
                self.assertEqual(sizes, expected)
                self.assertTrue(any('第 3/3 本' in m for m in messages))

    def test_collision_does_not_overwrite_or_prevent_next_comic(self):
        self.output.mkdir()
        existing = self.output/'123456.pdf'
        existing.write_bytes(b'existing document')
        result = export_many(self.library, self.keys, self.output, 'pdf', numeric=True)
        self.assertEqual((result.succeeded, result.failed, result.unprocessed), (1, 1, 0))
        self.assertEqual(existing.read_bytes(), b'existing document')
        self.assertEqual([p.name for p in result.paths], ['123457.pdf'])
        self.assertIn('123456', result.errors[0])

    def test_missing_source_does_not_prevent_following_comic(self):
        bad = self.library.key(self.root/'missing.zip')
        self.library.entries[bad] = dict(path=bad, root=str(self.root), id='9', title='Missing', format='zip', favorite=False)
        result = export_many(self.library, [bad]+self.keys, self.output, 'zip')
        self.assertEqual((result.succeeded, result.failed, result.unprocessed), (2, 1, 0))
        self.assertIn('Missing', result.errors[0])

    def test_cancel_mid_comic_rolls_back_current_and_indexes_completed(self):
        stopped = False
        def progress(message):
            nonlocal stopped
            if '第 2/2 本' in message and '保存图片 2/' in message:
                stopped = True
        result = export_many(self.library, self.keys, self.output, 'images', progress=progress, cancelled=lambda: stopped)
        self.assertEqual((result.succeeded, result.failed, result.unprocessed), (1, 0, 1))
        self.assertTrue(result.stopped)
        self.assertEqual(list(self.output.iterdir()), result.paths)
        self.assertEqual(len(read_album(result.paths[0], verify=True)[1]), 5)
        self.assertIn(self.library.key(result.paths[0]), self.library.entries)

    def test_cancel_before_start_produces_nothing(self):
        result = export_many(self.library, self.keys, self.output, 'zip', cancelled=lambda: True)
        self.assertEqual((result.succeeded, result.failed, result.unprocessed), (0, 0, 2))
        self.assertTrue(result.stopped)
        self.assertFalse(self.output.exists())

    def test_selection_is_deduplicated_and_snapshotted(self):
        selected = self.keys + self.keys[:1]
        result = export_many(self.library, selected, self.output, 'zip', progress=lambda _: selected.clear())
        self.assertEqual(result.succeeded, 2)
        self.assertEqual(len(result.paths), 2)

    def test_index_failure_is_warning_and_saved_files_survive(self):
        with patch.object(self.library, 'import_found', side_effect=OSError('catalogue locked')):
            result = export_many(self.library, self.keys, self.output, 'pdf')
        self.assertEqual((result.succeeded, result.failed), (2, 0))
        self.assertEqual(len(result.warnings), 1)
        self.assertTrue(all(p.is_file() for p in result.paths))

    def test_numeric_split_names_are_independent_for_each_book(self):
        result = export_many(self.library, self.keys, self.output, 'pdf', numeric=True, split_pdf=True)
        self.assertEqual(result.succeeded, 2)
        self.assertEqual([p.name for p in result.paths], ['123456-0001.pdf', '123456-0002.pdf', '123457-0001.pdf', '123457-0002.pdf'])


if __name__ == '__main__':
    unittest.main()
