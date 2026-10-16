"""Open the real reader with generated test pages and isolated state."""
import io
import os
import sys
import zipfile
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[3]
ROOT=PROJECT/'work/tests/reader-preview'
ROOT.mkdir(parents=True,exist_ok=True)
os.environ['JM_BATCH_HOME']=str(ROOT/'state')
sys.path.insert(0,str(PROJECT/'work/jmbatch'))
from PIL import Image,ImageDraw,ImageFont
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',42)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',24)
path=ROOT/'JM100001-阅读器测试.zip'
with zipfile.ZipFile(path,'w') as archive:
    for index in range(6):
        chapter,page=index//3+1,index%3+1
        image=Image.new('RGB',(750,1050),('#e6eff5','#e8e3d8','#dfebe5')[page-1])
        draw=ImageDraw.Draw(image)
        draw.text((52,50),'JM Batch · 阅读器测试',font=font,fill='#1d3549')
        draw.text((52,120),f'第 {chapter} 章 / 第 {page} 页 · 总第 {index+1} 页',font=small,fill='#3b5e70')
        for i in range(3):
            y=210+i*245
            draw.rounded_rectangle((50,y,700,y+210),radius=12,fill='white',outline='#7b9aa9',width=3)
            draw.text((82,y+80),f'示例分格 {i+1} · 用于阅读布局验证',font=small,fill='#3b5e70')
        draw.text((52,1000),'此页为生成的测试素材',font=small,fill='#3b5e70')
        data=io.BytesIO();image.save(data,'JPEG',quality=94)
        archive.writestr(f'{chapter:04d}/{page:05d}.jpg',data.getvalue())
import tkinter as tk
from app import App
from core import Task,Settings
root=tk.Tk();app=App(root,ROOT/'state')
for timer in root.tk.call('after','info'):root.after_cancel(timer)
task=Task('100001',Settings(output=str(ROOT),format='zip').__dict__)
task.status,task.title,task.result='done','阅读器测试（隔离示例）',str(path)
app.engine.tasks=[task];app.engine.library.sync([task])
reader=app.read_comic(app.engine.library.key(path));root.withdraw()
reader.window.geometry('1000x820+100+50')
def close():
    reader.close();root.destroy()
reader.window.protocol('WM_DELETE_WINDOW',close)
root.after(600000,close)
root.mainloop()
