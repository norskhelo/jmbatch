"""Prepare the authorized Android-only chapter deletion performance release."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android'
JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.5.22 — 大漫画章节删除提速

## 更新内容

- 优化图片文件夹打开“删除章节”列表：每个章节目录只读取一次，同时取得图片大小和修改时间，合并完整性及额外文件检查，不再逐页单独查询或反复扫描整本漫画。
- 确认删除后，保留图片直接复制到输出临时目录，并逐页读回校验，省去应用缓存中转和第二次整本复制，减少存储读写与临时空间需求。
- 显示章节检查、保留图片校验及页数进度、记录保存和原文件清理阶段，合并频繁界面刷新；检查和复制期间支持取消。
- 保留旧版图片目录兼容、源文件变化检查、书签/阅读位置迁移、收藏和任务地址同步、保存失败回滚。新副本及记录确认有效后才清理原漫画；至少保留一章。

## 版本与验证

- Android 0.5.21 → 0.5.22，versionCode 522；Windows 保持 0.3.22。沿用原包名、APK 签名证书和更新公钥，可覆盖安装。
- 151 章、7227 页合成外部目录在已有索引时，打开列表的存储查询从 7836 次降为 153 次；缺少索引时为 154 次。保留图片只从源读取一次、向目标写入一次，再完整读回目标校验。
- Android 10 框架回归覆盖大目录、旧布局、空时间戳、取消、源变化、读回损坏、重命名/清理失败，以及漫画库实际入口和阅读器；执行完整宿主检查、编译和原证书签名核验。
- 查询与读写次数来自合成测试，不代表手机实测提速倍数。保留页面仍需复制和读回校验，实际耗时取决于剩余图片大小及存储速度；仍需保留内容的临时可用空间。
'''

def change(path,old,new):
    text=path.read_text(encoding='utf-8');assert old in text,path
    path.write_text(text.replace(old,new),encoding='utf-8')

notes=ROOT/'work/release-android-0522/release-notes.md'
notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')
change(JAVA/'Core.java','VERSION = "0.5.21"','VERSION = "0.5.22"')
for path,old,new in [(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="521"','versionCode="522"'),
                     (ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.5.21"','versionName="0.5.22"'),
                     (ANDROID/'app/build.gradle','versionCode 521','versionCode 522'),
                     (ANDROID/'app/build.gradle',"versionName '0.5.21'","versionName '0.5.22'")]:change(path,old,new)
plain=re.sub(r'^#{1,2} ','',NOTES,flags=re.M).replace('- ','• ')
path=JAVA/'GithubUpdates.java'
text,count=re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',path.read_text(encoding='utf-8'));assert count==1
path.write_text(text,encoding='utf-8')
path=ROOT/'CHANGELOG.md';path.write_text(NOTES+'\n'+path.read_text(encoding='utf-8'),encoding='utf-8')
path=ANDROID/'README.txt';text=path.read_text(encoding='utf-8').split('Windows 0.3.22 / Android 0.5.21 —')[0].rstrip()
text=text.replace('SHA256-release-0.3.22-0.5.21.txt','SHA256-release-android-0.5.22.txt').replace('release-0.3.22-0.5.21','release-android-0.5.22').replace('0.5.21','0.5.22')
path.write_text(text+'\n\n'+plain,encoding='utf-8')
path=ROOT/'README.md';result=[]
for line in path.read_text(encoding='utf-8').splitlines():
    if line.startswith('当前源码及正式版本：'):
        line='当前源码及正式版本：**Windows 0.3.22 / Android 0.5.22（versionCode 522）**。Android 图片文件夹章节删除按目录合并检查，保留图片一次复制并读回校验，减少大漫画处理等待并显示阶段进度。安装包、更新日志与镜像入口见下方。'
    elif line.startswith('当前正式版为 '):
        line='当前正式版为 **Windows 0.3.22 / Android 0.5.22**（[Windows 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.22-0.5.21)、[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.5.22)）。完整附件及后续更新见 [Releases 页面](https://github.com/norskhelo/jmbatch/releases)。'
    elif line.startswith('| Android '):
        line=line.replace('SHA256-release-0.3.22-0.5.21.txt','SHA256-release-android-0.5.22.txt').replace('release-0.3.22-0.5.21','release-android-0.5.22').replace('0.5.21','0.5.22')
    result.append(line)
path.write_text('\n'.join(result)+'\n',encoding='utf-8')

mapping={'0.5.20':'0.5.22','0.5.19':'0.5.21','0.3.21':'0.3.22','0.3.20':'0.3.21',
         '0520':'0522','520':'522','519':'521','reader-startup':'chapter-speed',
         '图片文件夹阅读提速':'大漫画章节删除提速','LiveReaderStartupUpdate':'LiveChapterSpeedUpdate',
         '!=30':'!=32','30-release':'32-release','full_history_versions=30':'full_history_versions=32'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(mapping,key=len,reverse=True)))
for folder,old,new in [
    ('release','prepare_publication_android_0520.py','prepare_publication_android_0522.py'),
    ('release','publish_android_0520.py','publish_android_0522.py'),
    ('release','verify_reader_startup_commit.py','verify_chapter_speed_commit.py'),
    ('maintenance','verify_reader_startup_online.py','verify_chapter_speed_online.py')]:
    path=ROOT/'work/scripts'/folder/old
    (path.parent/new).write_text(pattern.sub(lambda m:mapping[m[0]],path.read_text(encoding='utf-8')),encoding='utf-8')
print('Prepared Android 0.5.22 / 522; Windows remains 0.3.22')
