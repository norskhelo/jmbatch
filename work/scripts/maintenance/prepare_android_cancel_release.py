"""Prepare the authorized Android 0.5.3 cancellation fix and release documentation."""
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android'
JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.5.3 — 2026-10-17

## 下载取消响应优化

- 修复图片下载时取消或暂停容易卡住界面的问题：先停止派发后续页面，再在后台并行关闭当前网络连接，避免一个慢连接拖住取消按钮和其他连接。
- 同一网络请求只关闭一次，重复点击取消不会重复清理连接；取消时立即显示停止状态并归零速度。
- 图片压缩结束后及刷盘后及时检查取消，减少无用的后续处理；正常下载仍保留刷盘、图片尺寸和成品完整性校验。
- 完整图片缓存保留，重试只补缺失或损坏页面；等待旧工作线程真正退出后才允许重试，避免同时写入缓存。取消单个任务不影响其他任务。
- 个别设备的网络请求或当前图片处理仍可能等待系统操作结束或超时，不承诺所有情况下瞬间取消。

## 版本与验证

- Android 0.5.2 → 0.5.3，versionCode 503；Windows 保持 0.3.9。沿用原包名、APK 签名证书与更新公钥，支持覆盖安装并保留设置、队列和收藏。
- 7000 页、16 路受阻请求的取消场景通过，覆盖响应头/响应体等待、重复取消、后续页面停止、临时文件清理、完整缓存及任务互斥；完成 928 项 Android 宿主检查、编译和原证书签名验证。
- 尚未连接 Android 真机；模拟测试验证取消调度，不代表手机上的实际耗时。未下载真实漫画图片或修改用户缓存。
- 发布新版 APK、同版日志、SHA-256 校验文件、更新清单与原密钥签名，并同步源码和应用内公告。
'''
notes=ROOT/'work/release-android-053/release-notes.md'
notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')

def replace(path,old,new):
    text=path.read_text(encoding='utf-8');assert old in text,path
    path.write_text(text.replace(old,new),encoding='utf-8')

replace(JAVA/'Core.java','VERSION = "0.5.2"','VERSION = "0.5.3"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="502"','versionCode="503"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.5.2"','versionName="0.5.3"')
replace(ANDROID/'app/build.gradle','versionCode 502','versionCode 503')
replace(ANDROID/'app/build.gradle',"versionName '0.5.2'","versionName '0.5.3'")
plain=re.sub(r'^#{1,2} ', '', NOTES, flags=re.M).replace('- ','• ')
path=JAVA/'GithubUpdates.java';text=path.read_text(encoding='utf-8')
text,count=re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',text)
assert count==1;path.write_text(text,encoding='utf-8')
path=ROOT/'CHANGELOG.md';text=path.read_text(encoding='utf-8')
assert text.startswith('# 未发布 — Android 下载取消优化')
path.write_text(NOTES+'\n'+text[text.index('# Android 0.5.2 —'):],encoding='utf-8')
path=ANDROID/'README.txt';text=path.read_text(encoding='utf-8').split('Android 0.5.2 — 2026-10-17')[0]
path.write_text(text.replace('0.5.2','0.5.3')+plain,encoding='utf-8')
path=ROOT/'README.md';text=path.read_text(encoding='utf-8')
text=text.replace('Android 0.5.2（versionCode 502）','Android 0.5.3（versionCode 503）')
text=text.replace('Android 0.5.2 移除云空间入口，按原生文件应用能力打开保存目录，不支持定位时显示保存位置。','Android 0.5.3 优化下载取消与暂停响应，后台并行关闭当前连接，保留完整图片及断点续传。')
text=text.replace('Android 0.5.2**','Android 0.5.3**').replace('| Android 0.5.2','| Android 0.5.3')
text=text.replace('release-android-0.5.2','release-android-0.5.3').replace('JMBatch-0.5.2-Android.apk','JMBatch-0.5.3-Android.apk')
text=text.replace('SHA256-release-android-0.5.2.txt','SHA256-release-android-0.5.3.txt')
text+='\nAndroid 0.5.3：取消和暂停改为后台并行关闭当前连接，避免慢连接拖住界面；重复取消不重复关闭。保留完整图片和断点续传，等待旧线程退出再允许重试。7000 页模拟取消与 928 项宿主检查通过，实际手机耗时尚待真机确认。\n'
path.write_text(text,encoding='utf-8')
for old,new in [('prepare_publication_android_052.py','prepare_publication_android_053.py'),('publish_android_052.py','publish_android_053.py')]:
    path=ROOT/'work/scripts/release'/old
    text=path.read_text(encoding='utf-8').replace('0.5.2','0.5.3').replace('android-052','android-053')
    text=text.replace('移除云空间入口与原生目录跳转','下载取消与暂停响应优化')
    (path.parent/new).write_text(text,encoding='utf-8')
# Adapt the production online updater check without changing historical recipes.
path=ROOT/'work/scripts/maintenance/verify_android_native_files_online.py'
text=path.read_text(encoding='utf-8').replace('0.5.2','0.5.3').replace('0.5.1','0.5.2')
text=text.replace('native-052','cancel-053').replace('android-052','android-053')
text=text.replace('LiveNativeFilesUpdate','LiveCancelUpdate').replace('原生文件管理与保存目录跳转','下载取消响应优化')
text=text.replace('!=12','!=13').replace('12-release','13-release').replace('full_history_versions=12','full_history_versions=13')
(path.parent/'verify_android_cancel_online.py').write_text(text,encoding='utf-8')
path=ROOT/'work/scripts/release/verify_native_files_commit.py'
text=path.read_text(encoding='utf-8').replace('0.5.2','0.5.3').replace('native-052','cancel-053')
(path.parent/'verify_cancel_commit.py').write_text(text,encoding='utf-8')
print('Prepared Android 0.5.3 / 503; Windows stays 0.3.9')
