"""Prepare Windows 0.3.22 / Android 0.5.21 chapter deletion release."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.22 / Android 0.5.21 — 漫画库删除章节

## 更新内容

- 在漫画库长按或进入“批量处理”，选中一本漫画，点击“删除章节”；可一次勾选多个章节，显示每章页数，二次确认后执行。
- 支持图片文件夹与按章节目录保存的 ZIP；至少保留一章。PDF、单章漫画或平铺 ZIP 仅识别为一章，删除整本请使用“删除文件”。
- 先保存并校验保留章节，再切换漫画库记录并清理原文件。保留图片原始字节、漫画标题和收藏；文件名会更新，操作需要临时可用空间。图片目录剩余章节重新连续编号，仅剩一章时恢复为根目录图片布局。
- 剩余页的书签与阅读位置自动调整，已删除页的书签移除；正在阅读的页被删除时定位到后续保留页，末尾则回到最后保留页。封面和下载完成记录同步更新。
- 操作前须暂停下载；Windows 须先关闭本书阅读窗口。可在提交前停止，原漫画保留。拒绝修改含额外文件或链接的图片目录；保存或校验失败保留源文件。若旧文件清理失败，会明确提示其位置，保留已完成的新漫画。
- Android 同时支持应用下载目录和已授权的外部目录；保留原包名、APK 签名证书和更新公钥，可覆盖安装。

## 版本与验证

- Windows 0.3.21 → 0.3.22；Android 0.5.20 → 0.5.21（versionCode 521）。
- 验证覆盖多章/连续删章、旧目录布局、ZIP 字节保留、阅读位置/书签、取消、记录保存失败、外部存储重命名与清理失败，以及真实 Windows 章节选择界面；执行双端回归、自检、构建与签名核验。
- Android 使用 Android 10 框架和模拟存储服务验证，未连接真机；手机视觉、手势和各厂商存储服务行为仍需设备验收。
'''
folder=ROOT/'work/release-0322-0521';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=ROOT/'CHANGELOG.md';s=p.read_text(encoding='utf-8')
if not s.startswith(notes):p.write_text(notes+'\n'+s,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=ROOT/name;s=p.read_text(encoding='utf-8').replace('0.3.21','0.3.22').replace('0.5.20','0.5.21').replace('versionCode 520','versionCode 521').replace('versionCode="520"','versionCode="521"');p.write_text(s,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name;s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'));p.write_text(s,encoding='utf-8')
for name,number in (('work/jmbatch/README.txt','0.3.22'),('work/jmbatch-android/README.txt','0.5.21')):
    p=ROOT/name;s=p.read_text(encoding='utf-8');s=re.split(r'\n(?:Windows 0\.3\.\d+ / Android 0\.5\.\d+|Android 0\.5\.\d+) — ',s,maxsplit=1)[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+','JM Batch '+number,s)
    s=re.sub(r'release-(?:0\.3\.\d+-0\.5\.\d+|android-0\.5\.\d+)','release-0.3.22-0.5.21',s)
    s=re.sub(r'JMBatch-0\.3\.\d+-Windows','JMBatch-0.3.22-Windows',s);s=re.sub(r'JMBatch-0\.5\.\d+-Android','JMBatch-0.5.21-Android',s)
    p.write_text(s+'\n'+plain,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8')
s=re.sub(r'release-(?:0\.3\.21-0\.5\.19|android-0\.5\.20)','release-0.3.22-0.5.21',s)
s=s.replace('0.3.21','0.3.22').replace('0.5.20','0.5.21').replace('versionCode 520','versionCode 521')
s=s.replace('Android 图片文件夹复用索引，优先打开上次阅读页及后续页面，其余页面后台检查并显示进度。','双端漫画库支持选择并删除章节，自动调整阅读位置、书签及封面。')
section='## 删除章节\n\n在漫画库长按或进入“批量处理”，选中一本漫画后点击“删除章节”，勾选章节并再次确认。支持图片目录和分章 ZIP，至少保留一章；PDF、平铺 ZIP 或单章漫画请使用整本删除。先暂停下载，Windows 还须关闭本书阅读窗口。保留章节先保存校验，再替换漫画库记录并清理原文件，需要临时空间且文件名会更新；标题、收藏、保留页书签与阅读位置同步保留。提交前可停止；原文件清理失败时会提示位置。\n\n'
if '## 删除章节' not in s:s=s.replace('## 内置阅读器',section+'## 内置阅读器')
p.write_text(s,encoding='utf-8')
changes={'0.3.21':'0.3.22','0.5.19':'0.5.21','0321-0519':'0322-0521','<= 519':'<= 521','下载列表与漫画库四列平铺':'漫画库删除章节'}
pattern=re.compile('|'.join(map(re.escape,changes)))
for name in ('prepare_publication','publish'):
    p=ROOT/f'work/scripts/release/{name}_0321_0519.py'
    (p.parent/f'{name}_0322_0521.py').write_text(pattern.sub(lambda m:changes[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
print('Prepared 0.3.22 / 0.5.21 (521)')
