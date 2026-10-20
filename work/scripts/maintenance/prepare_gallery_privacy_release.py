"""Prepare the authorized Android-only gallery privacy release."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
ANDROID = ROOT / "work/jmbatch-android"
JAVA = ANDROID / "app/src/main/java/app/jmbatch/android"
NOTES = """# Android 0.6.9 — 下载图片对系统相册隐藏

## 更新内容

- 下载为图片文件夹、导出为图片文件夹时，先写入 Android 标准 .nomedia 标记，再保存图片，让系统媒体扫描忽略漫画文件夹及其子目录。
- 启动应用后，后台为应用下载目录、当前及历史授权目录中可识别的旧漫画，以及漫画库和任务记录中的图片文件夹补上标记。已有图片、文件名、阅读进度和收藏保持不变。
- 自选公共目录只标记漫画子文件夹，不给公共目录根层添加标记，不影响同目录的其他照片。
- 保留应用内封面、阅读、格式导出、章节删除和取消清理。PDF、ZIP 的内容保持原有规则。
- 存储服务不支持准确创建标记时，停止新图片写入并提示原因；旧下载无法访问或授权失效时显示提示，重新授权或下次启动后重试。

## 使用说明

- 覆盖安装后打开一次应用，等待后台处理旧下载。已被相册收录的图片可能需要等待系统媒体索引和相册缓存刷新，部分设备需重启后刷新；第三方相册是否遵循标记取决于其实现。
- 这是相册扫描隐藏，不是加密；图片仍可通过应用内漫画库和文件管理器访问。请勿删除漫画文件夹里的 .nomedia 文件。

## 版本与验证

- Android 0.6.8 → 0.6.9（versionCode 609），保留 app.jmbatch.android 包名、原 APK 签名和更新公钥，可覆盖安装。Windows 保持 0.3.27。
- 验证本地及 SAF 目录的标记先行、旧下载补标记、重复处理、失败重试、公共目录隔离、文件夹导出、阅读与章节删除关联流程；完整编译、原签名及更新清单校验。
- 本次未连接 Android 真机；自动化框架测试不代表厂商相册缓存刷新效果已实测。
"""

def replace(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, (path, old)
    path.write_text(text.replace(old, new), encoding="utf-8")

notes = ROOT / "work/release-android-069/release-notes.md"
notes.parent.mkdir(parents=True, exist_ok=True)
notes.write_text(NOTES, encoding="utf-8")
replace(JAVA / "Core.java", 'VERSION = "0.6.8"', 'VERSION = "0.6.9"')
for path, old, new in [
    (ANDROID / "app/src/main/AndroidManifest.xml", 'versionCode="608"', 'versionCode="609"'),
    (ANDROID / "app/src/main/AndroidManifest.xml", 'versionName="0.6.8"', 'versionName="0.6.9"'),
    (ANDROID / "app/build.gradle", "versionCode 608", "versionCode 609"),
    (ANDROID / "app/build.gradle", "versionName '0.6.8'", "versionName '0.6.9'"),
]:
    replace(path, old, new)
plain = re.sub(r"^#{1,2} ", "", NOTES, flags=re.M).replace("- ", "• ")
path = JAVA / "GithubUpdates.java"
text, count = re.subn(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',
    lambda m: "private static final String CURRENT_NOTES=" + json.dumps(plain, ensure_ascii=False) + ";",
    path.read_text(encoding="utf-8"))
assert count == 1
path.write_text(text, encoding="utf-8")
path = ROOT / "CHANGELOG.md"
path.write_text(NOTES + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
path = ANDROID / "README.txt"
text = path.read_text(encoding="utf-8").split("Android 0.6.8 — 滚动阅读稳定性修复")[0].rstrip()
text = text.replace("0.6.8", "0.6.9").replace("文件夹和 ZIP 只含图片：", "ZIP 只含图片，图片文件夹另含相册隐藏标记 .nomedia：")
path.write_text(text + "\n\n" + plain, encoding="utf-8")
path = ROOT / "README.md"
lines = []
for line in path.read_text(encoding="utf-8").splitlines():
    if line.startswith("当前正式版本："):
        line = "当前正式版本：**Windows 0.3.27 / Android 0.6.9（versionCode 609）**。Android 下载图片对系统相册隐藏，自动为可访问的旧漫画补上隐藏标记，保留应用内阅读与导出。安装包、更新日志与镜像入口见下方。"
    elif line.startswith("当前正式版为 ") or line.startswith("| Android "):
        line = line.replace("0.6.8", "0.6.9")
    lines.append(line)
text = "\n".join(lines) + "\n"
text = text.replace("## 收藏夹\n", "## 下载图片与系统相册\n\nAndroid 0.6.9 在漫画文件夹内自动保留 `.nomedia`，启动时为可访问的旧下载补标记。不会隐藏公共保存目录里的其他照片。旧相册缩略图需等待系统索引/缓存刷新；图片仍可在漫画库或文件管理器中访问，此功能不加密文件。\n\n## 收藏夹\n")
path.write_text(text, encoding="utf-8")

mapping = {"0.6.8":"0.6.9","0.6.7":"0.6.8","608":"609","607":"608","068":"069",
           "reader-scroll-fix":"gallery-privacy","滚动阅读稳定性修复":"下载图片对系统相册隐藏",
           "LiveReaderScrollUpdate":"LiveGalleryPrivacyUpdate","!=41":"!=42","41-release":"42-release","full_history_versions=41":"full_history_versions=42"}
pattern = re.compile("|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)))
for folder, old, new in [
    ("release","prepare_publication_android_068.py","prepare_publication_android_069.py"),
    ("release","publish_android_068.py","publish_android_069.py"),
    ("maintenance","verify_reader_scroll_online.py","verify_gallery_privacy_online.py"),
    ("release","verify_reader_scroll_commit.py","verify_gallery_privacy_commit.py"),
]:
    source = ROOT / "work/scripts" / folder / old
    (source.parent / new).write_text(pattern.sub(lambda m:mapping[m[0]], source.read_text(encoding="utf-8")), encoding="utf-8")
print("Prepared Android 0.6.9 / 609; Windows remains 0.3.27.")
