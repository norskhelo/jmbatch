"""Prepare the authorized Android-only font layout release, preserving historical recipes."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android'
JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.5.8 — 字体与按钮尺寸适配

## 界面修复

- 更换系统字体或放大字号时，应用自建按钮按文字实际高度伸缩，保留字体上下留白和至少 48dp 的点击高度，完整显示标签。
- 首页、阅读器、漫画库和目录浏览的操作按钮按实际文字宽度自动调整每行数量，同排按钮保持等高；文字变化、按钮隐藏或屏幕宽度变化后重新排列。
- 阅读器和漫画库在大字号或横屏空间不足时，操作区支持滚动，给漫画和列表保留可见区域。
- 导出和更新页面使用相同的按钮尺寸规则；保留用户的系统字体和字号缩放。Android 原生对话框按钮继续由系统管理。

## 版本与验证

- Android 0.5.7 → 0.5.8，versionCode 508；Windows 保持 0.3.13。沿用原包名、APK 签名证书和更新公钥，可覆盖安装并保留设置、队列和收藏。
- 完成 1086 项既有 Android 宿主检查、96 组合成字体尺寸/字号/屏宽场景（11962 项断言）、完整编译及原证书签名核验。
- 在“设置 → 运行离线自检”加入 64 组 Android 原生文字测量检查。当前未连接安卓设备，新增原生检查未执行，宿主测试和编译不代表真机字体或视觉效果已验收。
- 发布新版 APK、同版日志、SHA-256 校验文件、更新清单及原密钥签名，同步源码与应用内公告。
'''

def replace(path,old,new):
    text=path.read_text(encoding='utf-8')
    assert old in text,path
    path.write_text(text.replace(old,new),encoding='utf-8')

notes=ROOT/'work/release-android-058/release-notes.md'
notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')
replace(JAVA/'Core.java','VERSION = "0.5.7"','VERSION = "0.5.8"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="507"','versionCode="508"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.5.7"','versionName="0.5.8"')
replace(ANDROID/'app/build.gradle','versionCode 507','versionCode 508')
replace(ANDROID/'app/build.gradle',"versionName '0.5.7'","versionName '0.5.8'")
plain=re.sub(r'^#{1,2} ', '', NOTES, flags=re.M).replace('- ','• ')
path=JAVA/'GithubUpdates.java';text=path.read_text(encoding='utf-8')
text,count=re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',text)
assert count==1;path.write_text(text,encoding='utf-8')
path=ROOT/'CHANGELOG.md';text=path.read_text(encoding='utf-8')
assert text.startswith('# 未发布 — Android 字体与按钮布局修复')
path.write_text(NOTES+'\n'+text[text.index('# Windows 0.3.13 / Android 0.5.7 —'):],encoding='utf-8')
path=ANDROID/'README.txt';text=path.read_text(encoding='utf-8').split('Windows 0.3.13 / Android 0.5.7 —')[0]
text=text.replace('JM Batch 0.5.7','JM Batch 0.5.8').replace('release-0.3.13-0.5.7','release-android-0.5.8')
text=text.replace('JMBatch-0.5.7-Android.apk','JMBatch-0.5.8-Android.apk').replace('SHA256-release-0.3.13-0.5.7.txt','SHA256-release-android-0.5.8.txt')
path.write_text(text+plain,encoding='utf-8')
path=ROOT/'README.md';lines=path.read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines):
    if line.startswith('当前源码及正式版本：'):
        lines[i]='当前源码及正式版本：**Windows 0.3.13 / Android 0.5.8（versionCode 508）**。Android 本版修复更换系统字体、放大字号时的按钮尺寸与布局异常；Windows 保持 0.3.13。安装包、更新日志与镜像入口见下方。'
    elif line.startswith('当前正式版为 '):
        lines[i]=line.replace('Android 0.5.7','Android 0.5.8').replace('[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.13-0.5.7)','[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.5.8)')
    elif line.startswith('| Android '):
        lines[i]=line.replace('Android 0.5.7','Android 0.5.8').replace('release-0.3.13-0.5.7','release-android-0.5.8').replace('JMBatch-0.5.7-Android.apk','JMBatch-0.5.8-Android.apk').replace('SHA256-release-0.3.13-0.5.7.txt','SHA256-release-android-0.5.8.txt')
lines+=['','Android 0.5.8：按钮按实际字体尺寸调整高度和每行数量，同排等高；大字号或横屏下阅读器/漫画库操作区可以滚动，并保留内容区域。保持系统字体与字号缩放。1086 项既有宿主检查、96 组合成布局场景和原签名构建通过，尚未进行真机字体视觉验收。']
path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
for name in ('prepare_publication_android_053.py','publish_android_053.py'):
    path=ROOT/'work/scripts/release'/name
    text=path.read_text(encoding='utf-8').replace('0.5.3','0.5.8').replace('0.3.9','0.3.13').replace('android-053','android-058').replace('<= 503','<= 508')
    text=text.replace('下载取消与暂停响应优化','字体与按钮尺寸适配')
    (path.parent/name.replace('053','058')).write_text(text,encoding='utf-8')
path=ROOT/'work/scripts/maintenance/verify_android_update_mirrors_online.py'
text=path.read_text(encoding='utf-8').replace('release-0.3.13-0.5.7','release-android-0.5.8').replace('0.5.7','0.5.8').replace('0.5.6','0.5.7')
text=text.replace('release-0313-057','release-android-058').replace('update-mirrors-057','font-058').replace('LiveCancelUpdate','LiveFontUpdate').replace('应用内更新下载自动切换镜像','字体与按钮尺寸适配')
text=text.replace('!=17','!=18').replace('17-release','18-release').replace('full_history_versions=17','full_history_versions=18')
(path.parent/'verify_android_font_online.py').write_text(text,encoding='utf-8')
path=ROOT/'work/scripts/release/verify_cancel_commit.py'
text=path.read_text(encoding='utf-8').replace('0.5.3','0.5.8').replace('cancel-053','font-058')
(path.parent/'verify_font_commit.py').write_text(text,encoding='utf-8')
print('Prepared Android 0.5.8 / 508; Windows stays 0.3.13')
