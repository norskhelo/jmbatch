"""Prepare Windows 0.3.27 / Android 0.6.7 and matching local release recipes."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[3]
notes='''# Windows 0.3.27 / Android 0.6.7 — 全部封面统一自适应

## 更新内容

- Windows 与 Android 的全部封面统一使用漫画第一张图片，等比铺满各自封面框；竖图直接铺满，横图保留中央部分并左右对称裁切，不拉伸图像。
- 规则覆盖下载列表、漫画库列表与平铺，以及收藏夹内每张小封面。收藏夹各小封面分别在自己的框内裁切，不遮挡相邻封面。
- 继续复用现有封面缓存，无需清缓存或重新下载；保留占位、批量选择与阅读交互，不修改原漫画和正文阅读方式。

## 版本与验证

- Windows 0.3.26 → 0.3.27；Android 0.6.6 → 0.6.7（versionCode 607），保留原包名、APK 签名证书和更新公钥。
- 相关功能已通过 Windows 25 项检查、Android 20 项框架用例和 37 项行绑定检查，包含旧缓存复用、显示方式切换及收藏夹原生图形裁切。
- 本次执行双端构建、原签名核验，以及 Windows 源码和打包成品的封面专项检查；Android 未做真机验证。
'''
folder=ROOT/'work/release-0327-067';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=ROOT/'CHANGELOG.md';text=p.read_text(encoding='utf-8')
if text.startswith('# 未发布 — 全部封面统一自适应显示'):
    text=text[text.index('# Windows 0.3.26'):]
if not text.startswith(notes):p.write_text(notes+'\n'+text,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=ROOT/name;text=p.read_text(encoding='utf-8')
    text=text.replace('0.3.26','0.3.27').replace('0.6.6','0.6.7').replace('versionCode 606','versionCode 607').replace('versionCode="606"','versionCode="607"')
    p.write_text(text,encoding='utf-8')
plain=re.sub(r'(?m)^#{1,6} ','',notes).replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name;text=p.read_text(encoding='utf-8')
    text=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),text)
    p.write_text(text,encoding='utf-8')
for name,version in (('work/jmbatch/README.txt','0.3.27'),('work/jmbatch-android/README.txt','0.6.7')):
    p=ROOT/name
    text=re.split(r'\n(?:Windows \d+\.\d+\.\d+ / Android \d+\.\d+\.\d+|Android \d+\.\d+\.\d+) — ',p.read_text(encoding='utf-8'),maxsplit=1)[0].rstrip()+'\n'
    text=re.sub(r'^JM Batch [\d.]+','JM Batch '+version,text)
    p.write_text(text+'\n'+plain,encoding='utf-8')
p=ROOT/'README.md';text=p.read_text(encoding='utf-8')
text=text.replace('0.3.26','0.3.27').replace('0.6.6','0.6.7').replace('versionCode 606','versionCode 607')
text=text.replace('漫画库首图等比铺满封面框，横图取中央部分。','全部封面统一等比铺满，横图取中央部分，覆盖下载列表、漫画库和收藏夹预览。')
text=re.sub(r'\n源码待发布改动：[^\n]+\n','\n',text)
text=text.replace('当前源码将此规则统一用于所有封面','此规则统一用于所有封面')
p.write_text(text,encoding='utf-8')
mapping={'0.3.26':'0.3.27','0.6.6':'0.6.7','0326-066':'0327-067','<= 606':'<= 607','首图自适应封面':'全部封面统一自适应'}
pattern=re.compile('|'.join(map(re.escape,mapping)))
for name in ('prepare_publication','publish'):
    p=ROOT/f'work/scripts/release/{name}_0326_066.py'
    (p.parent/f'{name}_0327_067.py').write_text(pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
p=ROOT/'work/scripts/maintenance/build_adaptive_cover_release.py'
text=pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')).replace('adaptive-cover-','all-cover-').replace("versionCode='606'","versionCode='607'").replace("len(data['checks'])==4","len(data['checks'])==7")
(p.parent/'build_all_cover_release.py').write_text(text,encoding='utf-8')
mapping.update({'0.3.25':'0.3.26','0.6.5':'0.6.6','adaptive-cover-':'all-cover-','LiveAdaptiveCoverUpdate':'LiveAllCoverUpdate','39-release':'40-release','!=39':'!=40','full_history_versions=39':'full_history_versions=40'})
pattern=re.compile('|'.join(map(re.escape,sorted(mapping,key=len,reverse=True))))
p=ROOT/'work/scripts/maintenance/verify_adaptive_cover_online.py'
(p.parent/'verify_all_cover_online.py').write_text(pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
print('Prepared Windows 0.3.27 / Android 0.6.7 (607), release notes and recipes')
