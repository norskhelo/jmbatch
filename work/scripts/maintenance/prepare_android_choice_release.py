"""Prepare the authorized Android batch-checkbox animation release."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ANDROID = ROOT/'work/jmbatch-android'
JAVA = ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES = '''# Android 0.5.16 — 批量选择显示修复

## 修复内容

- 修复漫画库开启批量处理后，滑动列表、停止滑动或封面加载完成时，勾选框反复播放勾选动画的问题。
- 列表复用勾选图标，刷新时直接显示当前选择状态，避免已选数量不变但勾选框反复闪动。
- 保留点击勾选和取消、长按选择、全选/反选、筛选及阅读返回后的选择恢复。

## 版本与验证

- Android 0.5.15 → 0.5.16，versionCode 516；Windows 保持 0.3.19。沿用原包名、APK 签名证书和更新公钥，可覆盖安装。
- 新增 22 项列表绑定回归，覆盖反复复用、封面完成刷新、批量模式切换及选择状态；包含原有 46 项漫画库交互检查，并执行完整 Android 宿主回归、编译和原证书签名校验。
- 当前没有连接 Android 真机；宿主动画状态检查不能替代手机实际渲染，显示效果仍需设备验收。
'''

def replace(path, old, new):
    text = path.read_text(encoding='utf-8')
    assert old in text, path
    path.write_text(text.replace(old, new), encoding='utf-8')

notes = ROOT/'work/release-android-0516/release-notes.md'
notes.parent.mkdir(parents=True, exist_ok=True)
notes.write_text(NOTES, encoding='utf-8')
replace(JAVA/'Core.java', 'VERSION = "0.5.15"', 'VERSION = "0.5.16"')
replace(ANDROID/'app/src/main/AndroidManifest.xml', 'versionCode="515"', 'versionCode="516"')
replace(ANDROID/'app/src/main/AndroidManifest.xml', 'versionName="0.5.15"', 'versionName="0.5.16"')
replace(ANDROID/'app/build.gradle', 'versionCode 515', 'versionCode 516')
replace(ANDROID/'app/build.gradle', "versionName '0.5.15'", "versionName '0.5.16'")
plain = re.sub(r'^#{1,2} ', '', NOTES, flags=re.M).replace('- ', '• ')
path = JAVA/'GithubUpdates.java'
text, count = re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',
    lambda m: 'private static final String CURRENT_NOTES='+json.dumps(plain, ensure_ascii=False)+';', path.read_text(encoding='utf-8'))
assert count == 1
path.write_text(text, encoding='utf-8')
path = ROOT/'CHANGELOG.md'; text = path.read_text(encoding='utf-8')
assert text.startswith('# 未发布 — Android 批量选择显示修复')
text = text[text.index('# Windows 0.3.19 / Android 0.5.15'):]
path.write_text(NOTES+'\n'+text, encoding='utf-8')
path = ANDROID/'README.txt'
text = path.read_text(encoding='utf-8').split('Windows 0.3.19 / Android 0.5.15 —')[0].rstrip()
text = text.replace('JM Batch 0.5.15', 'JM Batch 0.5.16')
text = text.replace('SHA256-release-0.3.19-0.5.15.txt', 'SHA256-release-android-0.5.16.txt')
text = text.replace('release-0.3.19-0.5.15', 'release-android-0.5.16').replace('JMBatch-0.5.15-Android.apk', 'JMBatch-0.5.16-Android.apk')
path.write_text(text+'\n\n'+plain, encoding='utf-8')
path = ROOT/'README.md'; lines = path.read_text(encoding='utf-8').splitlines(); result = []
for line in lines:
    if line.startswith('当前源码及正式版本：'):
        line = '当前源码及正式版本：**Windows 0.3.19 / Android 0.5.16（versionCode 516）**。Android 修复漫画库批量选择时滑动或封面刷新导致的勾选动画闪动。安装包、更新日志与镜像入口见下方。'
    elif line.startswith('当前正式版为 '):
        line = '当前正式版为 **Windows 0.3.19 / Android 0.5.16**（[Windows 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.19-0.5.15)、[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.5.16)）。完整附件及后续更新见 [Releases 页面](https://github.com/norskhelo/jmbatch/releases)。'
    elif line.startswith('| Android '):
        line = line.replace('Android 0.5.15', 'Android 0.5.16').replace('release-0.3.19-0.5.15', 'release-android-0.5.16').replace('JMBatch-0.5.15-Android.apk', 'JMBatch-0.5.16-Android.apk')
    elif line.startswith('| 双端 SHA-256 '):
        result.append(line.replace('双端 SHA-256', 'Windows 0.3.19 SHA-256'))
        line = line.replace('双端 SHA-256', 'Android 0.5.16 SHA-256').replace('SHA256-release-0.3.19-0.5.15.txt', 'SHA256-release-android-0.5.16.txt').replace('release-0.3.19-0.5.15', 'release-android-0.5.16')
    result.append(line)
path.write_text('\n'.join(result)+'\n', encoding='utf-8')

# Retain historical release recipes; generate reviewed files for this release.
changes = {'0.5.11':'0.5.16', '0.3.15':'0.3.19', 'android-0511':'android-0516',
           '<= 511':'<= 516', '返回前台时保持键盘收起':'批量选择显示修复'}
for name in ('prepare_publication_android_0511.py', 'publish_android_0511.py'):
    path = ROOT/'work/scripts/release'/name
    text = path.read_text(encoding='utf-8')
    for old, new in changes.items(): text = text.replace(old, new)
    (path.parent/name.replace('0511', '0516')).write_text(text, encoding='utf-8')
path = ROOT/'work/scripts/maintenance/verify_android_ime_online.py'
text = path.read_text(encoding='utf-8')
for old, new in {**changes, '0.5.10':'0.5.15', '0.3.14':'0.3.18', 'ime-0511':'choice-animation-0516',
                 'LiveImeUpdate':'LiveChoiceUpdate', '!=21':'!=26', '21-release':'26-release',
                 'full_history_versions=21':'full_history_versions=26'}.items():
    text = text.replace(old, new)
(path.parent/'verify_android_choice_online.py').write_text(text, encoding='utf-8')
path = ROOT/'work/scripts/release/verify_ime_commit.py'
text = path.read_text(encoding='utf-8').replace('0.5.11','0.5.16').replace('ime-0511','choice-animation-0516')
(path.parent/'verify_choice_commit.py').write_text(text, encoding='utf-8')
print('Prepared Android 0.5.16 / 516; Windows stays 0.3.19')
