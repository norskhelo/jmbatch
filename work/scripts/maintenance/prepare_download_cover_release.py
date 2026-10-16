"""Prepare the live download cover release and matching user-facing notes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
notes = """# Windows 0.3.4 / Android 0.4.4 — 2026-10-16

## 下载过程中显示封面

- Windows 下载列表和 Android 下载任务卡片新增封面。首章第一页下载并校验成功后自动显示，无需等待整本下载完成；PDF、ZIP、图片文件夹三种下载格式均支持。
- 第一页未下载完成或无法读取时显示占位，不会把先完成的后续页或未完成的临时图片当作封面；第一张图片就绪或修复后自动刷新。
- 暂停、继续、重试和重启应用后，可从已有第一页缓存恢复封面；下载完成并清理图片缓存后，自动改从最终成品读取第一页。
- 封面在后台异步读取，仅加载可见任务，并限制内存缓存和待加载队列。封面失败不影响下载、进度、重试或打开操作，不增加额外的网站图片请求，也不向成品写入封面或下载信息文件。

## 版本与验证

- Windows 升至 0.3.4；Android 升至 0.4.4（versionCode 404），保留原包名、APK 签名身份和更新公钥。
- Windows 回归覆盖下载尚未完成时的实际列表封面、三任务并行、暂停续传、完成后缓存清理、三种成品格式及最小窗口；源码和冻结成品均执行界面自检。
- Android 执行首页选择、临时文件排除、状态恢复、任务隔离等宿主检查，并编译、核验原证书签名；未进行 Android 真机界面验证。
- 同步源码、使用说明、更新日志、双端安装包、SHA-256 校验文件和签名更新清单。
"""
folder = ROOT / 'work/release-034-044'
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
    text = path.read_text(encoding='utf-8').replace('VERSION = "0.3.3"', 'VERSION = "0.3.4"').replace('VERSION = "0.4.3"', 'VERSION = "0.4.4"')
    if name.endswith(('build.gradle', 'AndroidManifest.xml')):
        text = text.replace('0.4.3', '0.4.4').replace('versionCode 403', 'versionCode 404').replace('versionCode="403"', 'versionCode="404"')
    path.write_text(text, encoding='utf-8')
for name, prefix in [('work/jmbatch/updates.py', 'CURRENT_NOTES = '),
                     ('work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java', '    private static final String CURRENT_NOTES=')]:
    path = ROOT / name
    lines = path.read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = prefix + json.dumps(plain, ensure_ascii=False) + (';' if name.endswith('.java') else '')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
usage = '下载列表会在首章第一页成功下载后自动显示封面，无需等待整本完成；暂停、继续和重启后可从缓存恢复。尚未就绪或无法读取时显示占位，完成后从 PDF、ZIP 或文件夹成品读取。'
for name in ('README.md', 'work/jmbatch/README.txt', 'work/jmbatch-android/README.txt'):
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    if name.endswith('.txt'):
        text = text.split('\nWindows 0.3.3 / Android 0.4.3')[0]
    text = text.replace('0.3.3', '0.3.4').replace('0.4.3', '0.4.4').replace('versionCode 403', 'versionCode 404')
    text = text.replace('本版修复公告窗口异步刷新，并在升级、重启及再次检查后保留本次跨版本的完整日志。',
                        '本版支持下载过程中在任务列表显示首章第一页封面，暂停、续传和下载完成后均可查看。')
    if name.endswith('.txt'):
        if usage not in text:
            text += '\n9. ' + usage + '\n\n' + plain
    elif '## 下载封面' not in text:
        text = text.replace('## 内置阅读器', '## 下载封面\n\n' + usage + '\n\n## 内置阅读器')
    path.write_text(text, encoding='utf-8')
for name in ('prepare_publication', 'publish'):
    source = ROOT / f'work/scripts/release/{name}_033_043.py'
    text = source.read_text(encoding='utf-8').replace('0.3.3', '0.3.4').replace('0.4.3', '0.4.4').replace('033-043', '034-044').replace('跨版本更新公告修复', '下载过程中显示封面')
    (source.parent / f'{name}_034_044.py').write_text(text, encoding='utf-8')
print('Prepared Windows 0.3.4 / Android 0.4.4 versions and matching notes.')
