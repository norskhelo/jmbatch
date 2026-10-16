"""Prepare explicit manual update checks and matching release documentation."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
notes = """# Windows 0.3.5 / Android 0.4.5 — 2026-10-16

## 手动检查更新

- Windows 和 Android 主界面新增明确的“检查更新 / 公告”入口，点击后打开更新窗口并立即联网检查。更新窗口和完整公告也提供“检查更新”按钮。
- 关闭“启动时自动检查更新”后仍可手动检查；检查使用已保存的仓库，不修改自动检查开关。修改仓库后先点击“保存”，再检查；仓库为空时提示先配置。
- 检查时显示进度状态并防止重复并发请求；完成后显示发现新版、当前已是适用版本或失败重试提示，更新公告同步刷新。失败保留离线公告，可重新点击检查。
- 检查过程不影响漫画下载；下载更新和安装仍由用户点击确认，沿用原清单签名、SHA-256 及 APK 签名验证机制。

## 版本与验证

- Windows 升至 0.3.5；Android 升至 0.4.5（versionCode 405），保留原包名、APK 签名身份和更新公钥。
- Windows 验证关闭自动检查后的实际按钮操作、重复点击、检查状态、失败重试、公告刷新和最小窗口布局；源码与冻结成品均执行界面自检。
- Android 执行宿主回归、编译及原证书签名核验；未进行 Android 真机界面验证。
- 同步源码、使用说明、同版日志、双端安装包、SHA-256 校验文件和签名更新清单。
"""
folder = ROOT / 'work/release-035-045'
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
    text = path.read_text(encoding='utf-8').replace('VERSION = "0.3.4"', 'VERSION = "0.3.5"').replace('VERSION = "0.4.4"', 'VERSION = "0.4.5"')
    if name.endswith(('build.gradle', 'AndroidManifest.xml')):
        text = text.replace('0.4.4', '0.4.5').replace('versionCode 404', 'versionCode 405').replace('versionCode="404"', 'versionCode="405"')
    path.write_text(text, encoding='utf-8')
for name, prefix in [('work/jmbatch/updates.py', 'CURRENT_NOTES = '),
                     ('work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java', '    private static final String CURRENT_NOTES=')]:
    path = ROOT / name
    lines = path.read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = prefix + json.dumps(plain, ensure_ascii=False) + (';' if name.endswith('.java') else '')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
usage = '点击主界面“检查更新 / 公告”立即联网检查，更新窗口与完整公告也可手动检查。关闭启动自动检查后仍可使用。检查采用已保存仓库；修改后先保存。检查失败保留离线公告，可再次点击重试。下载和安装新版需要手动确认。'
for name in ('README.md', 'work/jmbatch/README.txt', 'work/jmbatch-android/README.txt'):
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    if name.endswith('.txt'):
        text = text.split('\nWindows 0.3.4 / Android 0.4.4')[0]
    text = text.replace('0.3.4', '0.3.5').replace('0.4.4', '0.4.5').replace('versionCode 404', 'versionCode 405')
    text = text.replace('本版支持下载过程中在任务列表显示首章第一页封面，暂停、续传和下载完成后均可查看。', '本版提供明确的手动检查更新入口，关闭启动自动检查后也可随时检查。')
    if name.endswith('.txt'):
        if usage not in text:
            text += '\n10. ' + usage + '\n\n' + plain
    elif usage not in text:
        text = text.replace('## 更新公告\n\n', '## 更新公告\n\n' + usage + '\n\n')
    path.write_text(text, encoding='utf-8')
for name in ('prepare_publication', 'publish'):
    source = ROOT / f'work/scripts/release/{name}_034_044.py'
    text = source.read_text(encoding='utf-8').replace('0.3.4', '0.3.5').replace('0.4.4', '0.4.5').replace('034-044', '035-045').replace('下载过程中显示封面', '手动检查更新')
    (source.parent / f'{name}_035_045.py').write_text(text, encoding='utf-8')
print('Prepared Windows 0.3.5 / Android 0.4.5 versions and matching notes.')
