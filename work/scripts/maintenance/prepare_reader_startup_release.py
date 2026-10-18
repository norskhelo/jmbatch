"""Prepare the authorized Android reader startup release and reviewed publication recipes."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android'
JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.5.20 — 图片文件夹阅读提速

## 更新内容

- 图片文件夹阅读复用已有页面索引，优先打开上次阅读页，不再等待整本逐页文件检查完成后才显示漫画。
- 优先检查当前页及后续 4 页，跨章节同样有效；滚动和左右翻页按内存预算预加载后续图片，优先保障连续阅读。
- 其余页面在后台分批检查，当前阅读、翻页和跳章请求优先；显示索引建立、页面加载和后台检查进度。
- 缺失或损坏的索引尝试从可识别的图片目录重建并保存；保留旧版目录布局支持。缺图和大小变化按页提示，不阻止阅读其他正常页面，再次跳转可重试。
- 保留章节、书签、阅读位置、沉浸阅读和漫画库状态；图片缓存保持 32 MiB 上限，关闭阅读器停止后续检查。导出和删除继续使用完整校验。

## 版本与验证

- Android 0.5.19 → 0.5.20，versionCode 520；Windows 保持 0.3.21。沿用原包名、APK 签名证书和更新公钥，可覆盖安装。
- Android 10 框架回归覆盖 5000 页索引、外部目录按章读取、后续页面优先、滚动/翻页恢复、缺图重试、索引恢复与取消，并保留漫画库触摸模式回归；执行完整宿主回归、编译与原证书签名核验。
- 测试使用合成文件及 Android 框架环境；未取得手机实测耗时，不承诺具体提速倍数。无索引的旧漫画首次打开仍需建立索引；外部存储单次目录查询的等待时间取决于存储服务。
'''

def change(path,old,new):
    text=path.read_text(encoding='utf-8');assert old in text,path
    path.write_text(text.replace(old,new),encoding='utf-8')

notes=ROOT/'work/release-android-0520/release-notes.md';notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')
change(JAVA/'Core.java','VERSION = "0.5.19"','VERSION = "0.5.20"')
change(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="519"','versionCode="520"')
change(ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.5.19"','versionName="0.5.20"')
change(ANDROID/'app/build.gradle','versionCode 519','versionCode 520')
change(ANDROID/'app/build.gradle',"versionName '0.5.19'","versionName '0.5.20'")
plain=re.sub(r'^#{1,2} ','',NOTES,flags=re.M).replace('- ','• ')
path=JAVA/'GithubUpdates.java'
text,count=re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',path.read_text(encoding='utf-8'));assert count==1
path.write_text(text,encoding='utf-8')
path=ROOT/'CHANGELOG.md';path.write_text(NOTES+'\n'+path.read_text(encoding='utf-8'),encoding='utf-8')
path=ANDROID/'README.txt';text=path.read_text(encoding='utf-8').split('Windows 0.3.21 / Android 0.5.19 —')[0].rstrip()
text=text.replace('SHA256-release-0.3.21-0.5.19.txt','SHA256-release-android-0.5.20.txt').replace('release-0.3.21-0.5.19','release-android-0.5.20').replace('0.5.19','0.5.20')
path.write_text(text+'\n\n'+plain,encoding='utf-8')
path=ROOT/'README.md';lines=path.read_text(encoding='utf-8').splitlines();result=[]
for line in lines:
    if line.startswith('当前源码及正式版本：'):
        line='当前源码及正式版本：**Windows 0.3.21 / Android 0.5.20（versionCode 520）**。Android 图片文件夹复用索引，优先打开上次阅读页及后续页面，其余页面后台检查并显示进度。安装包、更新日志与镜像入口见下方。'
    elif line.startswith('当前正式版为 '):
        line='当前正式版为 **Windows 0.3.21 / Android 0.5.20**（[Windows 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.21-0.5.19)、[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.5.20)）。完整附件及后续更新见 [Releases 页面](https://github.com/norskhelo/jmbatch/releases)。'
    elif line.startswith('| Android '):
        line=line.replace('SHA256-release-0.3.21-0.5.19.txt','SHA256-release-android-0.5.20.txt').replace('release-0.3.21-0.5.19','release-android-0.5.20').replace('0.5.19','0.5.20')
    result.append(line)
text='\n'.join(result)+'\n'
text=text.replace('## 内置阅读器\n','## 内置阅读器\n\nAndroid 图片文件夹复用页面索引，先打开上次阅读页，优先检查后续 4 页并按内存预算预加载；其余页面后台分批检查，显示加载及检查进度。当前阅读请求优先，异常按页提示并允许再次跳转重试。缺失索引的旧目录首次打开需先建立索引。\n')
path.write_text(text,encoding='utf-8')
mapping={'0.5.18':'0.5.20','0.5.17':'0.5.19','0.3.20':'0.3.21','0.3.19':'0.3.20','0518':'0520','518':'520','517':'519',
    'library-crash':'reader-startup','漫画库闪退修复':'图片文件夹阅读提速','LiveLibraryCrashUpdate':'LiveReaderStartupUpdate',
    '!=28':'!=30','28-release':'30-release','full_history_versions=28':'full_history_versions=30'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(mapping,key=len,reverse=True)))
for folder,old,new in (
    ('release','prepare_publication_android_0518.py','prepare_publication_android_0520.py'),
    ('release','publish_android_0518.py','publish_android_0520.py'),
    ('release','verify_crash_commit.py','verify_reader_startup_commit.py'),
    ('maintenance','verify_android_crash_online.py','verify_reader_startup_online.py')):
    path=ROOT/'work/scripts'/folder/old
    (path.parent/new).write_text(pattern.sub(lambda m:mapping[m[0]],path.read_text(encoding='utf-8')),encoding='utf-8')
print('Prepared Android 0.5.20 / 520; Windows remains 0.3.21')
