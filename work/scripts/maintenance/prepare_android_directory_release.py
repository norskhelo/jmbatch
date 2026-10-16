"""Prepare Android 0.5.1 native file-manager behavior and matching release notes."""
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android'
JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.5.1 — 2026-10-17

## 默认使用系统文件管理器

- “打开保存目录”改用安卓原生 Intent，默认优先启动手机自带的文件管理应用；不再自动优先打开左侧菜单显示“JM Batch”的文档管理界面。
- 支持目录查看的系统文件管理器会收到保存目录地址；仅提供应用入口时，直接打开文件管理器主界面，并提示手动定位。返回 JM Batch 后可查看、复制保存位置或选择备用打开方式。
- 使用 Android 原生文件应用类别发现组件，并兼容旧款华为／荣耀文件管理器入口；仅自动启动可用的系统组件。组件受限或启动失败时继续尝试其他入口。
- 文档管理改为手动备用选项，保留选择其他应用和软件内查看。首页、任务详情、漫画库和软件内子目录的系统打开入口使用同一逻辑。
- 不移动已有文件，不更改保存目录或目录授权。部分文件管理器不能浏览应用目录，或会忽略指定位置；此时可用备用入口，或在首页为以后下载选择可见的公共文件夹。

## 版本与验证

- Android 0.5.0 → 0.5.1，versionCode 501；Windows 保持 0.3.9。保留原包名、APK 签名证书与更新公钥，支持覆盖安装。
- 回归默认文件管理器选择、文档管理仅手动回退、原生 Intent 参数、启动失败备用入口、禁用/非导出组件及第三方组件过滤；执行 Android 宿主回归、编译与签名核验。
- 用户设备为荣耀 Play5 / Android 10。未连接该手机；宿主模拟检查不能证明厂商界面实际跳转，未承诺所有系统都能直达保存目录。
- 同步源码、应用内说明、同版更新日志、APK、SHA-256 校验文件及原密钥签名更新清单，正式发布 Android 0.5.1。
'''
notes=ROOT/'work/release-android-051/release-notes.md';notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')
def replace(path,old,new):
    text=path.read_text(encoding='utf-8');assert old in text,path;path.write_text(text.replace(old,new),encoding='utf-8')
replace(JAVA/'Core.java','VERSION = "0.5.0"','VERSION = "0.5.1"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="500"','versionCode="501"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.5.0"','versionName="0.5.1"')
replace(ANDROID/'app/build.gradle','versionCode 500','versionCode 501')
replace(ANDROID/'app/build.gradle',"versionName '0.5.0'","versionName '0.5.1'")
plain=re.sub(r'^#{1,2} ', '', NOTES, flags=re.M).replace('- ','• ')
path=JAVA/'GithubUpdates.java';text=path.read_text(encoding='utf-8')
text=re.sub(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',text)
path.write_text(text,encoding='utf-8')
path=ROOT/'CHANGELOG.md';path.write_text(NOTES+'\n'+path.read_text(encoding='utf-8'),encoding='utf-8')
path=ANDROID/'README.txt';text=path.read_text(encoding='utf-8').split('Android 0.5.0 — 2026-10-16')[0]
path.write_text(text.replace('0.5.0','0.5.1').replace('2026-10-16','2026-10-17')+plain,encoding='utf-8')
path=ROOT/'README.md';text=path.read_text(encoding='utf-8')
text=text.replace('Android 0.5.0（versionCode 500）','Android 0.5.1（versionCode 501）')
text=text.replace('Android 0.5.0 优化图片处理并行、CDN 线路选择及临时图片刷盘，保留完整性校验和断点续传。','Android 0.5.1 将“打开保存目录”默认改为原生系统文件管理器，文档管理保留为手动备用入口。')
text=text.replace('Android 0.5.0**','Android 0.5.1**')
text=text.replace('release-android-0.5.0','release-android-0.5.1').replace('JMBatch-0.5.0-Android.apk','JMBatch-0.5.1-Android.apk')
text=text.replace('| Android 0.5.0','| Android 0.5.1')
text+='\nAndroid 0.5.1：默认调用原生系统文件管理应用，支持目录跳转时传入保存地址；仅有应用入口时打开主界面并提示手动定位，返回后可复制保存位置。文档管理保留为备用。未改变保存目录、移动已有文件或新增存储权限；荣耀 Play5 / Android 10 尚待真机确认。\n'
path.write_text(text,encoding='utf-8')
# New recipes only; do not rerun or mutate historical release recipes.
for old,new in [('prepare_publication_android_050.py','prepare_publication_android_051.py'),('publish_android_050.py','publish_android_051.py')]:
    path=ROOT/'work/scripts/release'/old;text=path.read_text(encoding='utf-8').replace('0.5.0','0.5.1').replace('android-050','android-051')
    text=text.replace('图片并行、CDN 选择与下载提速','默认打开原生系统文件管理器')
    (path.parent/new).write_text(text,encoding='utf-8')
print('Prepared Android 0.5.1 / 501; Windows stays 0.3.9')
