"""Prepare versioned documentation for the authorized metadata optimization."""
from pathlib import Path
import json
import re

root=Path(__file__).resolve().parents[3]
notes='''# Windows 0.3.7 / Android 0.4.7 — 2026-10-16

## 多章节读取提速与缓存

- 所选章节详情改为每任务最多 4 章并行读取，独立于图片线程数；只读取选中的章节，始终保留原章节编号、下载和导出顺序。
- 每章读取成功后立即保存到应用内部的任务缓存。暂停后继续、重启应用、重试及自动重连可复用已完成的章节信息，未读完的章节继续获取。
- 章节缓存有效期为 24 小时；过期、损坏、格式不兼容、账号 Cookie 或漫画目录信息变化时自动重新读取。图片下载失败时清除对应章节信息，供下次重试刷新；其他章节缓存保留。
- 读取进度显示已完成章节数、复用缓存章数及并行上限。暂停会结束该任务的在途请求，Android 等待旧章节线程退出后才允许重连，避免重复写入。
- 每次开始仍会联网确认漫画目录和所选章节；缓存不意味着可离线开始下载。现有任务首次使用新版需读取一次章节信息，之后即可复用。
- 缓存保存在应用内部，不加入 PDF、ZIP 或图片文件夹成品；图片缓存、断点续传及章节选择保持兼容。

## 版本与验证

- Windows 升至 0.3.7；Android 升至 0.4.7（versionCode 407），沿用原包名、APK 签名身份和更新公钥。
- 覆盖有界并发、乱序返回、部分失败、暂停/重启续读、缓存过期与损坏回退；Windows 源码和冻结成品均执行离线自检。
- Android 执行宿主测试、编译和原证书签名核验；未进行 Android 真机界面或网站下载验证。
- 同步源码、使用说明、同版日志、双端安装包、SHA-256 校验文件和签名更新清单。
'''
folder=root/'work/release-037-047';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=root/'CHANGELOG.md'
if not p.read_text(encoding='utf-8').startswith(notes):p.write_text(notes+'\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
for name in ['work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle','README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    p=root/name;text=p.read_text(encoding='utf-8').replace('0.3.6','0.3.7').replace('0.4.6','0.4.7').replace('versionCode 406','versionCode 407').replace('versionCode="406"','versionCode="407"')
    if name=='README.md':text=text.replace('本版支持获取章节后选择下载范围，可在设置中默认下载全章节。','本版优化多章节读取：最多 4 章并行，并缓存章节信息以加快暂停后的继续下载。')
    p.write_text(text,encoding='utf-8')
addition='\n章节读取提速：每任务最多 4 章并行读取，图片线程数不影响此上限。成功读取的章节在任务内部缓存 24 小时，暂停/重启/重试可复用；过期、损坏、Cookie 或目录信息变化会重新获取。进度显示复用章数；每次开始仍会联网确认漫画目录。旧任务首次使用新版需读取一次，缓存不会出现在导出的漫画中。\n'
for name in ['README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt']:
    p=root/name;text=p.read_text(encoding='utf-8')
    if addition.strip() not in text:p.write_text(text+addition,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ['work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java']:
    p=root/name;text=p.read_text(encoding='utf-8')
    text=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if name.endswith('.java') else ''),text)
    p.write_text(text,encoding='utf-8')
for prefix in ['prepare_publication','publish']:
    source=root/f'work/scripts/release/{prefix}_036_046.py'
    text=source.read_text(encoding='utf-8').replace('0.3.6','0.3.7').replace('0.4.6','0.4.7').replace('036-046','037-047').replace('下载章节选择','多章节读取提速与缓存')
    (source.parent/f'{prefix}_037_047.py').write_text(text,encoding='utf-8')
source=root/'work/scripts/maintenance/verify_chapter_selection_online.py'
text=source.read_text(encoding='utf-8').replace('0.3.6','0.3.7').replace('0.3.5','0.3.6').replace('0.4.6','0.4.7').replace('036-046','037-047').replace('chapter-choice','chapter-metadata').replace('下载章节选择','多章节读取提速与缓存')
text=text.replace("'0.3.4', '0.3.6', '0.3.7'", "'0.3.4', '0.3.5', '0.3.6', '0.3.7'")
(source.parent/'verify_chapter_metadata_online.py').write_text(text,encoding='utf-8')
print('Prepared Windows 0.3.7 / Android 0.4.7 documentation and release recipes')
