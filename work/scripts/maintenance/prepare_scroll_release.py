"""Prepare notes and version-specific recipes for the seamless scroll update."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.12 / Android 0.5.6 — 上下滚动无缝阅读

## 阅读体验

- 上下滚动阅读时，相邻图片直接相接，移除软件添加的页间空白、分隔线和逐页页码栏，跨章节连续阅读同样无间隔。
- 本章页码、总页码及章节信息继续显示在阅读状态栏；加载中和读取失败的提示保留在对应页面区域。
- Android 按阅读区域宽度计算图片高度，消除图片容器与实际图片尺寸不一致造成的边缘空隙。
- 保留图片自身内容，不裁掉原图已有白边；继续支持图片文件夹、ZIP、PDF、章节跳转、书签和阅读位置恢复。

## 版本与验证

- Windows 0.3.11 → 0.3.12；Android 0.5.5 → 0.5.6（versionCode 506）。沿用 Android 包名、APK 原签名证书和应用更新公钥。
- Windows 执行回归、源码及冻结成品自检，并检查三种格式、两种窗口尺寸和章节边界的实际图片接缝；Android 执行宿主检查、完整编译和原签名核验。
- 未连接 Android 真机，宿主检查和编译不代表手机界面实测。
- 提供双端安装包、同版日志、SHA-256、更新清单及原密钥签名，并发布对应源码与使用说明。
'''
folder = root / 'work/release-0312-056'
folder.mkdir(exist_ok=True)
(folder / 'release-notes.md').write_text(notes, encoding='utf-8')
p = root / 'CHANGELOG.md'
value = p.read_text(encoding='utf-8')
if not value.startswith(notes):
    p.write_text(notes + '\n' + value, encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p = root / name
    value = p.read_text(encoding='utf-8').replace('0.3.11', '0.3.12').replace('0.5.5', '0.5.6').replace('versionCode 505', 'versionCode 506').replace('versionCode="505"', 'versionCode="506"')
    p.write_text(value, encoding='utf-8')
plain = notes.replace('## ', '').replace('# ', '').replace('- ', '• ')
for name in ('work/jmbatch/updates.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p = root / name
    value = re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',
                   lambda m: m[1] + json.dumps(plain, ensure_ascii=False) + (';' if name.endswith('.java') else ''), p.read_text(encoding='utf-8'))
    p.write_text(value, encoding='utf-8')
for name in ('README.md', 'work/jmbatch/README.txt', 'work/jmbatch-android/README.txt'):
    p = root / name
    value = p.read_text(encoding='utf-8')
    if name != 'README.md':
        value = re.split(r'\nWindows 0\.3\.11 / Android 0\.5\.5 — ', value)[0].rstrip() + '\n'
    value = value.replace('0.3.11', '0.3.12').replace('0.5.5', '0.5.6').replace('versionCode 505', 'versionCode 506')
    value = value.replace('本版修复左右翻页闪屏，加入邻页预加载、跟手拖动与翻页回弹动画。', '本版上下滚动阅读的相邻图片无间隔直接相接，页码保留在状态栏。')
    if name != 'README.md':
        value += '\n' + plain
    else:
        value = value.replace('滚动阅读与左右翻页可随时切换，', '上下滚动时相邻图片无间隔直接相接，页码显示在状态栏；原图自身的白边保留。滚动阅读与左右翻页可随时切换，')
    p.write_text(value, encoding='utf-8')

# Reuse the established signing, publication, source audit and online checks.
recipes = [
    ('release/prepare_publication_0311_055.py', 'release/prepare_publication_0312_056.py'),
    ('release/publish_0311_055.py', 'release/publish_0312_056.py'),
    ('release/audit_paging_release.py', 'release/audit_scroll_release.py'),
    ('release/verify_paging_commit.py', 'release/verify_scroll_commit.py'),
    ('maintenance/verify_paging_online.py', 'maintenance/verify_scroll_online.py'),
    ('maintenance/verify_android_paging_online.py', 'maintenance/verify_android_scroll_online.py'),
]
for old, new in recipes:
    p = root / 'work/scripts' / old
    value = p.read_text(encoding='utf-8')
    for before, after in [
        ('0.3.11', '0.3.12'), ('0.3.10', '0.3.11'), ('0.5.5', '0.5.6'), ('0.5.4', '0.5.5'),
        ('0311-055', '0312-056'), ('0311_055', '0312_056'), ('paging-055', 'scroll-056'),
        ('paging-windows-final', 'scroll-windows-verified'), ('paging-android-final', 'scroll-android-verified'),
        ('paging-', 'scroll-'), ('prepare_paging_release', 'prepare_scroll_release'),
        ('verify_paging_online', 'verify_scroll_online'), ('verify_android_paging_online', 'verify_android_scroll_online'),
        ('audit_paging_release', 'audit_scroll_release'), ('verify_paging_commit', 'verify_scroll_commit'),
        ('左右翻页闪屏与流畅度修复', '上下滚动无缝阅读'), ('左右翻页流畅度修复', '上下滚动无缝阅读'),
        ('<= 505', '<= 506'), ("versionCode='505'", "versionCode='506'"),
        ('==35', '==36'), ('checks=35', 'checks=36'), ('range(1,12)', 'range(1,13)'),
        ('!=15', '!=16'), ('15-release', '16-release'), ('full_history_versions=15', 'full_history_versions=16')
    ]:
        value = value.replace(before, after)
    if new.endswith('audit_scroll_release.py'):
        value = value.replace(",'work/scripts/release/make_paging_checks.py'", '')
        value = value.replace("assert any('cache cleanup UI' in check for check in data['checks'])", "assert all(len(seams)==6 and all(s['gap']==0 for s in seams) for seams in data['reader_scroll_seams'].values())\n    assert set(data['reader_scroll_seams'])=={'images','zip','pdf'}")
    (root / 'work/scripts' / new).write_text(value, encoding='utf-8')
print('Prepared Windows 0.3.12 / Android 0.5.6, versionCode 506 and matching release recipes')
