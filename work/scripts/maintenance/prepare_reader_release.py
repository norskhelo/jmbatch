"""Prepare the requested internal-reader release; no remote mutations."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
notes = """# Windows 0.3.2 / Android 0.4.2 — 2026-10-16

## 软件内阅读

- 从下载任务或漫画库打开 PDF、ZIP、图片文件夹，直接进入内置阅读器。
- 支持章节列表、上一章/下一章、本章页码与总页码、输入总页码跳转。文件夹和 ZIP 按图片目录识别章节；PDF 作为一个章节，不恢复原章节。
- 阅读时可快捷收藏/取消收藏，与已有漫画库共用收藏记录。
- 支持添加、移除、查看和跳转书签。每本漫画分别保存书签、上次页码和阅读模式，重新打开恢复。
- 可在连续滚动与左右翻页之间切换。Windows 支持滚轮、方向键、PageUp/PageDown 和点击两侧；Android 支持上下滚动、左右滑动、点击两侧及按钮翻页。
- 页面按需后台加载，限制解码尺寸和缓存；关闭阅读器释放文件。阅读记录保存在应用内部，不向漫画文件夹或 ZIP 写入信息。
- Android 外部 ZIP 先复制到应用临时缓存再按页读取，关闭后清理；最多支持 8 GB 文件、20000 页。首次打开大文件需要等待，返回可取消。无效、加密或无权限文件显示错误，单页损坏可继续翻页。

## 版本与验证

- Windows 0.3.1 → 0.3.2；Android 0.4.1 → 0.4.2（versionCode 402）。保留原包名、APK 签名和更新公钥。
- 同步源码、使用说明、更新日志、安装包、SHA-256 和签名更新清单。
- 验证使用隔离素材、Windows 自动化界面与冻结成品自检、Android 宿主测试和编译；Android 真机手势及厂商 SAF 行为未因编译通过而视为验证通过。
"""
folder = ROOT / 'work/release-032-042'
folder.mkdir(parents=True, exist_ok=True)
(folder / 'release-notes.md').write_text(notes, encoding='utf-8')
plain = notes.replace('# ', '').replace('## ', '').replace('- ', '• ')
changelog = ROOT / 'CHANGELOG.md'
old = changelog.read_text(encoding='utf-8')
if not old.startswith(notes):
    changelog.write_text(notes + '\n' + old, encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','work/jmbatch-android/app/build.gradle','work/jmbatch-android/app/src/main/AndroidManifest.xml'):
    path=ROOT/name
    value=path.read_text(encoding='utf-8').replace('VERSION = "0.3.1"','VERSION = "0.3.2"').replace('VERSION = "0.4.1"','VERSION = "0.4.2"').replace('VERSION="0.4.1"','VERSION="0.4.2"')
    if name.endswith(('build.gradle','AndroidManifest.xml')):
        value=value.replace('0.4.1','0.4.2').replace('versionCode 401','versionCode 402').replace('versionCode="401"','versionCode="402"')
    path.write_text(value,encoding='utf-8')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    path=ROOT/name
    lines=path.read_text(encoding='utf-8').splitlines()
    for i,line in enumerate(lines):
        if line.startswith('CURRENT_NOTES = '):lines[i]='CURRENT_NOTES = '+json.dumps(plain,ensure_ascii=False)
        if line.startswith('    private static final String CURRENT_NOTES='):lines[i]='    private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
for name in ('README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt'):
    path=ROOT/name
    value=path.read_text(encoding='utf-8')
    if name.endswith('.txt'):
        value=value.split('\nWindows 0.3.1 / Android 0.4.1')[0]
    value=value.replace('0.3.1','0.3.2').replace('0.4.1','0.4.2').replace('versionCode 401','versionCode 402')
    value=value.replace('本版提供三种下载格式与六向互转，并包含此前已推送的续传修复。','本版新增内置漫画阅读器、章节导航、快捷收藏、书签及两种翻页模式。')
    usage='从任务或漫画库打开后直接在软件内阅读。支持章节切换、本章/总页码、跳页、快捷收藏、书签列表及跳转；再次打开恢复上次页码和模式。滚动阅读与左右翻页可随时切换，Windows 使用滚轮、方向键或页面两侧，Android 使用上下滚动、左右滑动或页面两侧。PDF 按一个章节显示。阅读记录绑定原文件路径/地址；移动文件或清除应用数据后不自动迁移。Android 外部 ZIP 首次打开需准备临时缓存，返回可取消，关闭后清理。'
    if name=='README.md':
        value=value.replace('## 其他功能','## 内置阅读器\n\n'+usage+'\n\n## 其他功能')
    else:
        value+='\n7. '+usage+'\n\n'+plain
    path.write_text(value,encoding='utf-8')
for name in ('prepare_publication','publish'):
    source=ROOT/f'work/scripts/release/{name}_031_041.py'
    value=source.read_text(encoding='utf-8').replace('0.3.1','0.3.2').replace('0.4.1','0.4.2').replace('031-041','032-042').replace('三种下载格式与互相导出','内置漫画阅读器')
    (source.parent/f'{name}_032_042.py').write_text(value,encoding='utf-8')
print('Prepared Windows 0.3.2 / Android 0.4.2 reader notes and versions')
