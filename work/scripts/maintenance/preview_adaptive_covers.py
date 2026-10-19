"""Show the real library with isolated first-page orientation fixtures."""
from pathlib import Path
from types import SimpleNamespace
import io
import os
import sys
import zipfile
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
scratch = ROOT / 'work/tests/adaptive-cover-preview'
scratch.mkdir(parents=True, exist_ok=True)
os.environ['JM_BATCH_HOME'] = str(scratch / 'state')
sys.path.insert(0, str(ROOT / 'work/jmbatch'))
from library import Library
from library_ui import LibraryWindow

library = Library(scratch / 'state')
library.entries = {}
library.collections = {}
font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 44)
small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 24)
samples = [('竖图 · 星海旅人',480,640,'#263c62','#5d8eaa'),
           ('横图 · 中央灯塔',960,640,'#b9dbe1','#477f97'),
           ('竖图 · 山间来信',480,640,'#cdd9c4','#688d76'),
           ('宽横图 · 中央小屋',1280,640,'#ecd2b0','#ad7e68')]
for n,(title,w,h,bg,fg) in enumerate(samples):
    image = Image.new('RGB',(w,h),bg);d=ImageDraw.Draw(image)
    d.ellipse((w/2-65,135,w/2+65,265),fill='#f6dfa3')
    d.polygon([(0,440),(w*.3,300),(w*.6,430),(w,330),(w,h),(0,h)],fill=fg)
    d.polygon([(0,545),(w*.45,440),(w*.7,530),(w,460),(w,h),(0,h)],fill='#36576b')
    d.rectangle((w/2-42,360,w/2+42,530),fill='#f5ead8')
    d.polygon([(w/2-60,365),(w/2,310),(w/2+60,365)],fill='#a45448')
    d.rectangle((w/2-12,465,w/2+12,530),fill='#668a95')
    d.text((w/2,55),title.split(' · ')[1],font=font,anchor='mt',fill='#ffffff')
    d.text((w/2,580),'第一页 / 演示图片',font=small,anchor='mt',fill='white')
    if w>h:
        d.rectangle((0,0,110,h),fill='#c36b65');d.rectangle((w-110,0,w,h),fill='#6278a9')
        d.text((18,300),'左侧',font=small,fill='white');d.text((w-90,300),'右侧',font=small,fill='white')
    image.save(scratch/f'first-page-{n+1}.png')
    data=io.BytesIO();image.save(data,format='PNG')
    path=scratch/f'JM{100001+n}.zip'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('00001.png',data.getvalue())
        archive.writestr('00002.png',b'not used as cover')
    key=library.key(path)
    library.entries[key]=dict(id=str(100001+n),title=title,path=str(path),root=str(scratch),format='zip',favorite=False)

root=tk.Tk();root.withdraw()
app=SimpleNamespace(root=root,engine=SimpleNamespace(library=library,tasks=[]),read_comic=lambda key:None)
ui=LibraryWindow(app)
ui.window.title('JM Batch · 首图自适应封面预览（演示数据）')
ui.window.geometry('1060x660+80+80')
ui.display_mode.set('tiles');ui.change_display()
ui.window.protocol('WM_DELETE_WINDOW',root.destroy)
print('PREVIEW_READY',flush=True)
root.mainloop()
