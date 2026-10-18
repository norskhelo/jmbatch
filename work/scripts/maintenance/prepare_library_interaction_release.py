"""Prepare matching source versions, user notes and release verification recipes."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.16 / Android 0.5.12 — 漫画库操作优化

## 漫画库

- 点击漫画即可打开内置阅读器，继续上次阅读位置；无需先勾选或双击。
- 长按漫画进入批量处理，并自动选中当前漫画。批量模式中点击只切换勾选，可全选、反选、取消选择，批量收藏、取消收藏、删除文件或仅移除记录。
- 点击“完成”退出批量处理并清空选择；Windows 也可按 Esc，Android 可按返回。另保留“批量处理”按钮，方便鼠标、键盘和辅助功能操作。
- 平时收起批量工具和选择标记，留出更多漫画列表空间。选中一本时可阅读、导出或打开保存目录；Android 的“更多操作”保留分享与目录入口。
- 长按松手不误打开漫画，拖动或滚动取消待触发手势。搜索或切换收藏筛选时清空选择，刷新保留仍然可见的已选漫画，避免对隐藏项目执行批量操作。
- 删除文件和仅移除记录继续分别确认；文件删除前仍需暂停下载。未选择漫画或选择多本时，不可用的操作按钮置灰。

## 版本与验证

- Windows 0.3.15 → 0.3.16；Android 0.5.11 → 0.5.12（versionCode 512）。保留原应用包名、APK 签名证书和更新公钥。
- 保留已有漫画、收藏、阅读进度、书签和下载设置，兼容图片文件夹、ZIP、PDF。
- 验证覆盖 Windows 真实窗口事件及冻结成品、Android 生产事件处理器的宿主回归、既有检查、完整构建与签名校验。未连接 Android 真机，手机手势与视觉效果仍需设备验证。
'''
folder=ROOT/'work/release-0316-0512';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=ROOT/'CHANGELOG.md';s=p.read_text(encoding='utf-8')
if not s.startswith(notes):p.write_text(notes+'\n'+s,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=ROOT/name;s=p.read_text(encoding='utf-8')
    s=s.replace('0.3.15','0.3.16').replace('0.5.11','0.5.12').replace('versionCode 511','versionCode 512').replace('versionCode="511"','versionCode="512"')
    p.write_text(s,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name
    s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'))
    p.write_text(s,encoding='utf-8')
for name,previous,version in (('work/jmbatch/README.txt','\nWindows 0.3.15 / Android 0.5.10 — ','0.3.16'),
                              ('work/jmbatch-android/README.txt','\nAndroid 0.5.11 — ','0.5.12')):
    p=ROOT/name;s=p.read_text(encoding='utf-8').split(previous)[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+', 'JM Batch '+version,s)
    s+='\n'+plain;p.write_text(s,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8');header,body=s.split('## 下载与导出',1)
header=header.replace('0.3.15','0.3.16').replace('0.5.11','0.5.12').replace('versionCode 511','versionCode 512')
header=header.replace('release-0.3.16-0.5.10','release-0.3.16-0.5.12').replace('release-android-0.5.12','release-0.3.16-0.5.12')
header=header.replace('Android 修复主界面返回前台时自动弹出键盘的问题；Windows 保持 0.3.16。','漫画库点击直接阅读，长按进入批量处理。')
# One shared release and checksum for both installers.
lines=header.splitlines();lines=[line for line in lines if not line.startswith('| Android 0.5.12 的 SHA-256')]
header='\n'.join(lines)+'\n\n'
header=header.replace('Windows 0.3.16 的 SHA-256 校验文件','双端 SHA-256 校验文件').replace('SHA256-release-0.3.16-0.5.10','SHA256-release-0.3.16-0.5.12')
body=body.replace('3. 在任务详情或“漫画库”选择任一 PDF、ZIP 或图片文件夹，点击“导出漫画”。','3. 在任务详情点击“导出漫画”；也可在漫画库长按一本 PDF、ZIP 或图片文件夹进入批量处理，再点击“导出漫画”。')
body=body.replace('漫画库支持排序图片目录及旧版 PDF / ZIP，提供搜索、收藏、扫描和批量管理。','漫画库点击直接阅读、长按进入批量处理；点击“完成”退出。Windows 支持 Esc，Android 支持返回；提供搜索、收藏、扫描和批量管理，兼容图片目录及 PDF / ZIP。')
p.write_text(header+'## 下载与导出'+body,encoding='utf-8')

replacements={'0.3.15':'0.3.16','0.3.14':'0.3.15','0.5.10':'0.5.12','0.5.9':'0.5.11',
              '0315-0510':'0316-0512','0315_0510':'0316_0512','immersive-0510':'library-0512',
              'immersive':'library_interaction','沉浸阅读':'漫画库操作优化','<= 510':'<= 512',
              'range(1,16)':'range(1,17)','!=20':'!=22','20-release':'22-release','full_history_versions=20':'full_history_versions=22'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True)))
for old,new in (
    ('release/prepare_publication_0315_0510.py','release/prepare_publication_0316_0512.py'),
    ('release/publish_0315_0510.py','release/publish_0316_0512.py'),
    ('release/verify_immersive_commit.py','release/verify_library_interaction_commit.py'),
    ('maintenance/verify_immersive_online.py','maintenance/verify_library_interaction_online.py'),
    ('maintenance/verify_android_immersive_online.py','maintenance/verify_android_library_interaction_online.py')):
    s=pattern.sub(lambda m:replacements[m[0]],(ROOT/'work/scripts'/old).read_text(encoding='utf-8'))
    (ROOT/'work/scripts'/new).write_text(s,encoding='utf-8')
print('Prepared Windows 0.3.16 / Android 0.5.12 notes and release recipes')
