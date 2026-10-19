import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PIL import Image
from library import Library
from collection_covers import load_collection_cover


class CollectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.library = Library(self.temp.name)
        self.keys = []
        for i in range(6):
            path = str(Path(self.temp.name) / f'{i}.zip')
            key = self.library.key(path)
            self.keys.append(key)
            self.library.entries[key] = dict(path=path, root=self.temp.name, id=str(i), title=f'Comic {i}', format='zip', favorite=i == 0)
        self.library.save()

    def test_old_catalogue_migrates_without_moving_files_or_stars(self):
        data = json.loads(self.library.path.read_text(encoding='utf8'))
        data.pop('collections')
        self.library.path.write_text(json.dumps(data), encoding='utf8')
        library = Library(self.temp.name)
        self.assertFalse(library.error)
        self.assertEqual(len(library.browse()), 6)
        self.assertTrue(library.entries[self.keys[0]]['favorite'])
        folder = library.create_collection('待读')
        library.move_to_collection(self.keys[:2], folder)
        loaded = Library(self.temp.name)
        self.assertEqual(len(loaded.browse()), 5)
        self.assertEqual(len(loaded.browse(collection=folder)), 2)
        self.assertEqual(loaded.entries[self.keys[0]]['path'], self.library.entries[self.keys[0]]['path'])

    def test_moves_rename_delete_and_scanning_preserve_membership(self):
        first, second = self.library.create_collection('待读'), self.library.create_collection('已读')
        self.library.move_to_collection(self.keys[:3], first)
        self.library.import_found([dict(self.library.entries[self.keys[0]], collection='')])
        self.assertEqual(self.library.entries[self.keys[0]]['collection'], first)
        self.library.rename_collection(first, '旅途')
        self.library.move_to_collection(self.keys[:1], second)
        self.library.delete_collection(first)
        self.assertEqual(self.library.entries[self.keys[0]]['collection'], second)
        self.assertEqual(self.library.entries[self.keys[1]]['collection'], '')
        self.assertEqual(len(self.library.entries), 6)
        self.library.move_to_collection(self.keys[:1])
        self.assertTrue(self.library.entries[self.keys[0]]['favorite'])
        for name in ('', ' ', '漫画库', '已读', 'x'*41, 'a\nb'):
            with self.assertRaises(ValueError):
                self.library.create_collection(name)

    def test_save_failures_roll_back_all_in_memory_changes(self):
        folder = self.library.create_collection('待读')
        self.library.move_to_collection(self.keys[:2], folder)
        entries, collections = self.library.entries.copy(), self.library.collections.copy()
        disk = self.library.path.read_bytes()
        with patch('library.atomic_json', side_effect=OSError('disk full')):
            for operation in (lambda: self.library.create_collection('新的'), lambda: self.library.rename_collection(folder, '重命名'), lambda: self.library.delete_collection(folder), lambda: self.library.move_to_collection(self.keys[:1])):
                with self.assertRaises(OSError): operation()
                self.assertEqual(self.library.entries, entries)
                self.assertEqual(self.library.collections, collections)
                self.assertEqual(self.library.path.read_bytes(), disk)

    def test_search_can_find_folders_by_name_or_contained_comic(self):
        folder = self.library.create_collection('旅途')
        self.library.move_to_collection(self.keys[:2], folder)
        self.assertEqual([k for k, _ in self.library.browse('Comic 0')], [folder])
        self.assertEqual([k for k, _ in self.library.browse('旅途')], [folder])
        self.assertEqual([k for k, _ in self.library.browse(favorites=True)], [folder])
        self.assertEqual([k for k, _ in self.library.browse('Comic 0', collection=folder)], [self.keys[0]])
        self.assertEqual(self.library.browse('unmatched'), [])

    def test_task_sync_and_stars_keep_folder(self):
        folder = self.library.create_collection('待读')
        self.library.move_to_collection(self.keys[:1], folder)
        item = self.library.entries[self.keys[0]]
        task = SimpleNamespace(status='done', result=item['path'], album_id='0', title='updated', settings={'output': self.temp.name, 'format': 'zip'})
        self.library.sync([task])
        self.library.favorite(self.keys[0])
        self.library.set_favorites(self.keys[:1], True)
        self.assertEqual(self.library.entries[self.keys[0]]['collection'], folder)
        self.assertEqual(self.library.entries[self.keys[0]]['title'], 'updated')

    def test_preview_limit_empty_and_missing_covers(self):
        folder = self.library.create_collection('待读')
        self.library.move_to_collection(self.keys, folder)
        children = self.library.browse()[0][1]['path']
        self.assertEqual(len(children), 4)
        loader = Mock(side_effect=[Image.new('RGB', (72, 96), c) if c else None for c in ('red', None, 'blue', 'green')])
        image = load_collection_cover(children, loader)
        self.assertEqual(image.size, (72, 96))
        self.assertEqual(loader.call_count, 4)
        self.assertGreater(image.getpixel((16, 32))[0], 200)
        self.assertEqual(load_collection_cover([], loader).size, (72, 96))

    def test_unknown_collection_cannot_overwrite_catalogue(self):
        disk = self.library.path.read_bytes()
        with self.assertRaises(ValueError): self.library.move_to_collection(self.keys, 'missing')
        self.assertEqual(self.library.path.read_bytes(), disk)
        data = json.loads(disk)
        data['entries'][self.keys[0]]['collection'] = 'missing'
        self.library.path.write_text(json.dumps(data), encoding='utf8')
        loaded = Library(self.temp.name)
        self.assertTrue(loaded.error)
        with self.assertRaises(OSError): loaded.create_collection('fail')


class CollectionUiTest(unittest.TestCase):
    setUp = CollectionTest.setUp
    def test_folder_navigation_and_batch_actions_use_same_view(self):
        import tkinter as tk
        from library_ui import LibraryWindow
        folder = self.library.create_collection('待读')
        self.library.move_to_collection(self.keys[:2], folder)
        root = tk.Tk()
        try:
            app = SimpleNamespace(root=root, engine=SimpleNamespace(library=self.library, tasks=[]), read_comic=Mock())
            ui = LibraryWindow(app)
            root.update()
            self.assertIn(folder, ui.tree.get_children())
            ui.enter_batch(folder)
            self.assertEqual(str(ui.action_buttons['delete']['state']), 'disabled')
            ui.action('open')
            root.update()
            self.assertEqual(set(ui.tree.get_children()), set(self.keys[:2]))
            self.assertEqual(ui.collection, folder)
            app.read_comic.assert_not_called()
            ui.activate(self.keys[0])
            app.read_comic.assert_called_once_with(self.keys[0])
            ui.display_mode.set('tiles');ui.change_display();root.update()
            self.assertEqual(ui.tree.mode, 'tiles')
            ui.navigate('');root.update()
            self.assertIn(folder, ui.tree.get_children())
        finally:
            root.destroy()
