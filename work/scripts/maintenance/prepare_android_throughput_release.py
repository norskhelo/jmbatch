"""Prepare Android-only 0.5.0 source version and matching user-facing notes."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[3]
ANDROID=ROOT/'work/jmbatch-android'
JAVA=ANDROID/'app/src/main/java/app/jmbatch/android'
NOTES='''# Android 0.5.0 — 2026-10-16

## 安卓下载速度优化

- 图片网络接收与还原、JPEG 压缩分开调度，预取图片数量有上限，避免所有下载线程都等同一张图片处理。
- 图片处理根据处理器数量最多并行 4 张，由所有下载任务共享位图内存预算；大图自动等待可用预算，保留原分辨率及条带还原，不通过缩图提速。
- 图片 CDN 记住近期成功线路，按实际请求的响应吞吐选择；连接失败、超时等故障暂时退避。每 8 次请求最多安排一次备用线路比较，两次比较至少间隔 15 秒，同时最多一次，直接使用该页正常请求，不重复下载测速。
- 去掉可丢弃的原始临时图片逐页强制刷盘；保留处理后图片刷盘、尺寸核验、原子提交以及最终成品完整性校验。
- 图片响应声明长度与实际接收不一致时拒绝使用并按原恢复规则处理；暂停、取消与失败会等待工作线程退出，再清理未完成临时文件，完整缓存保留，继续只下载缺失或损坏页。
- 保留原 HTTP 拒绝访问/限流处理、HTTPS 校验、请求上限和单页恢复规则。提高线程数不保证达到宽带测速上限，速度仍受图片服务器、线路、图片像素和手机性能影响。

## 版本与验证

- 仅更新 Android：0.4.9 → 0.5.0，versionCode 500；Windows 保持 0.3.9。保留原包名、APK 签名证书和更新公钥，可覆盖安装。
- 验证有界预取、并行处理、全局内存预算、失败页保留与续传、暂停清理、CDN 记忆/退避/慢线路比较、响应截断以及拒绝访问不绕过；执行全部 Android 宿主回归、编译和签名核验。
- 生产流水线的合成负载用于验证调度改善，不能解释为手机实测加速倍数。未连接 Android 真机，原生 Bitmap 并行图片还原自检已加入应用，尚待设备执行。
- 同步源码、使用说明、同版日志、APK、SHA-256 和签名更新清单，正式发布 Android 0.5.0。
'''
notes=ROOT/'work/release-android-050/release-notes.md';notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(NOTES,encoding='utf-8')
def replace(path,old,new):
    text=path.read_text(encoding='utf-8');assert old in text,path;path.write_text(text.replace(old,new),encoding='utf-8')
replace(JAVA/'Core.java','VERSION = "0.4.9"','VERSION = "0.5.0"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionCode="409"','versionCode="500"')
replace(ANDROID/'app/src/main/AndroidManifest.xml','versionName="0.4.9"','versionName="0.5.0"')
replace(ANDROID/'app/build.gradle','versionCode 409','versionCode 500')
replace(ANDROID/'app/build.gradle',"versionName '0.4.9'","versionName '0.5.0'")
path=JAVA/'GithubUpdates.java';text=path.read_text(encoding='utf-8')
plain=re.sub(r'^#{1,2} ', '', NOTES, flags=re.M).replace('- ','• ')
text=re.sub(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',text)
path.write_text(text,encoding='utf-8')
path=ROOT/'CHANGELOG.md';path.write_text(NOTES+'\n'+path.read_text(encoding='utf-8'),encoding='utf-8')
path=ANDROID/'README.txt';text=path.read_text(encoding='utf-8').split('Windows 0.3.9 / Android 0.4.9 — 2026-10-16')[0]
text=text.replace('0.4.9','0.5.0').replace('release-0.3.9-0.5.0','release-android-0.5.0')
text=text.replace('SHA256-release-0.3.9-0.5.0.txt','SHA256-release-android-0.5.0.txt')
path.write_text(text+plain,encoding='utf-8')
path=ROOT/'README.md';text=path.read_text(encoding='utf-8')
text=text.replace('当前源码及正式版本：**Windows 0.3.9 / Android 0.4.9（versionCode 409）**。本版加入手动清理下载缓存，并显示自动清理的文件数、释放空间与失败提示。','当前源码及正式版本：**Windows 0.3.9 / Android 0.5.0（versionCode 500）**。Android 0.5.0 优化图片处理并行、CDN 线路选择及临时图片刷盘，保留完整性校验和断点续传。')
text=text.replace('当前正式版为 **Windows 0.3.9 / Android 0.4.9**（[发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.9-0.4.9)）。','当前正式版为 **Windows 0.3.9 / Android 0.5.0**（[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.5.0)，[Windows 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.9-0.4.9)）。')
lines=text.splitlines()
for i,line in enumerate(lines):
    if line.startswith('| Android 0.4.9'):
        lines[i]=line.replace('0.4.9','0.5.0').replace('release-0.3.9-0.5.0','release-android-0.5.0')
    elif line.startswith('| 上述版本的 SHA-256'):
        lines[i]=line.replace('上述版本的 SHA-256','Windows 0.3.9 的 SHA-256')+'\n'+line.replace('上述版本的 SHA-256','Android 0.5.0 的 SHA-256').replace('release-0.3.9-0.4.9','release-android-0.5.0')
text='\n'.join(lines)+'\n\nAndroid 0.5.0 下载优化：网络接收与图片处理使用有界流水线；每任务预取中的原始图片不超过图片线程数加处理线程数（最多 20 张，每张响应最多 64 MiB）。图片处理根据 CPU 最多并行 4 张，并由所有任务共享位图内存预算；内存不足时等待，不降低图片分辨率。CDN 记住成功线路，故障退避，并有限比较备用线路；只省去可丢弃原始临时文件的强制刷盘，处理后缓存与最终保存仍校验并持久化。继续仅补缺失或损坏页；设置变化用于新任务或手动重试。宿主合成测试不能代表手机速度，未承诺达到网络测速上限。\n'
path.write_text(text,encoding='utf-8')
print('Prepared Android 0.5.0 / 500 notes and versions; Windows remains 0.3.9')
