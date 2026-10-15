"""Run the actual library with isolated, generated sample pages for review."""
from pathlib import Path
import json
import os
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[3]
ROOT = PROJECT / 'work/tests/cover-preview'
ROOT.mkdir(parents=True, exist_ok=True)
os.environ['JM_BATCH_HOME'] = str(ROOT / 'state')
sys.path.insert(0, str(PROJECT / 'work/jmbatch'))

from PIL import Image, ImageDraw, ImageFont
import img2pdf
from covers import load_cover

font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 60)
small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 22)
palette = [('#bddbe1', '#528596', '#234d64', '海岸来信'),
           ('#222d50', '#3c5680', '#e2b96a', '星海旅人'),
           ('#e9d9c9', '#9aa78f', '#58796e', '雨后的街角')]
pages = []
for i, (background, middle, foreground, title) in enumerate(palette):
    image = Image.new('RGB', (600, 800), background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((330, 170, 470, 310), fill='#f6e3b4')
    draw.polygon([(0, 490), (180, 360), (360, 530), (600, 370), (600, 800), (0, 800)], fill=middle)
    draw.polygon([(0, 650), (260, 470), (460, 620), (600, 510), (600, 800), (0, 800)], fill=foreground)
    draw.text((50, 65), title, font=font, fill='white' if i == 1 else '#243c4b')
    draw.text((52, 145), 'JM BATCH / SAMPLE', font=small, fill='white' if i == 1 else '#44616d')
    draw.text((50, 725), '示例漫画 · 第一页', font=small, fill='white')
    page = ROOT / f'sample-{i}.jpg'
    image.save(page, quality=94)
    pages.append(page)

folder = ROOT / 'JM100001-海岸来信-a1b2c3d4'
folder.mkdir(exist_ok=True)
(folder / '00001.jpg').write_bytes(pages[0].read_bytes())
archive = ROOT / 'JM100002-星海旅人.zip'
with zipfile.ZipFile(archive, 'w') as bundle:
    bundle.write(pages[0], '0002/00001.jpg')
    bundle.write(pages[1], '0001/00001.jpg')
pdf = ROOT / 'JM100003-雨后的街角.pdf'
pdf.write_bytes(img2pdf.convert(str(pages[2]), str(pages[0])))
for path, fmt in ((folder, 'images'), (archive, 'zip'), (pdf, 'pdf')):
    thumb = load_cover(path, fmt)
    assert thumb is not None and thumb.width <= 72 and thumb.height <= 96, (path, fmt)
assert load_cover(ROOT / 'missing.pdf', 'pdf') is None

if '--check' in sys.argv:
    print('First-page image directory / multichapter ZIP / PDF / missing-file checks passed')
    raise SystemExit(0)

import tkinter as tk
from app import App
from core import Task, Settings

root = tk.Tk()
app = App(root, ROOT / 'state')
for timer in root.tk.call('after', 'info'):
    root.after_cancel(timer)
app.engine.tasks = []
app.engine.library.entries.clear()
for number, title, path, fmt in reversed([
    ('100001', '海岸来信', folder, 'images'),
    ('100002', '星海旅人', archive, 'zip'),
    ('100003', '雨后的街角', pdf, 'pdf'),
    ('100004', '暂时无法读取的漫画', ROOT / 'missing.zip', 'zip'),
]):
    task = Task(number, Settings(output=str(ROOT), format=fmt).__dict__)
    task.status, task.title, task.result = 'done', title, str(path)
    app.engine.tasks.append(task)
app.engine.library.sync(app.engine.tasks)
app.engine.library.set_favorites(list(app.engine.library.entries), True)
app.show_library()
ui = app.library_window
ui.window.title('JM Batch · 收藏封面预览（示例数据）')
ui.window.geometry('1000x780+100+80')
ui.only_favorites.set(True)
ui.render()
ui.status.set('封面默认取第一页；多章节取第一章第一页。无法读取时显示占位图。')
root.withdraw()
ui.window.protocol('WM_DELETE_WINDOW', root.destroy)

def verify_ui():
    assert len(ui.tree.get_children()) == 4
    assert len(ui.cover_images) == 4, 'All visible covers must finish loading'
    keys = ui.tree.get_children()
    assert all(ui.cover_images[k] != ui.cover_placeholder for k in keys[:3])
    assert ui.cover_images[keys[3]] == ui.cover_placeholder
    ui.select('all')
    assert len(ui.tree.selection()) == 4
    ui.select('none')
    (ROOT / 'preview-checks.json').write_text(json.dumps(dict(
        source='actual Windows Tk interface', samples_only=True,
        cover_formats=['images', 'zip', 'pdf'], failed_cover_placeholder=True,
        multi_selection=True, pushed=False), indent=2), encoding='utf-8')
    print('PREVIEW_READY', flush=True)

root.after(2500, verify_ui)
root.mainloop()
