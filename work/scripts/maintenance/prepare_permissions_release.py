"""Prepare the authorized Android 0.6.0 permissions release, preserving Windows 0.3.22."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android';JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.6.0 — 权限检测与申请

## 更新内容

- 首页及失败任务详情加入“权限与联网检测”。查看联网、通知、保存目录、后台下载和安装更新权限；从系统设置返回后自动刷新。
- Android 13 及以上支持直接申请通知权限；首次开始下载最多提示一次，拒绝后不反复弹窗、不阻止下载，可在权限页主动申请或打开通知设置。识别“下载进度”通知类别被单独关闭的情况。
- 检查保存目录持久读写授权，支持重新选择授权；从失败任务进入时只重新授权该任务的原目录，防止误改保存位置。应用目录无需额外存储权限，不申请全部文件访问。
- 提供应用联网、通知、省电、后台流量及安装更新设置入口。Android 的联网权限由系统在安装时授予，不能重新弹窗申请；厂商额外联网限制无法可靠读取，页面会明确说明并引导核对，不虚报为已放行。
- 内置以 JM Batch 自身身份运行的联网诊断：检查 DNS、小米官网对照与四条漫画线路 HTTPS，可手动选择 IPv4/IPv6 直连对比。保留 TLS 证书及域名校验，不读取漫画、Cookie 或账号，不自动上传报告；支持复制、分享、保存和停止检测。
- 修正连接异常里手机本地 `from /::` 被误认为服务器地址异常的问题，区分联网权限拒绝、连接拒绝、路由不可达与超时；保持 HTTP 4xx 停止及敏感信息过滤。

## 版本与验证

- Android 0.5.22 → 0.6.0，versionCode 600；Windows 保持 0.3.22。保留原包名、APK 签名证书和更新公钥，可覆盖安装。
- 执行网络原因/诊断引擎宿主回归、Android 10 与 Android 15 框架权限流程、目录授权及页面入口测试，以及既有全量回归、布局检查、完整构建与签名核验。
- 手机暂不可获取，尚未进行 Redmi K70 Pro 真机验收。网络诊断结果用于定位具体原因，不能保证所有网络环境可达；省电和安装更新设置为可选项，不强制授予。
'''
def change(path,old,new):
    text=path.read_text(encoding='utf-8');assert old in text,path;path.write_text(text.replace(old,new),encoding='utf-8')
notes=ROOT/'work/release-android-060/release-notes.md';notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')
change(JAVA/'Core.java','VERSION = "0.5.22"','VERSION = "0.6.0"')
for path,old,new in [(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="522"','versionCode="600"'),(ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.5.22"','versionName="0.6.0"'),(ANDROID/'app/build.gradle','versionCode 522','versionCode 600'),(ANDROID/'app/build.gradle',"versionName '0.5.22'","versionName '0.6.0'")]:change(path,old,new)
plain=re.sub(r'^#{1,2} ','',NOTES,flags=re.M).replace('- ','• ')
p=JAVA/'GithubUpdates.java';text,count=re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',p.read_text(encoding='utf-8'));assert count==1;p.write_text(text,encoding='utf-8')
p=ROOT/'CHANGELOG.md';previous=p.read_text(encoding='utf-8');previous=previous[previous.index('# Android 0.5.22'):];p.write_text(NOTES+'\n'+previous,encoding='utf-8')
p=ANDROID/'README.txt';text=p.read_text(encoding='utf-8').split('Android 0.5.22 —')[0].rstrip().replace('0.5.22','0.6.0');p.write_text(text+'\n\n'+plain,encoding='utf-8')
p=ROOT/'README.md';lines=[]
for line in p.read_text(encoding='utf-8').splitlines():
    if line.startswith('当前源码及正式版本：'):line='当前源码及正式版本：**Windows 0.3.22 / Android 0.6.0（versionCode 600）**。Android 内置权限检测与申请、目录重新授权和本应用联网诊断，可直接打开对应系统设置并导出报告。安装包、更新日志与镜像入口见下方。'
    elif line.startswith('当前正式版为 '):line=line.replace('0.5.22','0.6.0')
    elif line.startswith('| Android '):line=line.replace('0.5.22','0.6.0')
    lines.append(line)
p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
mapping={'0.5.22':'0.6.0','0.5.21':'0.5.22','0522':'060','522':'600','521':'522','chapter-speed':'permissions','大漫画章节删除提速':'权限检测与申请','LiveChapterSpeedUpdate':'LivePermissionsUpdate','!=32':'!=33','32-release':'33-release','full_history_versions=32':'full_history_versions=33'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(mapping,key=len,reverse=True)))
for folder,old,new in [('release','prepare_publication_android_0522.py','prepare_publication_android_060.py'),('release','publish_android_0522.py','publish_android_060.py'),('release','verify_chapter_speed_commit.py','verify_permissions_commit.py'),('maintenance','verify_chapter_speed_online.py','verify_permissions_online.py')]:
    p=ROOT/'work/scripts'/folder/old;(p.parent/new).write_text(pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
print('Prepared Android 0.6.0 / 600; Windows unchanged')
