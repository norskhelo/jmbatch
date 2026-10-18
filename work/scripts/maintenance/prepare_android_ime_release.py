"""Prepare the explicitly authorized Android keyboard-resume release."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android'
JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.5.11 — 返回前台时保持键盘收起

## 修复内容

- 修复主界面从后台返回时，编号输入框保留焦点导致输入法自动弹出的问题。返回后保持键盘收起，点击输入框可继续正常输入。
- 保留未提交的编号文字；输入框焦点转移到页面外层，不因焦点切换主动滚动编号区域。
- “加入队列”和“添加连续编号”成功后结束本次输入、收起键盘；添加失败时保留输入内容，便于修改。
- 仅在页面恢复和本次输入结束时处理键盘，避免重复窗口焦点回调打断后续输入；下载、阅读、收藏和保存目录继续沿用原有行为。

## 版本与验证

- Android 0.5.10 → 0.5.11，versionCode 511；Windows 保持 0.3.15。沿用原应用包名、APK 签名证书和更新公钥，可覆盖安装。
- 验证包括焦点生命周期、窗口尚未就绪时的处理、连续切换、再次输入、未提交文字保留及弹窗窗口隔离的宿主回归，并执行既有 Android 检查、完整构建与签名校验。
- 当前没有连接 Android 真机；宿主测试不能代替具体手机和输入法的实测，实际系统恢复时序及界面效果仍需设备验证。
'''

def replace(path, old, new):
    text=path.read_text(encoding='utf-8')
    assert old in text,path
    path.write_text(text.replace(old,new),encoding='utf-8')

notes=ROOT/'work/release-android-0511/release-notes.md'
notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')
replace(JAVA/'Core.java','VERSION = "0.5.10"','VERSION = "0.5.11"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="510"','versionCode="511"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.5.10"','versionName="0.5.11"')
replace(ANDROID/'app/build.gradle','versionCode 510','versionCode 511')
replace(ANDROID/'app/build.gradle',"versionName '0.5.10'","versionName '0.5.11'")
plain=re.sub(r'^#{1,2} ', '', NOTES, flags=re.M).replace('- ','• ')
path=JAVA/'GithubUpdates.java';text=path.read_text(encoding='utf-8')
text,count=re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',text)
assert count==1;path.write_text(text,encoding='utf-8')
path=ROOT/'CHANGELOG.md';text=path.read_text(encoding='utf-8')
assert text.startswith('# Windows 0.3.15 / Android 0.5.10')
path.write_text(NOTES+'\n'+text,encoding='utf-8')
path=ANDROID/'README.txt';text=path.read_text(encoding='utf-8').split('Windows 0.3.15 / Android 0.5.10 —')[0]
text=text.replace('JM Batch 0.5.10','JM Batch 0.5.11').replace('release-0.3.15-0.5.10','release-android-0.5.11')
text=text.replace('JMBatch-0.5.10-Android.apk','JMBatch-0.5.11-Android.apk').replace('SHA256-release-0.3.15-0.5.10.txt','SHA256-release-android-0.5.11.txt')
text=text.replace('安装包下载（2026-10-17）','安装包下载（2026-10-18）')
path.write_text(text+plain,encoding='utf-8')
path=ROOT/'README.md';lines=path.read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines):
    if line.startswith('当前源码及正式版本：'):
        lines[i]='当前源码及正式版本：**Windows 0.3.15 / Android 0.5.11（versionCode 511）**。Android 修复主界面返回前台时自动弹出键盘的问题；Windows 保持 0.3.15。安装包、更新日志与镜像入口见下方。'
    elif line.startswith('当前正式版为 '):
        lines[i]='当前正式版为 **Windows 0.3.15 / Android 0.5.11**（[Windows 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.15-0.5.10)、[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.5.11)）。完整附件及后续更新见 [Releases 页面](https://github.com/norskhelo/jmbatch/releases)。'
    elif line.startswith('| Android '):
        lines[i]=line.replace('Android 0.5.10','Android 0.5.11').replace('release-0.3.15-0.5.10','release-android-0.5.11').replace('JMBatch-0.5.10-Android.apk','JMBatch-0.5.11-Android.apk').replace('SHA256-release-0.3.15-0.5.10.txt','SHA256-release-android-0.5.11.txt')
path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
for name in ('prepare_publication_android_058.py','publish_android_058.py'):
    path=ROOT/'work/scripts/release'/name
    text=path.read_text(encoding='utf-8').replace('0.5.8','0.5.11').replace('0.3.13','0.3.15').replace('android-058','android-0511').replace('<= 508','<= 511')
    text=text.replace('字体与按钮尺寸适配','返回前台时保持键盘收起')
    (path.parent/name.replace('058','0511')).write_text(text,encoding='utf-8')
path=ROOT/'work/scripts/maintenance/verify_android_immersive_online.py'
text=path.read_text(encoding='utf-8').replace('release-0.3.15-0.5.10','release-android-0.5.11').replace('"0.5.10"','"0.5.11"').replace("'0.5.10'","'0.5.11'").replace('"0.5.9"','"0.5.10"')
text=text.replace('release-0315-0510','release-android-0511').replace('immersive-0510','ime-0511').replace('LiveCancelUpdate','LiveImeUpdate').replace('沉浸阅读','返回前台时保持键盘收起')
text=text.replace('!=20','!=21').replace('20-release','21-release').replace('full_history_versions=20','full_history_versions=21')
(path.parent/'verify_android_ime_online.py').write_text(text,encoding='utf-8')
path=ROOT/'work/scripts/release/verify_font_commit.py'
text=path.read_text(encoding='utf-8').replace('0.5.8','0.5.11').replace('font-058','ime-0511')
(path.parent/'verify_ime_commit.py').write_text(text,encoding='utf-8')
print('Prepared Android 0.5.11 / 511; Windows stays 0.3.15')
