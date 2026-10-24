"""Category priority, per-category sorting and fixed ascending menu behavior."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from ui_library import sorted_items, sort_menu


class LibrarySortTest(TestCase):
    def setUp(self):
        self.items = [
            ('normal-b', dict(title='B', favorite=False)),
            ('fav-z', dict(title='Z', favorite=True)),
            ('folder-z', dict(title='Z folder', format='collection')),
            ('normal-a', dict(title='A', favorite=False)),
            ('folder-a', dict(title='A folder', format='collection')),
            ('fav-c', dict(title='C', favorite=True)),
        ]
        self.view = SimpleNamespace(sort_mode='name', sort_facts={},
                                    library=SimpleNamespace(entries={k:v for k,v in self.items if v.get('format')!='collection'}))

    def keys(self):
        return [key for key, _ in sorted_items(self.view, self.items)]

    def test_name_and_favorite_changes_preserve_category_priority(self):
        self.assertEqual(self.keys(), ['folder-a', 'folder-z', 'fav-c', 'fav-z', 'normal-a', 'normal-b'])
        self.items[1][1]['favorite'] = False
        self.assertEqual(self.keys(), ['folder-a', 'folder-z', 'fav-c', 'normal-a', 'normal-b', 'fav-z'])
        self.assertEqual(self.items[0][0], 'normal-b')  # Input order is not mutated.

    def test_numeric_modes_include_favorites_and_every_folder_member(self):
        self.view.sort_facts = {'normal-a': 5, 'normal-b': 2, 'fav-c': 8, 'fav-z': 4}
        for i in range(5):
            key = 'member-' + str(i)
            self.view.library.entries[key] = dict(collection='folder-a')
            self.view.sort_facts[key] = 10 if i == 4 else 1
        self.view.library.entries['member-z'] = dict(collection='folder-z')
        self.view.sort_facts['member-z'] = 6
        for key,item in self.view.library.entries.items():
            item['chapter_count']=self.view.sort_facts[key]
        for mode in ('time', 'size', 'chapters'):
            with self.subTest(mode=mode):
                self.view.sort_mode = mode
                self.assertEqual(self.keys(), ['folder-z', 'folder-a', 'fav-z', 'fav-c', 'normal-b', 'normal-a'])

    def test_empty_and_equal_values_use_name_within_each_group(self):
        self.view.sort_mode = 'size'
        self.assertEqual(self.keys(), ['folder-a', 'folder-z', 'fav-c', 'fav-z', 'normal-a', 'normal-b'])
        self.items = [pair for pair in self.items if pair[0].startswith('fav')]
        self.assertEqual(self.keys(), ['fav-c', 'fav-z'])

    def test_pinyin_names_apply_inside_all_groups_and_metadata_ties(self):
        self.items = [(str(i), dict(title=title, favorite=group==1,
                                  format='collection' if group==0 else 'images'))
                      for i, (group, title) in enumerate([
                          (2, '安白'), (1, '白安'), (0, '白安'),
                          (2, '安阿'), (1, '安阿'), (0, '安阿')])]
        for mode in ('name', 'size', 'time', 'chapters'):
            with self.subTest(mode=mode):
                self.view.sort_mode = mode
                self.view.library.entries = {}
                self.assertEqual(self.keys(), ['5', '2', '4', '1', '3', '0'])

    def test_selecting_same_mode_twice_keeps_ascending(self):
        self.view.window = Mock()
        self.view.sort_button = Mock()
        self.view.sort_button.winfo_rooty.return_value = 10
        self.view.sort_button.winfo_height.return_value = 20
        self.view.busy = False
        self.view.render = Mock()
        with patch('ui_library.tk.Menu') as factory:
            sort_menu(self.view)
            choose = factory.return_value.add_command.call_args_list[0].kwargs['command']
            choose()
            first = self.keys()
            choose()
            self.assertEqual(self.keys(), first)
            self.assertEqual(first, ['folder-a', 'folder-z', 'fav-c', 'fav-z', 'normal-a', 'normal-b'])

    def test_chapter_menu_uses_persisted_counts_without_background_loading(self):
        self.view.window=Mock();self.view.sort_button=Mock();self.view.busy=False
        self.view.sort_button.winfo_rooty.return_value=10
        self.view.sort_button.winfo_height.return_value=20
        self.view.render=Mock();self.view.run=Mock()
        with patch('ui_library.tk.Menu') as factory, patch('reader.ReaderSource',side_effect=AssertionError('sort opened a comic')):
            sort_menu(self.view)
            choose=factory.return_value.add_command.call_args_list[3].kwargs['command']
            for _ in range(3):choose()
        self.assertEqual(self.view.sort_mode,'chapters')
        self.view.run.assert_not_called()
        self.assertEqual(self.view.render.call_count,3)
