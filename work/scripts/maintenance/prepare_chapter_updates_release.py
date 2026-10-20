"""Prepare the two independently versioned chapter-update releases."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
notes = """# Windows 0.3.29 / Android 0.6.11 — 漫画库检查章节更新

发布日期：2026-10-20

## 新增
- 漫画库进入“批量处理”并选中一本漫画后，可点击“检查更新”；Android 的“更多操作”也提供入口。
- 先联网读取章节目录，按章节 ID 对比已知章节；有新章节时显示数量和名称，再询问是否下载。检查阶段不下载漫画图片。
- 确认后仅将新章节交给正常下载队列，使用当前下载设置，支持原有暂停、继续、失败重试及自动重连。新章节保存为独立漫画，原文件和阅读记录保留。
- 暂不下载、取消检查或下载失败不会消耗更新提示；同一本存在未完成任务时阻止重复加入。
- 已知章节记录在本地持久保存。兼容保留章节记录的旧任务；无可用记录的导入漫画首次建立当前目录基线，并明确提示，下次开始检查新增章节。

## 兼容与验证
- Windows 0.3.29；Android 0.6.11（versionCode 611），保留原包名、原 APK 签名和更新公钥。
- 验证新章节识别、目录重排、旧选择与旧记录、确认/拒绝/取消、队列持久化和正常章节下载；执行双端构建、冻结程序检查及签名校验。
- Android 使用 Android 10/15 框架和合成数据验证；未进行 Android 真机验证。
"""
folder = ROOT / "work/release-0329-0611"
folder.mkdir(parents=True, exist_ok=True)
(folder / "release-notes.md").write_text(notes, encoding="utf-8")
p = ROOT / "CHANGELOG.md"
if not p.read_text(encoding="utf-8").startswith(notes):
    p.write_text(notes + "\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
mapping = {"0.3.28": "0.3.29", "0.6.10": "0.6.11", "0328-0610": "0329-0611"}
def replace(text):
    for old, new in mapping.items():
        text = text.replace(old, new)
    return text
for name in ("work/jmbatch/core.py", "work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java",
             "work/jmbatch-android/app/src/main/AndroidManifest.xml", "work/jmbatch-android/app/build.gradle"):
    p = ROOT / name
    p.write_text(replace(p.read_text(encoding="utf-8")).replace("versionCode 610", "versionCode 611").replace('versionCode="610"', 'versionCode="611"'), encoding="utf-8")
plain = re.sub(r"(?m)^#{1,6} ", "", notes).replace("- ", "• ")
for name in ("work/jmbatch/updates.py", "work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java"):
    p = ROOT / name
    text = re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',
                  lambda m: m[1] + json.dumps(plain, ensure_ascii=False) + (";" if p.suffix == ".java" else ""),
                  p.read_text(encoding="utf-8"))
    p.write_text(text, encoding="utf-8")
for name in ("work/jmbatch/README.txt", "work/jmbatch-android/README.txt"):
    p = ROOT / name
    text = re.split(r"\n(?:Windows \d+\.\d+\.\d+ / Android \d+\.\d+\.\d+|Android \d+\.\d+\.\d+) — ",
                    p.read_text(encoding="utf-8"), maxsplit=1)[0].rstrip()
    p.write_text(replace(text) + "\n\n" + plain, encoding="utf-8")
p = ROOT / "README.md"
text = p.read_text(encoding="utf-8")
head, rest = text.split("## 下载图片与系统相册", 1)
head = replace(head).replace("versionCode 610", "versionCode 611")
head = head.replace("双端设置支持多章节合一或分章节观看，保留书签与阅读位置。", "双端漫画库支持先检查新章节，再确认使用正常下载功能下载。")
section = """## 检查漫画章节更新

漫画库 → 批量处理（或长按）→ 选中一本 → 检查更新。Android 也可从“更多操作”进入。先只读取服务器章节目录，有新增章节再确认下载；新章节使用当前下载设置，作为独立漫画保存，原文件和阅读记录保留。暂不下载后，下次仍会提示；同一本已有未完成任务时请先继续、重试或取消原任务。

检查使用本地保存的章节 ID，避免标题、顺序变化或旧的未选章节造成误报。缺少可用下载记录的导入漫画，首次只建立当前目录基线并提示，后续才可识别新章节。旧的全部章节下载记录按最后一个可匹配的已下载章节恢复旧目录前缀。

"""
if "## 检查漫画章节更新" not in head:
    head += section
p.write_text(head + "## 下载图片与系统相册" + rest, encoding="utf-8")
for kind in ("prepare_publication", "publish"):
    source = ROOT / f"work/scripts/release/{kind}_0328_0610.py"
    text = replace(source.read_text(encoding="utf-8")).replace("<= 610", "<= 611").replace("多章节观看模式", "漫画库检查章节更新")
    (source.parent / f"{kind}_0329_0611.py").write_text(text, encoding="utf-8")
source = ROOT / "work/scripts/maintenance/build_chapter_view_release.py"
text = replace(source.read_text(encoding="utf-8")).replace("chapter-view", "chapter-updates").replace("len(data['checks'])==6", "len(data['checks'])==4").replace("versionCode='610'", "versionCode='611'")
text = text.replace("test=ROOT/'work/tests'/", "suffix='-'+sys.argv[2] if len(sys.argv)>2 else ''\ntest=ROOT/'work/tests'/")
text = text.replace("f'chapter-updates-0329-0611-{platform}'", "f'chapter-updates-0329-0611-{platform}{suffix}'")
(source.parent / "build_chapter_updates_release.py").write_text(text, encoding="utf-8")
source = ROOT / "work/scripts/release/verify_chapter_view_commit.py"
(source.parent / "verify_chapter_updates_commit.py").write_text(replace(source.read_text(encoding="utf-8")).replace("chapter-view", "chapter-updates"), encoding="utf-8")
print("Prepared Windows 0.3.29 / Android 0.6.11 (611)")
