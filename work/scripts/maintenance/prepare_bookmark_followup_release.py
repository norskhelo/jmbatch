"""Prepare Android 0.6.13 and version-specific, auditable release recipes."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
NOTES = """# Android 0.6.13 — 书签首次跳转补充修复

发布日期：2026-10-21

## 修复内容
- 修复滚动阅读中跳转已发出、首帧布局前阅读区尺寸变化时，列表恢复旧页的问题。跳转目标保留到实际显示目标页并对齐页首；旧布局回调不会覆盖目标。
- 书签、页码和章节弹窗中的跳转统一在弹窗关闭且阅读窗口恢复焦点后执行，避免在离场弹窗下面定位或启动翻页动画。适用于滚动阅读与左右翻页，同章及跨章跳转。
- 连续跳转以最后一次选择为准；完成跳转后正常手动滚动，取消和删除书签不会触发跳转。
- 保留现有书签、阅读记录、漫画文件、下载设置及原签名，可直接覆盖安装。Windows 保持 0.3.30。

## 版本与验证
- Android 0.6.12 → 0.6.13（versionCode 613），原包名、APK 签名证书和更新公钥不变。
- Android 10/15 共 62 项相关框架检查通过，覆盖真实弹窗触摸、窗口根焦点恢复、首帧布局、冷页加载、两种阅读模式、页码/章节跳转和手动滚动。
- 新增布局交错场景在 0.6.12 的两个系统版本上均复现停在旧页，修复后通过。
- 未连接 Android 真机；已验证上述布局缺陷和跳转时序保护，尚未确认用户手机上两种模式的全部现场原因。
"""
notes = ROOT / 'work/release-android-0613/release-notes.md'
notes.parent.mkdir(parents=True, exist_ok=True)
notes.write_text(NOTES, encoding='utf-8')
java = ROOT / 'work/jmbatch-android/app/src/main/java/app/jmbatch/android'
for name in ('Core.java',):
    p = java / name
    text = p.read_text(encoding='utf-8')
    assert 'VERSION = "0.6.12"' in text
    p.write_text(text.replace('VERSION = "0.6.12"', 'VERSION = "0.6.13"'), encoding='utf-8')
for name in ('app/build.gradle', 'app/src/main/AndroidManifest.xml'):
    p = ROOT / 'work/jmbatch-android' / name
    p.write_text(p.read_text(encoding='utf-8').replace('0.6.12', '0.6.13')
                 .replace('versionCode 612', 'versionCode 613').replace('versionCode="612"', 'versionCode="613"'), encoding='utf-8')
plain = re.sub(r'(?m)^#{1,6} ', '', NOTES).replace('- ', '• ')
p = java / 'GithubUpdates.java'
p.write_text(re.sub(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',
    lambda m: 'private static final String CURRENT_NOTES=' + json.dumps(plain, ensure_ascii=False) + ';', p.read_text(encoding='utf-8')), encoding='utf-8')
p = ROOT / 'CHANGELOG.md'
p.write_text(NOTES + '\n' + p.read_text(encoding='utf-8'), encoding='utf-8')
p = ROOT / 'work/jmbatch-android/README.txt'
text = p.read_text(encoding='utf-8').split('Windows 0.3.30 / Android 0.6.12 — ')[0].rstrip()
p.write_text(text.replace('0.6.12', '0.6.13') + '\n\n' + plain, encoding='utf-8')
p = ROOT / 'README.md'
lines = []
for line in p.read_text(encoding='utf-8').splitlines():
    if line.startswith('当前正式版本：'):
        line = '当前正式版本：**Windows 0.3.30 / Android 0.6.13（versionCode 613）**。Android 补充修复书签跳转时的首帧布局覆盖，并在弹窗关闭、阅读窗口恢复焦点后执行跳转。安装包、更新日志与镜像入口见下方。'
    elif line.startswith('当前正式版为 '):
        line = line.replace('Android 0.6.12', 'Android 0.6.13').replace('[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.30-0.6.12)', '[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.6.13)')
    elif line.startswith('| Android '):
        line = line.replace('release-0.3.30-0.6.12', 'release-android-0.6.13').replace('0.6.12', '0.6.13')
    lines.append(line)
p.write_text('\n'.join(lines) + '\n', encoding='utf-8')

mapping = {'0.6.9':'0.6.13', '0.6.8':'0.6.12', '0.3.27':'0.3.30', '0.3.26':'0.3.29',
           '069':'0613', '609':'613', '608':'612', 'gallery-privacy':'bookmark-followup',
           'GalleryPrivacy':'BookmarkFollowup', '下载图片对系统相册隐藏':'书签首次跳转补充修复',
           '!=42':'!=46', '42-release':'46-release', 'full_history_versions=42':'full_history_versions=46'}
pattern = re.compile('|'.join(map(re.escape, sorted(mapping, key=len, reverse=True))))
for folder, old, new in (
    ('release','prepare_publication_android_069.py','prepare_publication_android_0613.py'),
    ('release','publish_android_069.py','publish_android_0613.py'),
    ('maintenance','verify_gallery_privacy_online.py','verify_bookmark_followup_online.py'),
):
    p = ROOT / 'work/scripts' / folder / old
    text = pattern.sub(lambda m: mapping[m[0]], p.read_text(encoding='utf-8'))
    if old.startswith('prepare_publication'):
        text = text.replace("'--platform','android'", "'--platform','android','--tracked-sources-only'")
    (p.parent / new).write_text(text, encoding='utf-8')
p = ROOT / 'work/scripts/maintenance/build_bookmark_release.py'
text = p.read_text(encoding='utf-8').replace('0.6.12','0.6.13').replace('0330-0612','followup-0613').replace("versionCode='612'","versionCode='613'")
(p.parent / 'build_bookmark_followup.py').write_text(text, encoding='utf-8')
print('Prepared Android 0.6.13 / 613; Windows unchanged at 0.3.30')
