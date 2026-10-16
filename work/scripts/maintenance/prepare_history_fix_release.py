"""Prepare matching versions, release notes and download instructions locally."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
notes = """# Windows 0.3.3 / Android 0.4.3 — 2026-10-16

## 跨版本更新公告修复

- 已打开的“完整更新公告”和升级后自动公告会随后台检查结果刷新，同时显示检查状态；网络失败时保留已有日志，关闭公告后检查完成也不会访问已关闭窗口。
- 单独保存升级前的版本，升级后的自动公告与完整公告均显示本次跨版本升级的全部已发布日志。重启应用或再次检查更新不会将其收缩成最后一版。
- 本次升级日志按版本升序显示；发现更高版本时，另列“可用更新”，区分已经安装和仍可升级的内容。下一次实际升级后，以刚刚使用的版本作为新起点。
- 兼容旧版本已查看标记和完整日志缓存。缓存不足时显示“完整日志尚未获取”，联网检查后补齐；首次安装、降级或切换仓库时不会混入不适用的升级记录。清除应用数据后无法恢复原升级起点。

## 版本与验证

- Windows 升至 0.3.3；Android 升至 0.4.3（versionCode 403），保留原包名、APK 签名身份及更新公钥。
- 补充窗口打开期间检查完成、跨多版升级、重启、再次检查、失败回退、下一次升级和仓库隔离回归验证；Windows 同时在源码与冻结成品中执行真实 Tk 控件检查。
- Android 执行宿主规则测试、编译和原证书签名验证；未将宿主测试或编译通过视为 Android 真机界面验收。
- 同步源码、使用说明、同版日志、双端安装包、SHA-256 文件及签名更新清单。
"""
folder = ROOT / 'work/release-033-043'
folder.mkdir(parents=True, exist_ok=True)
(folder / 'release-notes.md').write_text(notes, encoding='utf-8')
plain = '\n'.join(line.lstrip('# ') if line.startswith('#') else '• ' + line[2:] if line.startswith('- ') else line for line in notes.splitlines()) + '\n'
path = ROOT / 'CHANGELOG.md'
old = path.read_text(encoding='utf-8')
if not old.startswith(notes):
    path.write_text(notes + '\n' + old, encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/build.gradle', 'work/jmbatch-android/app/src/main/AndroidManifest.xml'):
    path = ROOT / name
    text = path.read_text(encoding='utf-8').replace('VERSION = "0.3.2"', 'VERSION = "0.3.3"').replace('VERSION = "0.4.2"', 'VERSION = "0.4.3"')
    if name.endswith(('build.gradle', 'AndroidManifest.xml')):
        text = text.replace('0.4.2', '0.4.3').replace('versionCode 402', 'versionCode 403').replace('versionCode="402"', 'versionCode="403"')
    path.write_text(text, encoding='utf-8')
for name, prefix in [('work/jmbatch/updates.py', 'CURRENT_NOTES = '),
                     ('work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java', '    private static final String CURRENT_NOTES=')]:
    path = ROOT / name
    lines = path.read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = prefix + json.dumps(plain, ensure_ascii=False) + (';' if name.endswith('.java') else '')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
for name in ('README.md', 'work/jmbatch/README.txt', 'work/jmbatch-android/README.txt'):
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    if name.endswith('.txt'):
        text = text.split('\nWindows 0.3.2 / Android 0.4.2')[0]
    text = text.replace('0.3.2', '0.3.3').replace('0.4.2', '0.4.3').replace('versionCode 402', 'versionCode 403')
    text = text.replace('本版新增内置漫画阅读器、章节导航、快捷收藏、书签及两种翻页模式。',
                        '本版修复公告窗口异步刷新，并在升级、重启及再次检查后保留本次跨版本的完整日志。')
    usage = '更新公告随后台检查结果刷新；升级后保留本次升级起点和全部中间版本日志，重启或再次检查仍可查看。未来新版另列为“可用更新”。日志未取全时保留本版说明并明确提示，联网检查后补齐。'
    if name.endswith('.txt'):
        text += '\n8. ' + usage + '\n\n' + plain
    else:
        text = text.replace('## 其他功能', '## 更新公告\n\n' + usage + '\n\n## 其他功能')
    path.write_text(text, encoding='utf-8')
for name in ('prepare_publication', 'publish'):
    source = ROOT / f'work/scripts/release/{name}_032_042.py'
    text = source.read_text(encoding='utf-8').replace('0.3.2', '0.3.3').replace('0.4.2', '0.4.3').replace('032-042', '033-043').replace('内置漫画阅读器', '跨版本更新公告修复')
    (source.parent / f'{name}_033_043.py').write_text(text, encoding='utf-8')
print('Prepared Windows 0.3.3 / Android 0.4.3 versions and matching notes.')
