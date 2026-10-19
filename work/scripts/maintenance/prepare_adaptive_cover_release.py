"""Prepare local release metadata; never push or publish before preview review."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.26 / Android 0.6.6 — 首图自适应封面

## 更新内容

- 漫画库平铺继续使用漫画的第一张图片作为封面，按原图比例放大并铺满 3:4 封面区域，避免额外留白，不拉伸图像。
- 竖向首图等比铺满；横向首图取中央部分，左右对称裁切。其他比例图片同样居中裁切至封面框。
- 收藏夹仍完整显示多封面拼图，列表封面保持原有完整居中方式；切换显示方式及卡片复用时自动使用对应规则。
- 继续复用本地缩略图，保留四列布局、批量选择和阅读交互，不增加网站请求，不修改原漫画文件。

## 版本与验证

- Windows 0.3.25 → 0.3.26；Android 0.6.5 → 0.6.6（versionCode 606），保留原包名、签名证书和更新公钥。
- Windows 16 项相关界面测试、Android 5 项框架测试和 36 项行绑定检查通过，覆盖横竖图、窄屏、横屏、切换模式和收藏夹卡片复用。
- 效果预览使用隔离演示漫画；Android 验证使用框架测试，未做真机验证。
'''
folder = ROOT / 'work/release-0326-066'
folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=ROOT/'CHANGELOG.md';text=p.read_text(encoding='utf-8')
if not text.startswith(notes):p.write_text(notes+'\n'+text,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=ROOT/name;text=p.read_text(encoding='utf-8')
    text=text.replace('0.3.25','0.3.26').replace('0.6.5','0.6.6').replace('versionCode 605','versionCode 606').replace('versionCode="605"','versionCode="606"')
    p.write_text(text,encoding='utf-8')
plain=re.sub(r'(?m)^#{1,6} ','',notes).replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name;text=p.read_text(encoding='utf-8')
    text=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),text)
    p.write_text(text,encoding='utf-8')
for name,version in (('work/jmbatch/README.txt','0.3.26'),('work/jmbatch-android/README.txt','0.6.6')):
    p=ROOT/name
    text=re.split(r'\n(?:Windows \d+\.\d+\.\d+ / Android \d+\.\d+\.\d+|Android \d+\.\d+\.\d+) — ',p.read_text(encoding='utf-8'),maxsplit=1)[0].rstrip()+'\n'
    text=re.sub(r'^JM Batch [\d.]+','JM Batch '+version,text)
    p.write_text(text+'\n'+plain,encoding='utf-8')
# Download links are switched only as part of the eventual release push.
p=ROOT/'README.md';text=p.read_text(encoding='utf-8')
old='当前源码及正式版本：**Windows 0.3.25 / Android 0.6.5（versionCode 605）**。修复漫画库四列平铺的封面缩放，封面区域随卡片宽度保持 3:4 比例，图片等比完整居中。'
text=text.replace(old,'当前源码：**Windows 0.3.26 / Android 0.6.6（versionCode 606，待发布）**。漫画库首图等比铺满封面框，横图取中央部分。当前正式版仍为 Windows 0.3.25 / Android 0.6.5。')
text=text.replace('平铺封面区域按卡片宽度保持 3:4 比例，图片按原比例完整居中显示。','平铺封面区域按卡片宽度保持 3:4 比例，漫画首图等比铺满，横图居中裁切；收藏夹拼图完整居中显示。')
p.write_text(text,encoding='utf-8')
mapping={'0.3.25':'0.3.26','0.6.5':'0.6.6','0325-065':'0326-066','<= 605':'<= 606','平铺封面缩放修复':'首图自适应封面'}
pattern=re.compile('|'.join(map(re.escape,mapping)))
for name in ('prepare_publication','publish'):
    p=ROOT/f'work/scripts/release/{name}_0325_065.py'
    (p.parent/f'{name}_0326_066.py').write_text(pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
p=ROOT/'work/scripts/maintenance/build_tile_cover_release.py'
text=pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')).replace('tile-cover-','adaptive-cover-').replace("versionCode='605'","versionCode='606'")
(p.parent/'build_adaptive_cover_release.py').write_text(text,encoding='utf-8')
print('Prepared local Windows 0.3.26 / Android 0.6.6; no push or publication')
