"""Offline source/frozen checks of the actual library and download cover binders."""
import io
import time
import tkinter as tk
import zipfile
from tkinter import ttk
from types import SimpleNamespace
from PIL import Image, ImageTk


def check_cover_displays(root, directory):
    from core import Settings, Task
    from cover_cache import CoverCache
    from collection_covers import load_collection_cover
    from download_covers import DownloadCovers
    from library import Library
    from library_ui import LibraryWindow
    directory.mkdir(parents=True,exist_ok=True)
    source=Image.new('RGB',(240,96),'red')
    source.paste('green',(72,0,168,96));source.paste('blue',(168,0,240,96))
    data=io.BytesIO();source.save(data,format='PNG')
    path=directory/'wide-first-page.zip'
    with zipfile.ZipFile(path,'w') as archive:archive.writestr('00001.png',data.getvalue())
    original=path.read_bytes()
    cache=CoverCache(directory);raw=cache.load(path,'zip')
    assert raw.width/raw.height>2
    cached=cache.file(path,'zip').read_bytes()

    def wait(predicate,poll=lambda:None):
        until=time.monotonic()+6
        while time.monotonic()<until:
            root.update();poll()
            if predicate():return
            time.sleep(.02)
        raise AssertionError('Cover binding timed out')

    def green(photo,size):
        image=ImageTk.getimage(photo);assert image.size==size
        for xy in ((4,4),(size[0]//2,size[1]//2),(size[0]-5,size[1]-5)):
            assert image.getpixel(xy)[:3]==(0,128,0)

    checks=[]
    library=Library(directory);key=library.key(path)
    library.entries[key]=dict(path=str(path),root=str(directory),id='123456',title='Synthetic cover',format='zip',favorite=False)
    app=SimpleNamespace(root=root,engine=SimpleNamespace(library=library,tasks=[]),read_comic=lambda key:None)
    ui=LibraryWindow(app)
    try:
        wait(lambda:key in ui.cover_images and ui.cover_images[key] is not ui.cover_placeholder)
        green(ui.cover_images[key],(72,96))
        assert cache.file(path,'zip').read_bytes()==cached
        checks.append('Actual library list center-fills a previously cached landscape first page')
    finally:
        ui.window.destroy();root.update()

    popup=tk.Toplevel(root);popup.geometry('500x300')
    tree=ttk.Treeview(popup);tree.pack(fill='both',expand=True)
    task=Task('123456',Settings(format='zip',output=str(directory)).__dict__,status='done')
    task.result=str(path)
    covers=DownloadCovers(tree,directory)
    try:
        tree.insert('','end',iid=task.key,text='Synthetic task',image=covers.placeholder)
        root.update()
        wait(lambda:task.key in covers.images and covers.images[task.key][1],lambda:covers.poll([task]))
        green(covers.images[task.key][2],(54,72))
        checks.append('Actual download list center-fills a completed task cover using its cached source')
    finally:
        popup.destroy();root.update()

    preview=load_collection_cover([(str(path),'zip')]*4,cache.load)
    for xy in ((20,30),(52,30),(20,70),(52,70)):
        assert preview.getpixel(xy)==(0,128,0)
    assert path.read_bytes()==original and cache.file(path,'zip').read_bytes()==cached
    checks.append('All four collection cells center-fill while preserving the source archive and disk thumbnail')
    return checks
