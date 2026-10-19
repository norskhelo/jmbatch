"""Open the actual Windows library using disposable, generated sample comics."""
from pathlib import Path
from types import SimpleNamespace
import io
import os
import sys
import zipfile
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
scratch = ROOT / 'work/tests/collections-preview'
scratch.mkdir(parents=True, exist_ok=True)
os.environ['JM_BATCH_HOME'] = str(scratch / 'state')
sys.path.insert(0, str(ROOT / 'work/jmbatch'))
from library import Library
from library_ui import LibraryWindow

library = Library(scratch / 'state')
library.entries = {}
library.collections = {}
font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 48)
small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 22)
titles = ['星海旅人', '山间来信', '远行日记', '落日航线', '雨后的街角', '周末小屋', '风中的约定', '春日列车']
palette = [('#222d50','#3c5680','#e2b96a'),('#bddbe1','#528596','#234d64'),('#d2d9cb','#8b9f86','#4b6559'),('#e8c5b6','#b57e75','#76505f'),('#e9d9c9','#9aa78f','#58796e'),('#efe1b9','#b8b391','#647569'),('#d4d5ec','#9b9bbf','#686b91'),('#cce2dc','#8bb4ac','#477c7c')]
keys = []
for i, (title, colors) in enumerate(zip(titles, palette)):
    image = Image.new('RGB', (480, 640), colors[0]);draw = ImageDraw.Draw(image)
    draw.ellipse((280, 170, 390, 280), fill='#f6e3b4')
    draw.polygon([(0,400),(150,290),(300,440),(480,310),(480,640),(0,640)], fill=colors[1])
    draw.polygon([(0,520),(210,390),(365,500),(480,430),(480,640),(0,640)], fill=colors[2])
    draw.text((32,55),title,font=font,fill='white' if i==0 else '#243c4b')
    draw.text((32,120),'JM BATCH / SAMPLE',font=small,fill='white' if i==0 else '#44616d')
    draw.text((32,585),'演示漫画',font=small,fill='white')
    data=io.BytesIO();image.save(data,format='JPEG',quality=94)
    path=scratch/f'JM{100001+i}-{title}.zip'
    with zipfile.ZipFile(path,'w') as archive:archive.writestr('00001.jpg',data.getvalue())
    key=library.key(path);keys.append(key)
    library.entries[key]=dict(id=str(100001+i),title=title,path=str(path),root=str(scratch),format='zip',favorite=i in (0,4,6))
first=library.create_collection('冒险故事');second=library.create_collection('日常小集')
library.move_to_collection(keys[:4],first);library.move_to_collection(keys[4:6],second)
root=tk.Tk();root.withdraw()
app=SimpleNamespace(root=root,engine=SimpleNamespace(library=library,tasks=[]),read_comic=lambda key:None)
ui=LibraryWindow(app)
ui.window.title('JM Batch 0.3.23 · 收藏夹效果预览（演示数据）')
ui.window.geometry('1000x640+100+100')
ui.display_mode.set('tiles');ui.change_display()
ui.window.protocol('WM_DELETE_WINDOW',root.destroy)
print('PREVIEW_READY',flush=True)
root.mainloop()
