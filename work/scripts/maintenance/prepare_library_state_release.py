"""Prepare the paired retained-library release and its verification recipes."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.18 / Android 0.5.14 — 阅读保留漫画库

## 漫画库与阅读

- 从漫画库进入阅读后保留原漫画库页面，返回时继续原来的浏览位置，无需重新打开漫画库。
- 保留搜索文字、仅显示收藏筛选、列表滚动位置，以及批量处理模式和已选漫画。
- 阅读中修改收藏后，漫画库同步显示最新结果，并尽量保持当前可见漫画的位置；该漫画不再符合筛选时，显示附近仍符合条件的漫画。
- Windows 再次打开已有漫画库窗口或刷新列表时保留位置与选择，避免阅读后返回列表顶部。
- Android 返回阅读前的漫画库时收起搜索键盘，并保存页面状态供系统重建主页面时恢复。主动关闭漫画库仍正常关闭并释放资源。

## 版本与验证

- Windows 0.3.17 → 0.3.18；Android 0.5.13 → 0.5.14（versionCode 514）。沿用原 Android 包名、APK 签名证书和更新公钥。
- 验证覆盖 Windows 实际漫画库/阅读器窗口、反复进出、收藏筛选与列表变化，以及源码和冻结成品；Android 覆盖生产状态处理器宿主回归、状态保存恢复、完整构建和原签名核验。
- 未连接 Android 真机，返回界面、系统回收重建及输入法的设备表现仍需真机确认。
'''
folder = ROOT/'work/release-0318-0514'
folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes, encoding='utf-8')
p = ROOT/'CHANGELOG.md'
s = p.read_text(encoding='utf-8')
if not s.startswith(notes): p.write_text(notes+'\n'+s, encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p = ROOT/name
    s = p.read_text(encoding='utf-8').replace('0.3.17','0.3.18').replace('0.5.13','0.5.14').replace('versionCode 513','versionCode 514').replace('versionCode="513"','versionCode="514"')
    p.write_text(s, encoding='utf-8')
plain = notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name
    s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'))
    p.write_text(s,encoding='utf-8')
for name,version in (('work/jmbatch/README.txt','0.3.18'),('work/jmbatch-android/README.txt','0.5.14')):
    p=ROOT/name
    s=p.read_text(encoding='utf-8').split('\nWindows 0.3.17 / Android 0.5.13 — ')[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+','JM Batch '+version,s)
    p.write_text(s+'\n'+plain,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8');header,body=s.split('## 下载与导出',1)
header=header.replace('0.3.17','0.3.18').replace('0.5.13','0.5.14').replace('versionCode 513','versionCode 514')
header=header.replace('漫画库批量处理支持一次导出多本漫画，统一选择格式与目录。','进入阅读后保留漫画库页面，返回继续原来的搜索、筛选、滚动位置和批量选择。')
body=body.replace('在任务列表或漫画库中打开漫画，即可使用内置阅读器。','在任务列表或漫画库中打开漫画，即可使用内置阅读器。从漫画库进入阅读会保留原页面，返回继续原来的搜索、收藏筛选、滚动位置和批量选择；阅读中修改收藏会同步刷新，尽量保留当前可见漫画的位置。')
p.write_text(header+'## 下载与导出'+body,encoding='utf-8')
replacements={'0.3.17':'0.3.18','0.3.16':'0.3.17','0.5.13':'0.5.14','0.5.12':'0.5.13',
              '0317-0513':'0318-0514','0317_0513':'0318_0514','batch-export-0513':'library-state-0514',
              'batch_export':'library_state','漫画库批量导出':'阅读保留漫画库','<= 513':'<= 514',
              'range(1,18)':'range(1,19)','!=23':'!=24','23-release':'24-release','full_history_versions=23':'full_history_versions=24'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True)))
for old,new in (
    ('release/prepare_publication_0317_0513.py','release/prepare_publication_0318_0514.py'),
    ('release/publish_0317_0513.py','release/publish_0318_0514.py'),
    ('release/verify_batch_export_commit.py','release/verify_library_state_commit.py'),
    ('maintenance/verify_batch_export_online.py','maintenance/verify_library_state_online.py'),
    ('maintenance/verify_android_batch_export_online.py','maintenance/verify_android_library_state_online.py')):
    s=pattern.sub(lambda m:replacements[m[0]],(ROOT/'work/scripts'/old).read_text(encoding='utf-8'))
    (ROOT/'work/scripts'/new).write_text(s,encoding='utf-8')
print('Prepared Windows 0.3.18 / Android 0.5.14')
