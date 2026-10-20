"""Prepare both chapter-view releases and the reviewed publication recipes."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
notes = """# Windows 0.3.28 / Android 0.6.10 — 多章节观看模式

## 更新内容

- 设置中新增“多章节观看模式”：1 多章节合一，保持原来的整本连续阅读；2 分章节观看，每次只显示当前章节。
- 默认使用模式 1。选择模式 2 后，上下滚动、左右翻页和上一页/下一页都停留在本章范围；使用上一章、下一章或章节列表切换章节。
- 设置保存后重新打开漫画生效。保留原有全书阅读位置、书签与收藏；总页码跳转和跨章书签自动打开目标章节，无需重新下载。
- 图片文件夹和分章 ZIP 按已有章节划分；PDF、平铺 ZIP 和单章漫画仍作为一个章节。下载及导出格式保持原有规则。

## 版本与验证

- Windows 0.3.27 → 0.3.28；Android 0.6.9 → 0.6.10（versionCode 610），保留 app.jmbatch.android 包名、原 APK 签名和更新公钥。
- 验证设置持久化、旧设置兼容、章首/章末边界、滚动与翻页切换、跨章跳转、书签及阅读位置恢复，并回归阅读缓存稳定性和页面索引。
- 完成双端构建、Windows 源码及冻结成品专项检查、Android 10/15 框架检查和签名/交付校验；未进行 Android 真机验证。
"""
folder = ROOT / "work/release-0328-0610"
folder.mkdir(exist_ok=True)
(folder / "release-notes.md").write_text(notes, encoding="utf-8")
p = ROOT / "CHANGELOG.md"
text = p.read_text(encoding="utf-8")
if not text.startswith(notes):
    p.write_text(notes + "\n" + text, encoding="utf-8")
for name in ("work/jmbatch/core.py", "work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java",
             "work/jmbatch-android/app/src/main/AndroidManifest.xml", "work/jmbatch-android/app/build.gradle"):
    p = ROOT / name
    text = p.read_text(encoding="utf-8").replace("0.3.27", "0.3.28").replace("0.6.9", "0.6.10")
    text = text.replace("versionCode 609", "versionCode 610").replace('versionCode="609"', 'versionCode="610"')
    p.write_text(text, encoding="utf-8")
plain = re.sub(r"(?m)^#{1,6} ", "", notes).replace("- ", "• ")
for name in ("work/jmbatch/updates.py", "work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java"):
    p = ROOT / name
    text = re.sub(r"(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$",
                  lambda m: m[1] + json.dumps(plain, ensure_ascii=False) + (";" if p.suffix == ".java" else ""),
                  p.read_text(encoding="utf-8"))
    p.write_text(text, encoding="utf-8")
for name, version in (("work/jmbatch/README.txt", "0.3.28"), ("work/jmbatch-android/README.txt", "0.6.10")):
    p = ROOT / name
    text = re.split(r"\n(?:Windows \d+\.\d+\.\d+ / Android \d+\.\d+\.\d+|Android \d+\.\d+\.\d+) — ",
                    p.read_text(encoding="utf-8"), maxsplit=1)[0].rstrip() + "\n"
    text = re.sub(r"^JM Batch [\d.]+", "JM Batch " + version, text)
    text = re.sub(r"release-(?:android-)?[\d.]+(?:-[\d.]+)?", "release-0.3.28-0.6.10", text)
    text = re.sub(r"JMBatch-[\d.]+-", "JMBatch-" + version + "-", text)
    text = re.sub(r"安装包下载（[\d-]+）", "安装包下载（2026-10-20）", text)
    p.write_text(text + "\n" + plain, encoding="utf-8")
p = ROOT / "README.md"
text = p.read_text(encoding="utf-8")
head, rest = text.split("## 下载图片与系统相册", 1)
head = head.replace("release-0.3.27-0.6.7", "release-0.3.28-0.6.10").replace("release-android-0.6.9", "release-0.3.28-0.6.10")
head = head.replace("0.3.27", "0.3.28").replace("0.6.9", "0.6.10").replace("versionCode 609", "versionCode 610")
head = head.replace("Android 下载图片对系统相册隐藏，自动为可访问的旧漫画补上隐藏标记，保留应用内阅读与导出。",
                    "双端设置支持多章节合一或分章节观看，保留书签与阅读位置。")
text = head + "## 下载图片与系统相册" + rest
text = text.replace("## 内置阅读器\n", "## 内置阅读器\n\n在“下载设置”中选择“多章节观看模式”：**1 多章节合一**（默认）整本连续阅读；**2 分章节观看**只显示当前章，章末通过上一章、下一章或章节列表切换。保存后重新打开漫画生效；两种模式共享阅读位置和书签，总页码跳转及书签可跨章。PDF、平铺 ZIP 和单章漫画仍作为一个章节。\n", 1)
p.write_text(text, encoding="utf-8")
mapping = {"0.3.27": "0.3.28", "0.6.7": "0.6.10", "0327-067": "0328-0610", "<= 607": "<= 610",
           "全部封面统一自适应": "多章节观看模式"}
pattern = re.compile("|".join(map(re.escape, mapping)))
for name in ("prepare_publication", "publish"):
    p = ROOT / f"work/scripts/release/{name}_0327_067.py"
    (p.parent / f"{name}_0328_0610.py").write_text(pattern.sub(lambda m: mapping[m[0]], p.read_text(encoding="utf-8")), encoding="utf-8")
p = ROOT / "work/scripts/maintenance/build_all_cover_release.py"
text = pattern.sub(lambda m: mapping[m[0]], p.read_text(encoding="utf-8")).replace("all-cover-", "chapter-view-")
text = text.replace("--self-test-tiles", "--self-test-chapter-view").replace("tile-selftest", "chapter-view-selftest")
text = text.replace("len(data['checks'])==7", "len(data['checks'])==6").replace("versionCode='607'", "versionCode='610'")
(p.parent / "build_chapter_view_release.py").write_text(text, encoding="utf-8")
mapping.update({"0.3.26": "0.3.27", "0.6.6": "0.6.9", "all-cover-": "chapter-view-",
                "LiveAllCoverUpdate": "LiveChapterViewUpdate", "40-release": "43-release",
                "!=40": "!=43", "full_history_versions=40": "full_history_versions=43"})
pattern = re.compile("|".join(map(re.escape, sorted(mapping, key=len, reverse=True))))
p = ROOT / "work/scripts/maintenance/verify_all_cover_online.py"
(p.parent / "verify_chapter_view_online.py").write_text(pattern.sub(lambda m: mapping[m[0]], p.read_text(encoding="utf-8")), encoding="utf-8")
p = ROOT / "work/scripts/release/verify_all_cover_commit.py"
(p.parent / "verify_chapter_view_commit.py").write_text(p.read_text(encoding="utf-8").replace("all-cover-0327-067", "chapter-view-0328-0610"), encoding="utf-8")
print("Prepared Windows 0.3.28 / Android 0.6.10 (610)")
