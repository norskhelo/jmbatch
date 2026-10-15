"""Prepare this approved first-page cover release and its publication recipes."""
from pathlib import Path
import json
import re
import shutil

ROOT=Path(__file__).resolve().parents[3]
notes='''# Windows 0.3.0 / Android 0.4.0 — 2026-10-15

## 收藏列表显示封面

- 已下载漫画 / 收藏界面新增封面缩略图，默认取漫画第一页；多章节取第一章第一页，按章节和页码顺序读取。
- 同时支持图片文件夹、ZIP 和 PDF。封面按比例缩放，保留完整页面；ZIP 内的下载信息、隐藏文件不作为封面。
- 封面在后台按可见列表加载，滚动和搜索时复用有限内存缓存，保留搜索、收藏、多选和批量操作。
- 文件缺失、损坏、加密或目录权限失效时显示占位图，不妨碍管理记录；恢复文件或授权后点击“刷新”可重试。
- 缩略图不写入漫画文件夹或 ZIP，保留既有纯图片成品结构。Android 读取系统目录中的 ZIP 时仅在应用缓存临时读取，完成后清理；超过 512 MB 的外部 ZIP 显示占位图。

## 版本与交付

- 按 0.x.0 递增：Windows 0.2.4 → 0.3.0；Android 0.3.4 → 0.4.0（versionCode 400）。保留 app.jmbatch.android 包名、原 APK 签名和更新公钥。
- 同步源码、使用说明、更新日志、安装包、SHA-256 校验文件和签名更新清单。
- 验证使用隔离素材、Windows 实际界面与成品自检、Android 宿主测试和编译；尚未连接 Android 真机验证厂商目录权限和界面显示。
'''
notes_path=ROOT/'work/release-030-040/release-notes.md'
notes_path.parent.mkdir(parents=True,exist_ok=True);notes_path.write_text(notes,encoding='utf-8')
plain=re.sub(r'^#+ ','',notes,flags=re.M).replace('\n- ','\n• ')
changelog=ROOT/'CHANGELOG.md'
old=changelog.read_text(encoding='utf-8')
assert not old.startswith('# Windows 0.3.0')
changelog.write_text(notes+'\n'+old,encoding='utf-8')
for name,old,new in [
    ('work/jmbatch/core.py','VERSION = "0.2.4"','VERSION = "0.3.0"'),
    ('work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','VERSION = "0.3.4"','VERSION = "0.4.0"'),
    ('work/jmbatch-android/app/src/main/AndroidManifest.xml','versionCode="304" android:versionName="0.3.4"','versionCode="400" android:versionName="0.4.0"'),
    ('work/jmbatch-android/app/build.gradle',"versionCode 304; versionName '0.3.4'","versionCode 400; versionName '0.4.0'")]:
    path=ROOT/name;text=path.read_text(encoding='utf-8');assert old in text;path.write_text(text.replace(old,new),encoding='utf-8')
for name,prefix,value in [('work/jmbatch/updates.py','CURRENT_NOTES = ',repr(plain)),
    ('work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java','    private static final String CURRENT_NOTES=',json.dumps(plain,ensure_ascii=False)+';')]:
    path=ROOT/name;lines=path.read_text(encoding='utf-8').splitlines();index=next(i for i,line in enumerate(lines) if line.startswith(prefix));lines[index]=prefix+value;path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
for name in ['README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    path=ROOT/name;text=path.read_text(encoding='utf-8')
    if name.endswith('.txt'):text=text.split('Windows 0.2.4 / Android 0.3.4 —')[0]
    text=text.replace('0.2.4','0.3.0').replace('0.3.4','0.4.0').replace('versionCode 304','versionCode 400')
    if name=='README.md':text=text.replace('本版统一图片文件夹和 ZIP 结构：单章节图片平铺，多章节分目录；成品不含下载信息文件。','本版在漫画库和收藏列表显示第一页封面，支持图片目录、ZIP 和 PDF，后台加载并保留搜索与多选操作。')
    else:text+='6. 漫画库 / 收藏列表默认显示第一页封面，多章节取第一章第一页。无法读取时显示占位图；恢复文件或授权后点击刷新。\n\n'+plain
    path.write_text(text,encoding='utf-8')
for old,new in [('prepare_publication_024_034.py','prepare_publication_030_040.py'),('publish_024_034.py','publish_030_040.py')]:
    directory=ROOT/'work/scripts/release';text=(directory/old).read_text(encoding='utf-8').replace('0.2.4','0.3.0').replace('0.3.4','0.4.0').replace('024-034','030-040').replace('纯图片目录与压缩包','收藏列表第一页封面');(directory/new).write_text(text,encoding='utf-8')
text=(ROOT/'work/scripts/maintenance/verify_clean_layout_online.py').read_text(encoding='utf-8').replace('0.2.4','0.3.0').replace('0.3.4','0.4.0').replace('0.2.3','0.2.4').replace('clean-layout-024-034','covers-030-040').replace('release-024-034','release-030-040').replace('图片目录与 ZIP 统一结构','收藏列表显示封面')
(ROOT/'work/scripts/maintenance/verify_cover_online.py').write_text(text,encoding='utf-8')
licenses=ROOT/'work/venv/Lib/site-packages/pypdfium2-5.14.0.dist-info/licenses'
shutil.copytree(licenses,ROOT/'work/jmbatch/THIRD_PARTY_LICENSES/pypdfium2',dirs_exist_ok=True)
index=ROOT/'work/jmbatch/THIRD_PARTY_LICENSES/INDEX.txt';index.write_text(index.read_text(encoding='utf-8')+'\npypdfium2 5.14.0 / PDFium\nSee pypdfium2/LICENSES and pypdfium2/data/windows_x64/BUILD_LICENSES for wrapper and bundled binary licenses.\n',encoding='utf-8')
skill=ROOT/'.agents/skills/jmbatch-maintenance/SKILL.md';text=skill.read_text(encoding='utf-8');text=text.replace('当前阶段先本地实现并提供隔离示例的界面效果图，暂停 Git 推送和 Release 发布，等待用户看图后的明确后续指示；不能沿用原请求自动推送或发布。','已用隔离示例展示 Windows 实际界面，用户看图后明确要求“推送”，恢复完整双端更新、构建签名、源码与日志推送以及正式 Release 发布；此前暂停限制已由本次明确指示解除。');skill.write_text(text,encoding='utf-8')
