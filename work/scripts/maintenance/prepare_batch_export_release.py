"""Prepare matching versions, changelog and release verification recipes."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
notes='''# Windows 0.3.17 / Android 0.5.13 — 漫画库批量导出

## 漫画库

- 批量处理支持一次导出多本漫画。长按进入批量模式，勾选多本后点击“导出漫画”，统一选择导出格式和保存目录。
- 支持混选图片文件夹、ZIP 和 PDF，逐本导出为独立文件，不合并不同漫画；保留纯编号命名和按章节分别导出 PDF 的选项。
- 导出时显示当前漫画和总进度，结束后汇总成功、失败、未处理的漫画数量及已保存项目数，并将已导出的结果加入漫画库。
- 单本失败后继续处理其余漫画；同名文件拒绝覆盖并列出失败原因。停止导出会清理当前漫画未完成的输出，保留此前完成的结果和全部源漫画。
- Android 停止导出后保持进度提示，等待清理与汇总完成；完成后刷新漫画库。导出前继续检查下载与其他文件操作状态。

## 版本与验证

- Windows 0.3.16 → 0.3.17；Android 0.5.12 → 0.5.13（versionCode 513）。保留原应用包名、APK 签名证书和更新公钥。
- 保留已有漫画、收藏、阅读进度、书签和下载设置，延续点击阅读、长按批量处理的操作方式。
- 验证覆盖 Windows 混合格式实际导出、失败继续、取消回滚、界面及冻结成品，Android 生产批量调度宿主回归、完整构建与签名校验。未连接 Android 真机，手机界面及目录授权流程仍需设备验证。
'''
folder=ROOT/'work/release-0317-0513';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=ROOT/'CHANGELOG.md';s=p.read_text(encoding='utf-8')
if not s.startswith(notes):p.write_text(notes+'\n'+s,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=ROOT/name;s=p.read_text(encoding='utf-8')
    s=s.replace('0.3.16','0.3.17').replace('0.5.12','0.5.13').replace('versionCode 512','versionCode 513').replace('versionCode="512"','versionCode="513"')
    p.write_text(s,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name
    s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'))
    p.write_text(s,encoding='utf-8')
for name,version in (('work/jmbatch/README.txt','0.3.17'),('work/jmbatch-android/README.txt','0.5.13')):
    p=ROOT/name;s=p.read_text(encoding='utf-8').split('\nWindows 0.3.16 / Android 0.5.12 — ')[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+','JM Batch '+version,s)
    s+='\n'+plain;p.write_text(s,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8');header,body=s.split('## 下载与导出',1)
header=header.replace('0.3.16','0.3.17').replace('0.5.12','0.5.13').replace('versionCode 512','versionCode 513')
header=header.replace('漫画库点击直接阅读，长按进入批量处理。','漫画库批量处理支持一次导出多本漫画，统一选择格式与目录。')
body=body.replace('也可在漫画库长按一本 PDF、ZIP 或图片文件夹进入批量处理，再点击“导出漫画”。','也可在漫画库长按进入批量处理，勾选一本或多本 PDF、ZIP、图片文件夹，再点击“导出漫画”。多本共用格式与目录，逐本独立导出；单本失败继续，停止时保留已完成结果和全部源漫画。')
body=body.replace('同名输出会停止并提示，不覆盖已有文件。','同名输出会跳过该本并提示，不覆盖已有文件；批量导出继续处理其余漫画。')
p.write_text(header+'## 下载与导出'+body,encoding='utf-8')
replacements={'0.3.16':'0.3.17','0.3.15':'0.3.16','0.5.12':'0.5.13','0.5.11':'0.5.12',
              '0316-0512':'0317-0513','0316_0512':'0317_0513','library-0512':'batch-export-0513',
              'library_interaction':'batch_export','漫画库操作优化':'漫画库批量导出','<= 512':'<= 513',
              'range(1,17)':'range(1,18)','!=22':'!=23','22-release':'23-release','full_history_versions=22':'full_history_versions=23'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True)))
for old,new in (
    ('release/prepare_publication_0316_0512.py','release/prepare_publication_0317_0513.py'),
    ('release/publish_0316_0512.py','release/publish_0317_0513.py'),
    ('release/verify_library_interaction_commit.py','release/verify_batch_export_commit.py'),
    ('maintenance/verify_library_interaction_online.py','maintenance/verify_batch_export_online.py'),
    ('maintenance/verify_android_library_interaction_online.py','maintenance/verify_android_batch_export_online.py')):
    s=pattern.sub(lambda m:replacements[m[0]],(ROOT/'work/scripts'/old).read_text(encoding='utf-8'))
    (ROOT/'work/scripts'/new).write_text(s,encoding='utf-8')
print('Prepared Windows 0.3.17 / Android 0.5.13 notes and release recipes')
