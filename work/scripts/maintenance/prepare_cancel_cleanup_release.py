"""Prepare the authorized Windows/Android cancellation cleanup update."""
from pathlib import Path
import json
import re

root=Path(__file__).resolve().parents[3]
notes='''# Windows 0.3.10 / Android 0.5.4 — 2026-10-17

## 取消任务后自动删除文件与记录

- 取消未完成任务后，自动停止下载，后台删除该任务已下载图片、章节缓存、下载/导出临时文件及尚未确认完成的任务输出；清理成功后自动移除队列记录，无需再手动删除。
- 取消与暂停明确区分：暂停继续保留完整图片和断点续传；取消会放弃进度，即使设置了保留图片缓存也会删除该取消任务的缓存。重新添加相同编号时创建新任务。
- 清理先等待下载进程及图片、章节工作线程退出，避免清理后又写回文件；重复取消不会重复启动清理，取消单个任务不影响其他任务。
- 显示取消清理状态和结果。文件占用、目录权限失效或异常路径导致清理失败时保留任务记录；再次点击取消或重试会重试清理，不会重新下载。应用重开后继续处理未完成的取消清理。
- 仅清理该任务记录的文件和缓存，不按漫画编号或文件名批量删除；保护其他任务、已完成任务、已有同名成品、收藏与书签，拒绝跟随链接目录。旧版已取消记录不会在升级时被批量删除，可再次取消以清理。

## 版本与验证

- Windows 0.3.9 → 0.3.10；Android 0.5.3 → 0.5.4（versionCode 504），沿用 Android 包名、APK 签名证书与更新公钥。
- 验证取消后的文件及队列持久化、暂停保护、重复取消、失败重试、重启恢复、成品保存竞争和链接路径边界；使用隔离测试数据，不清理用户真实下载。
- Windows 执行回归、源码与冻结成品自检；Android 执行宿主检查、编译与原证书签名核验。未连接 Android 真机，不将宿主结果作为手机实测。
- 发布双端安装包、同版日志、SHA-256 校验文件、更新清单及原密钥签名，并推送源码和使用说明。
'''
folder=root/'work/release-0310-054';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=root/'CHANGELOG.md';value=p.read_text(encoding='utf-8')
if not value.startswith(notes):p.write_text(notes+'\n'+value,encoding='utf-8')
for name in ['work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle']:
    p=root/name;value=p.read_text(encoding='utf-8').replace('0.3.9','0.3.10').replace('0.5.3','0.5.4').replace('versionCode 503','versionCode 504').replace('versionCode="503"','versionCode="504"')
    p.write_text(value,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ['work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java']:
    p=root/name;value=p.read_text(encoding='utf-8')
    value=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if name.endswith('.java') else ''),value)
    p.write_text(value,encoding='utf-8')
for name in ['README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    p=root/name;value=p.read_text(encoding='utf-8')
    value=re.split(r'\n(?:Windows 0\.3\.9 / Android 0\.4\.9|Android 0\.5\.3) — ',value)[0].rstrip()+'\n'
    value=value.replace('release-0.3.9-0.4.9','release-0.3.10-0.5.4').replace('release-android-0.5.3','release-0.3.10-0.5.4')
    value=value.replace('0.3.9','0.3.10').replace('0.5.3','0.5.4').replace('versionCode 503','versionCode 504')
    value=value.replace('Android 0.5.4 优化下载取消与暂停响应，后台并行关闭当前连接，保留完整图片及断点续传。','本版取消任务后自动删除任务文件和记录；暂停仍保留完整图片及断点续传。')
    value=value.replace('取消单个任务不会影响其他任务；暂停会停止全部下载并保留缓存。','取消会删除该任务文件和记录，不影响其他任务；暂停会停止全部下载并保留缓存。')
    value=value.replace('SHA256-release-android-0.5.4.txt','SHA256-release-0.3.10-0.5.4.txt')
    if name!='README.md':value+='\n'+plain
    else:value+='\n## 取消任务\n\n取消未完成任务会删除该任务文件、缓存和队列记录；暂停仍保留续传。清理在后台执行，失败时保留记录并提示重试，重开应用可继续取消清理。已完成任务不受影响。\n'
    p.write_text(value,encoding='utf-8')
p=root/'work/jmbatch/app.py';value=p.read_text(encoding='utf-8').replace('STATUS = {','STATUS = {"cancelling": "取消清理中", "cancel_failed": "取消清理失败", ').replace('text="取消选中"','text="取消并删除"')
p.write_text(value,encoding='utf-8')
for prefix in ('prepare_publication','publish'):
    p=root/f'work/scripts/release/{prefix}_039_049.py'
    value=p.read_text(encoding='utf-8').replace('0.3.9','0.3.10').replace('0.4.9','0.5.4').replace('039-049','0310-054').replace('缓存清理与结果提示','取消任务自动删除文件与记录')
    if prefix=='publish':
        newer=(p.parent/'publish_android_053.py').read_text(encoding='utf-8')
        preflight=newer.split('def preflight():',1)[1].split('\ndef check_assets',1)[0].replace('<= 503','<= 504')
        value=value.split('def preflight():',1)[0]+'def preflight():'+preflight+'\ndef check_assets'+value.split('\ndef check_assets',1)[1]
    (p.parent/f'{prefix}_0310_054.py').write_text(value,encoding='utf-8')
p=root/'.agents/skills/jmbatch-maintenance/SKILL.md';value=p.read_text(encoding='utf-8')
entry='- 2026-10-17 取消任务自动清理：用户要求“更新，推送：取消任务后自动删除文件以及记录”。默认适用于 Windows 与 Android；取消后等待下载线程退出，后台删除任务图片、章节缓存、临时输出及未确认完成输出，成功后删除队列记录；暂停仍续传，失败保留记录供重试，保护其他任务与已完成文件。计划 Windows 0.3.10 / Android 0.5.4（504），完成验证、原密钥签名、分版本交付、源码日志推送与正式 Release 发布；当前实现与验收进行中。\n\n'
value=value.replace('## 更新范围与发布权限\n\n','## 更新范围与发布权限\n\n'+entry,1);p.write_text(value,encoding='utf-8')
print('Prepared cancellation cleanup release 0.3.10 / 0.5.4')
