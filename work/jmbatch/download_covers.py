"""Live queue thumbnails: inspect only the committed first page, off the UI thread."""
from collections import OrderedDict
from pathlib import Path
import queue
import time

from core import task_cache
from covers import CoverWorker, load_cover, fit_cover


def cover_identity(task):
    chosen = task.selected_chapters or [{"number": 1}]
    return (task.key, chosen[0]["number"], task.settings["format"], task.settings["output"])


def cover_source(task):
    chosen = task.get("selected_chapters") or [{"number": 1}]
    first = task_cache(task) / "images" / f"{chosen[0]['number']:04d}" / "00001.jpg"
    if first.is_file():
        path, fmt = first, "image"
    elif task.get("status") == "done" and task.get("result"):
        path, fmt = Path(task["result"]), task["settings"]["format"]
    else:
        return None
    stat = path.stat()
    return str(path), fmt, stat.st_mtime_ns, stat.st_size


class DownloadCoverLoader:
    def __init__(self, home=None):
        self.cache = OrderedDict()
        from cover_cache import CoverCache
        self.disk = CoverCache(home) if home is not None else None

    @staticmethod
    def preview_path(task):
        chosen = task.get('selected_chapters') or [{'number': 1}]
        return task_cache(task) / f"cover-{chosen[0]['number']}-{task['settings']['format']}"

    def restore(self, task):
        """No original-file access: startup displays the last known small preview."""
        if self.disk is None:
            return None
        try:
            saved = self.disk.peek(self.preview_path(task), 'download-preview')
            if saved and isinstance(saved[0], list) and len(saved[0]) == 4:
                return tuple(saved[0]), saved[1]
            # Reuse older releases' finished-comic cache on the first launch too.
            if task.get('status') == 'done' and task.get('result'):
                path, fmt = task['result'], task['settings']['format']
                saved = self.disk.peek(path, fmt)
                if saved and isinstance(saved[0], list) and len(saved[0]) == 2:
                    return (path, fmt, *saved[0]), saved[1]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def __call__(self, task, _fmt):
        try:
            source = cover_source(task)
        except (OSError, ValueError):
            source = None
        key = task["key"]
        previous = self.cache.get(key)
        now = time.monotonic()
        if previous and previous[0] == source and (previous[1] is not None or now - previous[2] < 3):
            self.cache.move_to_end(key)
            return previous[:2]
        loader = self.disk.load if self.disk is not None and source and source[1] != "image" else load_cover
        saved = self.restore(task) if source and previous is None else None
        # Only raw-page stamps fully describe the source. Finished albums may
        # have nested dependencies, which the shared cache must still validate.
        result = (saved[1] if saved and saved[0] == source and source[1] == 'image'
                  else loader(*source[:2]) if source else None)
        if result is not None and self.disk is not None:
            self.disk.remember_preview(self.preview_path(task), 'download-preview', source, result)
        self.cache[key] = (source, result, now)
        self.cache.move_to_end(key)
        while len(self.cache) > 64:
            self.cache.popitem(last=False)
        return source, result


class DownloadCovers:
    def __init__(self, tree, home=None):
        from PIL import Image, ImageDraw, ImageTk
        self.tree = tree
        placeholder = Image.new("RGB", (54, 72), "#e8edf1")
        draw = ImageDraw.Draw(placeholder)
        draw.rectangle((13, 14, 41, 58), outline="#96a6b2", width=2)
        for y in (28, 36, 44):
            draw.line((20, y, 34, y), fill="#96a6b2", width=2)
        self.placeholder = ImageTk.PhotoImage(placeholder, master=tree)
        self.loader = DownloadCoverLoader(home)
        self.worker = CoverWorker(self.loader)
        self.pending = set()
        self.images = OrderedDict()
        self.next_check = {}
        self.identities = {}
        tree.bind("<Destroy>", self.destroy, add="+")

    def destroy(self, event):
        if event.widget == self.tree:
            self.worker.close()
            self.images.clear()

    def poll(self, tasks):
        from PIL import ImageTk
        by_key = {task.key: task for task in tasks}
        identities = {key: cover_identity(task) for key, task in by_key.items()}
        self.pending.intersection_update(by_key)
        for index, (key, identity) in enumerate(identities.items()):
            if self.identities.get(key) != identity:
                self.images.pop(key, None)
                self.next_check.pop(key, None)
                self.pending.discard(key)
                if self.tree.exists(key):
                    self.tree.item(key, image=self.placeholder)
                    # Bound synchronous startup work to a screenful of private
                    # thumbnails; originals and remaining rows stay asynchronous.
                    loader = getattr(self, 'loader', None)
                    saved = loader.restore(by_key[key].to_dict()) if loader and index < 12 else None
                    if saved:
                        source, result = saved
                        photo = ImageTk.PhotoImage(fit_cover(result, (54, 72)), master=self.tree)
                        self.images[key] = (source, True, photo)
                        self.tree.item(key, image=photo)
        self.identities = identities
        for key in list(self.images):
            if key not in by_key:
                self.images.pop(key)
        self.next_check = {key: value for key, value in self.next_check.items() if key in by_key}
        try:
            while True:
                identity, key, (source, result) = self.worker.results.get_nowait()
                if identities.get(key) != identity:
                    continue
                self.pending.discard(key)
                if key not in by_key or not self.tree.exists(key):
                    continue
                previous = self.images.get(key)
                # Export removes the live page before the finished path reaches
                # the UI. Preserve the valid preview during that handoff/failure.
                if previous and previous[1] and result is None:
                    continue
                if previous and previous[0] == source and previous[1] == (result is not None):
                    continue
                if result is not None:
                    result = fit_cover(result, (54, 72))
                photo = ImageTk.PhotoImage(result, master=self.tree) if result is not None else self.placeholder
                self.images[key] = (source, result is not None, photo)
                self.tree.item(key, image=photo)
                while len(self.images) > 64:
                    old, _ = self.images.popitem(last=False)
                    if self.tree.exists(old):
                        self.tree.item(old, image=self.placeholder)
        except queue.Empty:
            pass
        now = time.monotonic()
        visible = self.tree.visible_keys() if hasattr(self.tree, "visible_keys") else dict.fromkeys(self.tree.identify_row(y) for y in range(0, self.tree.winfo_height(), 20))
        for key in visible:
            if key not in by_key or key in self.pending:
                continue
            if key in self.images:
                self.images.move_to_end(key)
            if now < self.next_check.get(key, 0):
                continue
            try:
                self.worker.jobs.put_nowait((identities[key], key, by_key[key].to_dict(), "task"))
            except queue.Full:
                break
            self.pending.add(key)
            self.next_check[key] = now + 1
