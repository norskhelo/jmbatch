"""Prepare matching local documentation for the authorized cache cleanup release."""
from pathlib import Path
import json
import re

root=Path(__file__).resolve().parents[3]
notes='''# Windows 0.3.9 / Android 0.4.9 — 2026-10-16

## 手动清理下载缓存与自动清理提示

- 双端主界面加入“清理下载缓存”，暂停全部下载并等待请求退出后可使用；清理在后台执行，显示进度与结果，清理期间不能启动下载。
- 手动清理队列中已完成任务的可删除图片缓存、章节缓存，以及各任务内未完成的图片临时文件、导出临时文件和保存暂存目录。暂停、失败、取消、排队及待选章节任务的完整图片与章节信息保留，支持继续下载。
- 自动清理在成品校验、保存并写入完成标记后执行；支持 PDF、ZIP、图片文件夹和完成标记恢复路径。清理后明确显示删除文件数、释放的文件字节数及未能清理的数量，失败可手动重试，成品仍显示下载完成。
- Windows 在任务详情及日志显示自动清理结果；Android 在任务列表、详情及主界面显示结果，并保存最近一次清理提示，重开应用可见。
- 保留已下载成品、收藏、书签、队列和完成标记；沿用任务的“保留图片缓存”设置。手动清理无法确认成品存在时保留完整图片缓存，拒绝跟随符号链接或目录联接。
- 仅处理仍有队列记录的任务目录内已知缓存，不扫描系统垃圾、不删除无法确认归属的文件、不清理已移除记录的孤立缓存，也不触及外部保存目录中的可疑残留。需要清理时请先清理缓存，再移除任务记录。

## 版本与验证

- Windows 0.3.9；Android 0.4.9（versionCode 409），保留原包名、APK 签名证书及更新公钥。
- 验证三种下载格式的自动清理和恢复、文件数/字节数、续传与成品保护、重复清理、缺失路径、清理失败重试及链接目录边界；Windows 包含实际界面按钮与后台互斥检查。
- Windows 执行回归测试、源码和冻结成品自检；Android 执行宿主测试、编译及签名核验，未连接 Android 真机，不将宿主结果视为手机实测。
- 同步源码、使用说明、同版更新日志、安装包、SHA-256 校验文件和签名更新清单。
'''
folder=root/'work/release-039-049';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=root/'CHANGELOG.md';value=p.read_text(encoding='utf-8')
if not value.startswith(notes):p.write_text(notes+'\n'+value,encoding='utf-8')
for name in ['work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle',
             'README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    p=root/name;value=p.read_text(encoding='utf-8')
    if name.endswith('README.txt'):
        value=value.split('\nWindows 0.3.8 / Android 0.4.8 — ',1)[0].rstrip()+'\n'
    value=value.replace('0.3.8','0.3.9').replace('0.4.8','0.4.9').replace('versionCode 408','versionCode 409').replace('versionCode="408"','versionCode="409"')
    value=value.replace('本版优化 Android 图片文件夹的校验与保存，并为双端加入 1–8 章读取并行数配置（默认 4）。','本版加入手动清理下载缓存，并显示自动清理的文件数、释放空间与失败提示。')
    p.write_text(value,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ['work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    p=root/name;value=p.read_text(encoding='utf-8')
    value=value.split('\nWindows 0.3.9 / Android 0.4.9 — ',1)[0].rstrip()
    p.write_text(value+'\n\n'+plain,encoding='utf-8')
for name in ['work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java']:
    p=root/name;value=p.read_text(encoding='utf-8')
    value=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if name.endswith('.java') else ''),value)
    p.write_text(value,encoding='utf-8')
for prefix in ['prepare_publication','publish']:
    p=root/f'work/scripts/release/{prefix}_038_048.py'
    value=p.read_text(encoding='utf-8').replace('0.3.8','0.3.9').replace('0.4.8','0.4.9').replace('038-048','039-049').replace('图片保存优化与章节并行配置','缓存清理与结果提示')
    (p.parent/f'{prefix}_039_049.py').write_text(value,encoding='utf-8')
print('Prepared Windows 0.3.9 / Android 0.4.9 documentation and publication recipes')
