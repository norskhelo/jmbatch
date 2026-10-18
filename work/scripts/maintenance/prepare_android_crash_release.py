"""Prepare the authorized Android library crash fix release."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ANDROID = ROOT/'work/jmbatch-android'
JAVA = ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES = '''# Android 0.5.18 — 漫画库闪退修复

## 修复内容

- 修复 Android 0.5.17 在手机触摸模式下，点开有漫画的漫画库立即闪退的问题。
- 修正漫画库列表/平铺控件的滚动位置恢复方式，避免进入页面或刷新时访问无效条目。
- 保留列表和平铺切换、批量选择，以及刷新和重新打开漫画库后的浏览位置；忽略重复的显示方式回调，避免切换时回到顶部。

## 版本与验证

- Android 0.5.17 → 0.5.18，versionCode 518；Windows 保持 0.3.20。沿用原包名、APK 签名证书和更新公钥，可覆盖安装。
- Android 10 框架触摸模式回归覆盖空库、有漫画、主界面入口、显示切换、批量选择及刷新重开定位。同一组 7 项测试中，原代码 4 项越界异常，修复后全部通过；执行完整 Android 宿主回归、编译与原证书签名校验。
- 当前 ADB 尚未识别手机，未完成真机验收；框架回归不等同于荣耀设备实际验证。
'''

def replace(path, old, new):
    text = path.read_text(encoding='utf-8')
    assert old in text, path
    path.write_text(text.replace(old, new), encoding='utf-8')

notes = ROOT/'work/release-android-0518/release-notes.md'
notes.parent.mkdir(parents=True, exist_ok=True)
notes.write_text(NOTES, encoding='utf-8')
replace(JAVA/'Core.java', 'VERSION = "0.5.17"', 'VERSION = "0.5.18"')
replace(ANDROID/'app/src/main/AndroidManifest.xml', 'versionCode="517"', 'versionCode="518"')
replace(ANDROID/'app/src/main/AndroidManifest.xml', 'versionName="0.5.17"', 'versionName="0.5.18"')
replace(ANDROID/'app/build.gradle', 'versionCode 517', 'versionCode 518')
replace(ANDROID/'app/build.gradle', "versionName '0.5.17'", "versionName '0.5.18'")
plain = re.sub(r'^#{1,2} ', '', NOTES, flags=re.M).replace('- ', '• ')
path = JAVA/'GithubUpdates.java'
text, count = re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',
    lambda m: 'private static final String CURRENT_NOTES='+json.dumps(plain, ensure_ascii=False)+';', path.read_text(encoding='utf-8'))
assert count == 1
path.write_text(text, encoding='utf-8')
path = ROOT/'CHANGELOG.md'; text = path.read_text(encoding='utf-8')
assert text.startswith('# 未发布 — Android 漫画库进入闪退修复')
text = text[text.index('# Windows 0.3.20 / Android 0.5.17'):]
path.write_text(NOTES+'\n'+text, encoding='utf-8')
path = ANDROID/'README.txt'
text = path.read_text(encoding='utf-8').split('Windows 0.3.20 / Android 0.5.17 —')[0].rstrip()
text = text.replace('JM Batch 0.5.17', 'JM Batch 0.5.18')
text = text.replace('SHA256-release-0.3.20-0.5.17.txt', 'SHA256-release-android-0.5.18.txt')
text = text.replace('release-0.3.20-0.5.17', 'release-android-0.5.18').replace('JMBatch-0.5.17-Android.apk', 'JMBatch-0.5.18-Android.apk')
path.write_text(text+'\n\n'+plain, encoding='utf-8')
path = ROOT/'README.md'; lines = path.read_text(encoding='utf-8').splitlines(); result = []
for line in lines:
    if line.startswith('当前源码及正式版本：'):
        line = '当前源码及正式版本：**Windows 0.3.20 / Android 0.5.18（versionCode 518）**。Android 修复点开漫画库立即闪退，保留列表/平铺切换、批量选择与浏览位置。安装包、更新日志与镜像入口见下方。'
    elif line.startswith('当前正式版为 '):
        line = '当前正式版为 **Windows 0.3.20 / Android 0.5.18**（[Windows 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.20-0.5.17)、[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.5.18)）。完整附件及后续更新见 [Releases 页面](https://github.com/norskhelo/jmbatch/releases)。'
    elif line.startswith('| Android '):
        line = line.replace('Android 0.5.17', 'Android 0.5.18').replace('SHA256-release-0.3.20-0.5.17.txt', 'SHA256-release-android-0.5.18.txt').replace('release-0.3.20-0.5.17', 'release-android-0.5.18').replace('JMBatch-0.5.17-Android.apk', 'JMBatch-0.5.18-Android.apk')
    result.append(line)
path.write_text('\n'.join(result)+'\n', encoding='utf-8')

# Keep historical recipes intact. Each generated recipe is reviewed before use.
changes = {'0.5.16':'0.5.18', '0.5.15':'0.5.17', '0.3.19':'0.3.20', '0.3.18':'0.3.19',
    '0516':'0518', 'choice-animation':'library-crash', '516':'518',
    '批量选择显示修复':'漫画库闪退修复', 'LiveChoiceUpdate':'LiveLibraryCrashUpdate',
    '!=26':'!=28', '26-release':'28-release', 'full_history_versions=26':'full_history_versions=28',
    'f810fdeb8edaba73e19b12589169f5392f782cf3':'72b2b90d9d09f3611109c05d68a29483ec611821',
    'prepare_android_choice_release.py':'prepare_android_crash_release.py',
    'verify_android_choice_online.py':'verify_android_crash_online.py',
    'verify_choice_commit.py':'verify_crash_commit.py',
    '1340':'1347', '11962':'12430',
    'Action layout: 96 synthetic font/scale/width scenarios, 11962 checks passed (not Android rendering)':
        'Action layout: 96 synthetic font/scale/width scenarios, 18 grid/list scenarios, 12430 checks passed (not Android rendering)'}
pattern = re.compile('|'.join(re.escape(k) for k in sorted(changes, key=len, reverse=True)))
for folder, old, new in (
    ('release', 'prepare_publication_android_0516.py', 'prepare_publication_android_0518.py'),
    ('release', 'publish_android_0516.py', 'publish_android_0518.py'),
    ('release', 'audit_android_0516.py', 'audit_android_0518.py'),
    ('release', 'verify_choice_commit.py', 'verify_crash_commit.py'),
    ('maintenance', 'verify_android_choice_online.py', 'verify_android_crash_online.py')):
    source = ROOT/'work/scripts'/folder/old
    (source.parent/new).write_text(pattern.sub(lambda m: changes[m[0]], source.read_text(encoding='utf-8')), encoding='utf-8')
print('Prepared Android 0.5.18 / 518; Windows stays 0.3.20')
