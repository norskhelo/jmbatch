"""Prepare the explicitly requested Windows 0.3.25 / Android 0.6.5 release."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.25 / Android 0.6.5 — 平铺封面缩放修复

## 修复内容

- Windows 与 Android 的漫画库平铺封面区域随卡片宽度按 3:4 比例调整，修正窄屏四列布局下封面区域过高、上下留白过多的问题。
- 封面按原图比例完整居中显示，横图、竖图和收藏夹预览均不会拉伸或裁切；Windows 缩略图随卡片一起缩放。
- 保留列表封面尺寸、四列布局、点击阅读、批量选择和显示方式切换，并尽量保留浏览位置。
- 继续复用本地缩略图；Windows 仅保留可见卡片的缩放副本，不增加网站请求，不修改漫画文件。

## 版本与验证

- Windows 0.3.24 → 0.3.25；Android 0.6.4 → 0.6.5（versionCode 605），保留原包名、APK 签名证书和更新公钥。
- 修复已通过 Windows 15 项界面回归、Android 6 项框架用例和 32 项行绑定检查，覆盖封面比例、窄屏/横屏、大字号、批量选择和显示方式切换。
- 本次安装包执行相关成品检查、构建和签名核验；Android 使用隔离框架测试，未做真机验证。
'''
folder = ROOT / 'work/release-0325-065'
folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes, encoding='utf-8')
p=ROOT/'CHANGELOG.md';s=p.read_text(encoding='utf-8')
if s.startswith('# 未发布 — 漫画库平铺封面缩放修复'):
    s=s[s.index('# Windows 0.3.24'):]
if not s.startswith(notes):p.write_text(notes+'\n'+s,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=ROOT/name;s=p.read_text(encoding='utf-8')
    s=s.replace('0.3.24','0.3.25').replace('0.6.4','0.6.5').replace('versionCode 604','versionCode 605').replace('versionCode="604"','versionCode="605"')
    p.write_text(s,encoding='utf-8')
plain=re.sub(r'(?m)^#{1,6} ','',notes).replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name
    s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'))
    p.write_text(s,encoding='utf-8')
for name,version in (('work/jmbatch/README.txt','0.3.25'),('work/jmbatch-android/README.txt','0.6.5')):
    p=ROOT/name
    s=re.split(r'\n(?:Windows \d+\.\d+\.\d+ / Android \d+\.\d+\.\d+|Android \d+\.\d+\.\d+) — ',p.read_text(encoding='utf-8'),maxsplit=1)[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+','JM Batch '+version,s)
    p.write_text(s+'\n'+plain,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8')
s=s.replace('0.3.24','0.3.25').replace('0.6.4','0.6.5').replace('versionCode 604','versionCode 605')
s=s.replace('修复下载列表封面反复刷新，滚回列表优先复用缓存，完成清理时保留已显示封面。','修复漫画库四列平铺的封面缩放，封面区域随卡片宽度保持 3:4 比例，图片等比完整居中。')
s=s.replace('当前源码中的平铺封面区域','平铺封面区域').replace('；此缩放修复尚未包含在已发布的安装包中','')
p.write_text(s,encoding='utf-8')
mapping={'0.3.24':'0.3.25','0.6.4':'0.6.5','0324-064':'0325-065','<= 604':'<= 605','下载列表封面刷新修复':'平铺封面缩放修复'}
pattern=re.compile('|'.join(map(re.escape,mapping)))
for name in ('prepare_publication','publish'):
    p=ROOT/f'work/scripts/release/{name}_0324_064.py'
    (p.parent/f'{name}_0325_065.py').write_text(pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
p=ROOT/'work/scripts/maintenance/verify_download_cover_fix_online.py'
mapping={'0.3.24':'0.3.25','0.3.23':'0.3.24','0.6.4':'0.6.5','0.6.3':'0.6.4','0324-064':'0325-065','download-cover-fix-':'tile-cover-', 'LiveDownloadCoverFixUpdate':'LiveTileCoverUpdate','下载列表封面刷新修复':'平铺封面缩放修复','37-release':'38-release','!=37':'!=38','full_history_versions=37':'full_history_versions=38'}
pattern=re.compile('|'.join(map(re.escape,sorted(mapping,key=len,reverse=True))))
(p.parent/'verify_tile_cover_online.py').write_text(pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
print('Prepared 0.3.25 / 0.6.5 (605), release notes and publication recipes')
