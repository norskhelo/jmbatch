"""Prepare Android 0.5.2 native file-manager behavior and matching release notes."""
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android'
JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.5.2 — 2026-10-17

## 原生文件管理与保存目录跳转

- 修复荣耀 Play5 / Android 10 上“打开保存目录”误入云空间的问题：删除旧华为／荣耀包名兼容入口，并在自动打开、文档管理备用和其他应用选择中排除已确认的华为云空间包。
- 改用 Android 原生文件应用选择机制，启动系统实际声明的文件管理活动，不再打开猜测包名对应的应用首页。原生“文件”与文件选择器分别判断，保留可用系统默认项及启动失败回退。
- 文件管理器明确支持目录查看时，以目录地址请求直接打开保存目录；同时支持默认保存目录、自选目录及软件内当前子目录。默认目录使用只读文档目录树地址，供接收方读取子目录和图片。
- 不支持目录跳转时打开原生文件应用首页，并显示可复制的保存位置；不会把打开首页显示为已定位。仍可手动使用文档管理或软件内查看。
- 不移动文件、不更改保存设置、不新增存储权限。目录跳转取决于手机文件应用支持；系统应用可能忽略地址，原生界面也由设备决定。

## 版本与验证

- Android 0.5.1 → 0.5.2，versionCode 502；Windows 保持 0.3.9。保留原包名、APK 签名证书与更新公钥，支持覆盖安装。
- 检查云空间过滤、真实原生组件选择、目录地址与只读授权、首页回退、禁用或受限组件及备用选择；执行 Android 宿主回归、编译与签名核验。
- 未连接荣耀 Play5 / Android 10 真机；模拟框架检查验证调用参数和选择策略，不代表已验证手机实际界面和目录定位。
- 同步源码、应用内说明、同版更新日志、APK、SHA-256 校验文件及原密钥签名更新清单，正式发布 Android 0.5.2。
'''
notes=ROOT/'work/release-android-052/release-notes.md';notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')
def replace(path,old,new):
    text=path.read_text(encoding='utf-8');assert old in text,path;path.write_text(text.replace(old,new),encoding='utf-8')
replace(JAVA/'Core.java','VERSION = "0.5.1"','VERSION = "0.5.2"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="501"','versionCode="502"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.5.1"','versionName="0.5.2"')
replace(ANDROID/'app/build.gradle','versionCode 501','versionCode 502')
replace(ANDROID/'app/build.gradle',"versionName '0.5.1'","versionName '0.5.2'")
plain=re.sub(r'^#{1,2} ', '', NOTES, flags=re.M).replace('- ','• ')
path=JAVA/'GithubUpdates.java';text=path.read_text(encoding='utf-8')
text=re.sub(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',text)
path.write_text(text,encoding='utf-8')
path=ROOT/'CHANGELOG.md';path.write_text(NOTES+'\n'+path.read_text(encoding='utf-8'),encoding='utf-8')
path=ANDROID/'README.txt';text=path.read_text(encoding='utf-8').split('Android 0.5.1 — 2026-10-17')[0]
path.write_text(text.replace('0.5.1','0.5.2').replace('2026-10-16','2026-10-17')+plain,encoding='utf-8')
path=ROOT/'README.md';text=path.read_text(encoding='utf-8')
text=text.replace('Android 0.5.1（versionCode 501）','Android 0.5.2（versionCode 502）')
text=text.replace('Android 0.5.1 将“打开保存目录”默认改为原生系统文件管理器，文档管理保留为手动备用入口。','Android 0.5.2 移除云空间入口，按原生文件应用能力打开保存目录，不支持定位时显示保存位置。')
text=text.replace('Android 0.5.1**','Android 0.5.2**')
text=text.replace('release-android-0.5.1','release-android-0.5.2').replace('JMBatch-0.5.1-Android.apk','JMBatch-0.5.2-Android.apk')
text=text.replace('| Android 0.5.1','| Android 0.5.2')
text+='\nAndroid 0.5.2：移除上一版误用的华为云空间入口，改用原生文件应用选择机制；支持目录查看时传入保存目录及只读授权，仅支持首页时显示保存位置。默认目录及子目录使用可浏览的文档目录树。未连接荣耀 Play5 / Android 10，实际定位取决于设备支持。\n'
path.write_text(text,encoding='utf-8')
# New recipes only; do not rerun or mutate historical release recipes.
for old,new in [('prepare_publication_android_051.py','prepare_publication_android_052.py'),('publish_android_051.py','publish_android_052.py')]:
    path=ROOT/'work/scripts/release'/old;text=path.read_text(encoding='utf-8').replace('0.5.1','0.5.2').replace('android-051','android-052')
    text=text.replace('默认打开原生系统文件管理器','移除云空间入口与原生目录跳转')
    (path.parent/new).write_text(text,encoding='utf-8')
print('Prepared Android 0.5.2 / 502; Windows stays 0.3.9')
