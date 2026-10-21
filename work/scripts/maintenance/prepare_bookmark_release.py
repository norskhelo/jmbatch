"""Prepare the bookmark fix and its reproducible build/publication recipes."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
notes = """# Windows 0.3.30 / Android 0.6.12 — 书签跳转修复

发布日期：2026-10-21

## 修复内容
- 修复左右翻页时首次跳转书签仍停在旧页的问题：目标图片尚在加载或翻页动画尚未结束时，轻点画面、收放工具栏和阅读区尺寸变化不再取消跳转目标。
- 切换滚动阅读与左右翻页时保留最近请求的目标页；连续选择书签时以最后一次选择为准，旧页面加载结果不会取代新目标。
- Android 滚动阅读跳转时停止原有惯性滚动并对齐页首。修复最后一页较短时列表向前回填、画面与目标页码不一致的问题；章节之间仍无额外间隙。
- Windows 同步修复轻点取消待加载书签及模式切换丢失目标的问题，滚动定位精确到页首，保持原有滚轮速度。
- 保留已有书签、阅读记录、收藏、漫画文件及下载设置，无需重新下载漫画。

## 版本与验证
- Windows 0.3.29 → 0.3.30；Android 0.6.11 → 0.6.12（versionCode 612），沿用原包名、APK 签名证书和更新公钥。
- Android 10/15 框架的同组 20 项书签场景中，旧版有 6 项失败，修复后全部通过；另通过 18 项章节/滚动框架回归及 105 项翻页/工具栏宿主检查。
- Windows 通过 26 项阅读相关测试及源码/冻结成品的实际窗口书签检查，完成双端构建与交付签名校验。
- 未连接 Android 真机，框架验证不等同于特定手机实测。
"""
folder = ROOT / 'work/release-0330-0612'
folder.mkdir(parents=True, exist_ok=True)
(folder / 'release-notes.md').write_text(notes, encoding='utf-8')
p = ROOT / 'CHANGELOG.md'
if not p.read_text(encoding='utf-8').startswith(notes):
    p.write_text(notes + '\n' + p.read_text(encoding='utf-8'), encoding='utf-8')

mapping = {'0.3.29': '0.3.30', '0.6.11': '0.6.12', '0329-0611': '0330-0612', '0329_0611': '0330_0612'}
def replace(text):
    return re.sub('|'.join(map(re.escape, mapping)), lambda m: mapping[m[0]], text)

for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p = ROOT / name
    p.write_text(replace(p.read_text(encoding='utf-8')).replace('versionCode 611', 'versionCode 612').replace('versionCode="611"', 'versionCode="612"'), encoding='utf-8')
plain = re.sub(r'(?m)^#{1,6} ', '', notes).replace('- ', '• ')
for name in ('work/jmbatch/updates.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p = ROOT / name
    p.write_text(re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',
        lambda m: m[1] + json.dumps(plain, ensure_ascii=False) + (';' if p.suffix == '.java' else ''), p.read_text(encoding='utf-8')), encoding='utf-8')
for name in ('work/jmbatch/README.txt', 'work/jmbatch-android/README.txt'):
    p = ROOT / name
    text = re.split(r'\n(?:Windows \d+\.\d+\.\d+ / Android \d+\.\d+\.\d+|Android \d+\.\d+\.\d+) — ', p.read_text(encoding='utf-8'), maxsplit=1)[0].rstrip()
    p.write_text(replace(text) + '\n\n' + plain, encoding='utf-8')
p = ROOT / 'README.md'
text = replace(p.read_text(encoding='utf-8')).replace('versionCode 611', 'versionCode 612')
text = text.replace('双端漫画库支持先检查新章节，再确认使用正常下载功能下载。', '修复书签首次跳转被轻点、布局变化或模式切换取消，以及滚动阅读末页定位偏移。')
p.write_text(text, encoding='utf-8')

for kind in ('prepare_publication', 'publish'):
    p = ROOT / f'work/scripts/release/{kind}_0329_0611.py'
    text = replace(p.read_text(encoding='utf-8')).replace('<= 611', '<= 612').replace('漫画库检查章节更新', '书签跳转修复')
    if kind == 'prepare_publication':
        text = text.replace("'--notes', str(notes)", "'--tracked-sources-only', '--notes', str(notes)")
    (p.parent / f'{kind}_0330_0612.py').write_text(text, encoding='utf-8')
p = ROOT / 'work/scripts/maintenance/build_chapter_updates_release.py'
text = replace(p.read_text(encoding='utf-8')).replace('chapter-updates', 'bookmarks').replace("versionCode='611'", "versionCode='612'")
(p.parent / 'build_bookmark_release.py').write_text(text, encoding='utf-8')
p = ROOT / 'work/scripts/maintenance/verify_chapter_updates_online.py'
online = {'0.3.28': '0.3.29', '0.3.29': '0.3.30', '0.6.10': '0.6.11', '0.6.11': '0.6.12', '0329-0611': '0330-0612'}
text = re.sub('|'.join(map(re.escape, online)), lambda m: online[m[0]], p.read_text(encoding='utf-8'))
text = text.replace('chapter-updates', 'bookmarks').replace('ChapterUpdates', 'Bookmark').replace('漫画库检查章节更新', '书签跳转修复').replace('44', '45')
(p.parent / 'verify_bookmark_online.py').write_text(text, encoding='utf-8')
print('Prepared Windows 0.3.30 / Android 0.6.12 (612)')
