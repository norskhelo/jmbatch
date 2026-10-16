"""Prepare the 0.3.6 / 0.4.6 chapter-selection release locally."""
from pathlib import Path
import json
import re

root = Path(__file__).resolve().parents[3]
def edit(name, old, new):
    p = root / name
    text = p.read_text(encoding='utf-8')
    assert old in text, (name, old[:100])
    p.write_text(text.replace(old, new), encoding='utf-8')

edit('work/jmbatch/app.py', 'STATUS = {', 'STATUS = {"selecting": "待选章节", ')
edit('work/jmbatch/worker.py', 'emit({"type": "chapter_plan", "chapters": chosen})', 'task["selected_chapters"] = chosen\n            emit({"type": "chapter_plan", "chapters": chosen})')
edit('work/jmbatch/worker.py', 'f"读取章节 {index}/{len(photos)}"', 'f"读取所选章节 {len(self.expected_chapters)}/{len(photos)}"')
store='work/jmbatch-android/app/src/main/java/app/jmbatch/android/Store.java'
edit(store, 'case "running": return "下载中";', 'case "selecting": return "待选章节"; case "running": return "下载中";')
edit(store, 't.status = "queued"; t.phase = "排队中";', 't.status = !t.chapterOptions.isEmpty() && t.selectedChapters.isEmpty() ? "selecting" : "queued"; t.phase = t.status.equals("selecting") ? "请选择下载章节" : "排队中";')
edit(store, 'if (t.status.equals("queued")) { t.status = "paused";', 'if (t.status.equals("queued") || t.status.equals("selecting")) { t.status = "paused";')
# finishQueue must keep pending choices; only an explicit pause pauses selection.
edit('work/jmbatch-android/app/src/main/java/app/jmbatch/android/DownloadService.java',
     'try{store.pauseQueued();}catch(Exception error){store.note=error.getMessage();}\n        if(wake.isHeld())',
     'try{store.pauseQueuedOnly();}catch(Exception error){store.note=error.getMessage();}\n        if(wake.isHeld())')
edit(store, '    public File cache(Task task)', '    public synchronized void pauseQueuedOnly() throws IOException { for(Task t:tasks)if(t.status.equals("queued")){t.status="paused";t.phase="已暂停";}save(); }\n    public File cache(Task task)')

# Existing whole-album fixtures explicitly request all chapters; new tests cover the default.
for name in ['diagnostics.py','tests/test_albums.py','tests/test_app.py','tests/test_download_covers.py','tests/test_resume.py']:
    p=root/'work/jmbatch'/name
    text=p.read_text(encoding='utf-8').replace('Settings(output=', 'Settings(download_all_chapters=True, output=')
    p.write_text(text,encoding='utf-8')
edit('work/jmbatch/diagnostics.py', 'from worker import run_download', 'from chapters import ChapterChoiceRequired\nfrom worker import run_download')
# The above import appears once at module scope and once inside a function; repair its indent.
edit('work/jmbatch/diagnostics.py', '        from chapters import ChapterChoiceRequired\nfrom worker import run_download', '        from worker import run_download')
edit('work/jmbatch/diagnostics.py', '        run_download(task, cookie, channel.put, client_factory=FixtureClient)\n    except Exception',
     '        run_download(task, cookie, channel.put, client_factory=FixtureClient)\n    except ChapterChoiceRequired as choice:\n        channel.put({"type": "chapters", "chapters": choice.chapters})\n    except Exception')

notes='''# Windows 0.3.6 / Android 0.4.6 — 2026-10-16

## 下载章节选择

- 多章节漫画获取章节列表后，弹出下载章节选择，可多选、全选、清空；至少选择一章才会开始下载。
- 下载设置新增“默认下载全章节”，默认关闭。开启后，新任务和未选择章节的手动重试任务跳过弹窗；单章节直接下载。
- 关闭弹窗或选择“稍后选择”会暂停该任务，点击“开始 / 继续”可再次选择。待选任务不占下载名额，多个任务依次弹窗；Android 在应用返回前台后显示待选章节。
- 只读取和下载选中章节的图片；PDF、ZIP、文件夹均适用。选择随任务保存，暂停、重启、重试和自动重连沿用原选择；已选章节不会因全章节设置改变而增加。
- 保留原章节顺序与编号以正确复用缓存；单个所选章节的 ZIP / 文件夹图片平铺，多个所选章节按原章节编号分目录，封面取首个所选章节第一页。

## 版本与验证

- Windows 升至 0.3.6；Android 升至 0.4.6（versionCode 406），沿用原包名、APK 签名身份和更新公钥。
- 使用离线章节素材验证选择、默认全选、缓存续传、队列调度和三种成品；Windows 源码与冻结成品执行实际界面自检。
- Android 执行宿主测试、编译和签名核验；未进行 Android 真机界面或真实网站下载验证。
- 同步源码、使用说明、同版日志、双端安装包、SHA-256 校验文件和签名更新清单。
'''
folder=root/'work/release-036-046';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=root/'CHANGELOG.md';p.write_text(notes+'\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
for name in ['work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle','README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    p=root/name;text=p.read_text(encoding='utf-8').replace('0.3.5','0.3.6').replace('0.4.5','0.4.6').replace('versionCode 405','versionCode 406').replace('versionCode="405"','versionCode="406"')
    p.write_text(text,encoding='utf-8')
edit('README.md','本版提供明确的手动检查更新入口，关闭启动自动检查后也可随时检查。','本版支持获取章节后选择下载范围，可在设置中默认下载全章节。')
for name in ['README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    p=root/name;text=p.read_text(encoding='utf-8')
    p.write_text(text+'\n多章节下载：获取章节后选择要下载的章节，支持多选、全选和清空。设置中的“默认下载全章节”默认关闭，开启后新任务自动下载全部章节。关闭选择框会暂停该任务，点击开始可重新选择；已确认的选择在暂停、重启和重试后保留。仅选一章时 ZIP / 文件夹图片平铺，多章按原章节编号分目录。\n',encoding='utf-8')
plain=notes.replace('# ','').replace('## ','').replace('- ','• ')
for name in ['work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java']:
    p=root/name;text=p.read_text(encoding='utf-8')
    text=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if name.endswith('.java') else ''),text)
    p.write_text(text,encoding='utf-8')
for prefix in ['prepare_publication','publish']:
    source=root/f'work/scripts/release/{prefix}_035_045.py'
    text=source.read_text(encoding='utf-8').replace('0.3.5','0.3.6').replace('0.4.5','0.4.6').replace('035-045','036-046').replace('手动检查更新','下载章节选择')
    (source.parent/f'{prefix}_036_046.py').write_text(text,encoding='utf-8')
skill=root/'.agents/skills/jmbatch-maintenance/SKILL.md'
text=skill.read_text(encoding='utf-8').replace('## 更新范围与发布权限\n','## 更新范围与发布权限\n\n- 2026-10-16 多章节下载选择：用户要求“更新，推送：多章节下载时，获取章节后弹出下载章节选择（可在设置中设置默认下载全章节）”。适用于 Windows / Android；默认获取多章节列表后选择，设置可跳过选择下载全章节；单章直接下载，支持多选、全选、清空及稍后选择，确认后保留任务选择以便暂停、重启和重试。按完整更新流程交付 Windows 0.3.6 / Android 0.4.6（versionCode 406），原密钥签名、源码和日志推送、正式 Release 发布。本条记录要求，完成情况待验证后追加。\n')
skill.write_text(text,encoding='utf-8')
