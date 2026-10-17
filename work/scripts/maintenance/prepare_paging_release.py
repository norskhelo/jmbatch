"""Prepare the explicitly requested dual-platform reader release; no publication."""
import json
import re
from pathlib import Path

root=Path(__file__).resolve().parents[3]
notes='''# Windows 0.3.11 / Android 0.5.5 — 左右翻页流畅度修复

## 阅读体验

- 左右翻页加载新页时保留当前图片，新图就绪后再切换，避免先清空页面造成闪屏；加载失败明确显示目标页并允许继续翻页。
- 按阅读方向预加载相邻页，使用有上限的图片缓存；合并重复加载请求，快速正反向翻页时不再重复解码同一运行任务。
- Android 支持跟手横向拖动、松手翻页和短拖回弹；Windows 支持鼠标拖动及按钮/键盘翻页过渡。相邻页未准备好时保留当前页，首尾越界回弹，快速反向操作可取消旧动画。
- 页码、书签和阅读记录跟随实际显示页，动画未完成或目标加载失败时不提前记录为已经阅读；继续兼容滚动模式、章节跳转、图片目录、ZIP 和 PDF。
- Windows 加载期间缩短结果轮询等待并复用图片图层；Android 减少重复布局，阅读记录由有序后台线程保存，遵循系统动画开关。

## 版本与验证

- Windows 0.3.10 → 0.3.11；Android 0.5.4 → 0.5.5（versionCode 505）。沿用 Android 包名、APK 原签名证书和应用更新公钥。
- 验证慢加载保留旧页、邻页预加载、快速往返去重、拖动/回弹、动画中反向、损坏页、边界、模式及尺寸变化、收藏书签和重开位置；使用隔离生成素材。
- Windows 执行回归与源码/冻结成品的实际 Tk 界面自检；Android 执行宿主手势/调度检查、完整编译和原签名核验。未连接 Android 真机，宿主验证不代表手机实测帧率。
- 提供双端安装包、同版日志、SHA-256、更新清单及原密钥签名，并发布对应源码与使用说明。
'''
folder=root/'work/release-0311-055';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=root/'CHANGELOG.md';value=p.read_text(encoding='utf-8')
if not value.startswith(notes): p.write_text(notes+'\n'+value,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=root/name;value=p.read_text(encoding='utf-8').replace('0.3.10','0.3.11').replace('0.5.4','0.5.5').replace('versionCode 504','versionCode 505').replace('versionCode="504"','versionCode="505"')
    p.write_text(value,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=root/name;value=p.read_text(encoding='utf-8')
    value=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if name.endswith('.java') else ''),value)
    p.write_text(value,encoding='utf-8')
for name in ('README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt'):
    p=root/name;value=p.read_text(encoding='utf-8')
    if name!='README.md': value=re.split(r'\nWindows 0\.3\.10 / Android 0\.5\.4 — ',value)[0].rstrip()+'\n'
    value=value.replace('0.3.10','0.3.11').replace('0.5.4','0.5.5').replace('versionCode 504','versionCode 505')
    value=value.replace('本版取消任务后自动删除任务文件和记录；暂停仍保留完整图片及断点续传。','本版修复左右翻页闪屏，加入邻页预加载、跟手拖动与翻页回弹动画。')
    if name!='README.md': value+='\n'+plain
    elif '## 翻页体验' not in value: value+='\n## 翻页体验\n\n左右翻页保留旧图直到新页就绪，按阅读方向预加载邻页。Windows 可鼠标拖动，Android 可跟手滑动；短拖和越界回弹。页码、书签和阅读位置在新页显示后提交。缓存有内存上限，目标页尚未就绪时显示加载提示。\n'
    p.write_text(value,encoding='utf-8')
# Version-specific release recipes retain all established signature and remote checks.
for old,new in (('prepare_publication_0310_054.py','prepare_publication_0311_055.py'),('publish_0310_054.py','publish_0311_055.py')):
    p=root/'work/scripts/release'/old;s=p.read_text(encoding='utf-8')
    s=s.replace('0.3.10','0.3.11').replace('0.5.4','0.5.5').replace('0310-054','0311-055').replace('<= 504','<= 505')
    s=s.replace('取消任务自动删除文件与记录','左右翻页闪屏与流畅度修复')
    (p.parent/new).write_text(s,encoding='utf-8')
print('Prepared Windows 0.3.11 / Android 0.5.5, versionCode 505, notes and release recipes')
