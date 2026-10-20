"""Prepare the authorized Android-only 0.6.8 release and its explicit recipes."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ANDROID = ROOT / "work/jmbatch-android"
JAVA = ANDROID / "app/src/main/java/app/jmbatch/android"
NOTES = """# Android 0.6.8 — 滚动阅读稳定性修复

## 修复内容

- 修复上下滚动阅读时图片反复出现“正在加载”、页面高度来回变化和画面上下抖动的问题。预加载预算查询不再错误提升屏幕外图片的缓存优先级。
- 已显示的有效图片在共享缓存被淘汰后继续显示；已知页面尺寸独立保存，回滚和行复用不再退回默认占位高度。
- 仅在图片或文字实际改变时更新对应控件；离屏回收和关闭阅读器时释放行内图片引用。图片缓存仍为 32 MiB，按可见图片占用计算后续预加载预算。
- 保留原漫画、下载、书签和阅读页码，支持沉浸模式、滚动与左右翻页切换；无需清理缓存或重新下载漫画。

## 版本与验证

- Android 0.6.7 → 0.6.8（versionCode 608），保留 app.jmbatch.android 包名、原 APK 签名和更新公钥，可覆盖安装。Windows 保持 0.3.27。
- 通过 Android 10/15 的滚动稳定性、缓存压力、页高复用、快速回滚、模式切换与关闭回调测试，并验证阅读索引及分页相关回归。
- 使用隔离合成图片对照旧版；真机触发受分辨率、图片比例与停留位置影响，本次未连接手机做视觉或帧时间实测。

## 旧版复现条件

- 0.6.7 上使用约 1440 像素宽的阅读区，准备竖图、横图、长图交替的漫画。先读到约第 9–11 页，再向前滚回。
- 停在第 1 页下半部、第 2 页横图和第 3 页长图开头同时可见的位置，第 4 页留在屏幕外；停手后观察加载提示和页高是否仍循环变化。
- 仓库 work/jmbatch-android/tests/runtime/READER_SCROLL_REPRO.txt 提供合成测试漫画生成方法与自动化复现命令；框架对照可重复触发，不保证所有手机手动必现。
"""


def replace(path, old, new):
    value = path.read_text(encoding="utf-8")
    assert old in value, (path, old)
    path.write_text(value.replace(old, new), encoding="utf-8")


notes = ROOT / "work/release-android-068/release-notes.md"
notes.parent.mkdir(parents=True, exist_ok=True)
notes.write_text(NOTES, encoding="utf-8")
replace(JAVA / "Core.java", 'VERSION = "0.6.7"', 'VERSION = "0.6.8"')
replace(ANDROID / "app/src/main/AndroidManifest.xml", 'versionCode="607"', 'versionCode="608"')
replace(ANDROID / "app/src/main/AndroidManifest.xml", 'versionName="0.6.7"', 'versionName="0.6.8"')
replace(ANDROID / "app/build.gradle", "versionCode 607", "versionCode 608")
replace(ANDROID / "app/build.gradle", "versionName '0.6.7'", "versionName '0.6.8'")
plain = re.sub(r"^#{1,2} ", "", NOTES, flags=re.M).replace("- ", "• ")
path = JAVA / "GithubUpdates.java"
value, count = re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',
    lambda m: "private static final String CURRENT_NOTES=" + json.dumps(plain, ensure_ascii=False) + ";",
    path.read_text(encoding="utf-8"))
assert count == 1
path.write_text(value, encoding="utf-8")
path = ROOT / "CHANGELOG.md"
path.write_text(NOTES + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
path = ANDROID / "README.txt"
value = path.read_text(encoding="utf-8").split("Windows 0.3.27 / Android 0.6.7 —")[0].rstrip()
value = value.replace("JM Batch 0.6.7", "JM Batch 0.6.8").replace("安装包下载（2026-10-19）", "安装包下载（2026-10-20）")
value = re.sub(r"release-0\.3\.\d+-0\.6\.\d+/JMBatch-0\.6\.\d+-Android\.apk",
               "release-android-0.6.8/JMBatch-0.6.8-Android.apk", value)
value = re.sub(r"release-0\.3\.\d+-0\.6\.\d+/SHA256-release-0\.3\.\d+-0\.6\.\d+\.txt",
               "release-android-0.6.8/SHA256-release-android-0.6.8.txt", value)
path.write_text(value + "\n\n" + plain, encoding="utf-8")
path = ROOT / "README.md"
result = []
for line in path.read_text(encoding="utf-8").splitlines():
    if line.startswith("当前正式版本："):
        line = "当前正式版本：**Windows 0.3.27 / Android 0.6.8（versionCode 608）**。Android 修复上下滚动阅读时的画面抖动和加载闪烁，保留已显示图片与已知页高。安装包、更新日志与镜像入口见下方。"
    elif line.startswith("当前正式版为 "):
        line = line.replace("Android 0.6.7", "Android 0.6.8").replace("[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-0.3.27-0.6.7)", "[Android 发布说明](https://github.com/norskhelo/jmbatch/releases/tag/release-android-0.6.8)")
    elif line.startswith("| Android "):
        line = line.replace("SHA256-release-0.3.27-0.6.7.txt", "SHA256-release-android-0.6.8.txt").replace("release-0.3.27-0.6.7", "release-android-0.6.8").replace("0.6.7", "0.6.8")
    result.append(line)
value = "\n".join(result) + "\n"
value = value.replace("## 内置阅读器\n", "## 内置阅读器\n\nAndroid 0.6.8 修复滚动时的缓存反复淘汰与加载闪烁，保留可见图片和已知页高。旧版复现步骤与合成测试漫画生成方法见 [阅读稳定性复现说明](work/jmbatch-android/tests/runtime/READER_SCROLL_REPRO.txt)。\n")
path.write_text(value, encoding="utf-8")

mapping = {"0.6.2": "0.6.8", "0.6.1": "0.6.7", "602": "608", "601": "607", "062": "068",
           "0.3.22": "0.3.27", "0.3.21": "0.3.26", "dns-speed": "reader-scroll-fix",
           "备用 DNS 图片下载提速": "滚动阅读稳定性修复", "LiveDnsSpeedUpdate": "LiveReaderScrollUpdate",
           "!=35": "!=41", "35-release": "41-release", "full_history_versions=35": "full_history_versions=41"}
pattern = re.compile("|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)))
for folder, old, new in [
    ("release", "prepare_publication_android_062.py", "prepare_publication_android_068.py"),
    ("release", "publish_android_062.py", "publish_android_068.py"),
    ("maintenance", "verify_dns_speed_online.py", "verify_reader_scroll_online.py"),
]:
    path = ROOT / "work/scripts" / folder / old
    (path.parent / new).write_text(pattern.sub(lambda m: mapping[m[0]], path.read_text(encoding="utf-8")), encoding="utf-8")
path = ROOT / "work/scripts/release/verify_all_cover_commit.py"
(path.parent / "verify_reader_scroll_commit.py").write_text(path.read_text(encoding="utf-8").replace(
    "all-cover-0327-067-complete", "reader-scroll-fix-068-complete"), encoding="utf-8")
print("Prepared Android 0.6.8 / 608; Windows remains 0.3.27.")
