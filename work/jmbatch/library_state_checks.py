"""Exercise retained library state with actual Tk windows and an offline reader."""
import time
from pathlib import Path
from types import SimpleNamespace


def check_library_state(root, directory):
    from PIL import Image
    from app import App
    from library import Library
    from reader_ui import open_reader

    home = Path(directory) / 'retained-library'
    home.mkdir(parents=True, exist_ok=True)
    library = Library(home)
    for n in range(40):
        folder = home / f'{n:03}'
        folder.mkdir(exist_ok=True)
        Image.new('RGB', (40, 60), (n * 5, 80, 120)).save(folder / '00001.jpg')
        key = library.key(folder)
        library.entries[key] = dict(path=str(folder), root=str(home), id=str(n),
                                    title=f'Comic {n:03}', format='images', favorite=True)
    library.save()
    host = SimpleNamespace(root=root, home=home, engine=SimpleNamespace(library=library, tasks=[]))
    host.read_comic = lambda key: open_reader(host, key)
    ui = None
    try:
        App.show_library(host)
        ui = host.library_window
        ui.query.set('Comic')
        ui.only_favorites.set(True)
        ui.render()
        ui.enter_batch()
        root.update()
        keys = ui.tree.get_children()
        key = keys[20]
        ui.tree.selection_set(key)
        ui.tree.focus(key)
        ui.tree.yview_moveto(.5)
        root.update()
        position, geometry = ui.tree.yview(), ui.window.geometry()
        reader = host.read_comic(key)
        deadline = time.monotonic() + 8
        while not reader.pages and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert reader.pages, 'offline reader did not open'
        for _ in range(3):
            assert host.read_comic(key) is reader
            App.show_library(host)
            root.update()
            assert host.library_window is ui and ui.window.winfo_exists()
            assert ui.tree.yview() == position and ui.window.geometry() == geometry
            assert ui.query.get() == 'Comic' and ui.only_favorites.get()
            assert ui.batch_mode and ui.tree.selection() == (key,) and ui.tree.focus() == key
        reader.close()
        root.update()
        assert ui.window.winfo_exists() and ui.tree.yview() == position
        # Reader favorites update the retained list without resetting its viewport.
        reader = host.read_comic(keys[0])
        reader.favorite()
        root.update()
        assert not ui.tree.exists(keys[0]) and ui.tree.bbox(key)[1] > 0
        assert ui.tree.selection() == (key,) and ui.tree.focus() == key
        top_y = ui.tree.bbox(key)[1]
        reader.favorite()
        root.update()
        assert ui.tree.exists(keys[0]) and ui.tree.bbox(key)[1] == top_y
        reader.close()
        # Removing the visible anchor keeps the nearest remaining row in place.
        library.entries.pop(key)
        ui.render()
        root.update()
        assert not ui.tree.selection() and ui.tree.bbox(keys[21])
        assert ui.batch_mode and ui.query.get() == 'Comic' and ui.only_favorites.get()
        ui.query.set('Comic 039')
        root.update()
        assert len(ui.tree.get_children()) == 1 and ui.tree.yview()[0] == 0
        ui.query.set('missing')
        root.update()
        assert not ui.tree.get_children()
    finally:
        for reader in list(getattr(host, 'readers', {}).values()):
            reader.close()
        if ui and ui.window.winfo_exists():
            ui.close()

