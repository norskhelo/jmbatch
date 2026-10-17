"""Prepare the paired immersive-reader release and its matching user notes."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.15 / Android 0.5.10 — 沉浸阅读

## 阅读体验

- 在软件内阅读时，轻点漫画区域即可隐藏阅读工具栏、页码状态栏和滚动条，只保留漫画；再次轻点恢复。
- 工具栏以约 220 毫秒的滑动过渡收起或展开，Android 同时淡入淡出；动画中再次点击可平滑反向。Android 遵循系统动画开关，隐藏时同时收起系统状态栏与导航栏。
- 滚动阅读和左右翻页均支持。轻点页面任何位置统一切换工具栏，左右滑动/拖动继续翻页；Windows 还可使用方向键、PageUp/PageDown 或滚轮，工具栏显示时仍可点击上一页/下一页。
- 区分轻点、滑动和长按，Android 多指操作不触发工具栏切换。收起与恢复保留当前页，滚动模式的高度变化不重新解码漫画。
- Windows 按 Esc 可恢复工具栏；Android 隐藏时按返回先恢复工具栏，再次返回退出阅读。

## 版本与兼容性

- Windows 0.3.14 → 0.3.15；Android 0.5.9 → 0.5.10（versionCode 510）。保留原应用包名、APK 签名证书及更新公钥。
- 图片文件夹、ZIP、PDF，以及章节、收藏、书签、阅读进度与下载设置继续兼容。
- 验证覆盖 Windows 实际阅读窗口和冻结成品、Android 宿主手势/动画/布局检查及原签名构建。未连接 Android 真机，宿主检查不代表手机视觉验收。
'''
folder = ROOT/'work/release-0315-0510'; folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes, encoding='utf-8')
p = ROOT/'CHANGELOG.md'; current = p.read_text(encoding='utf-8')
if not current.startswith(notes): p.write_text(notes+'\n'+current, encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p = ROOT/name
    s = p.read_text(encoding='utf-8').replace('0.3.14','0.3.15').replace('0.5.9','0.5.10').replace('versionCode 509','versionCode 510').replace('versionCode="509"','versionCode="510"')
    p.write_text(s, encoding='utf-8')
plain = notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p = ROOT/name
    s = re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',
        lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''), p.read_text(encoding='utf-8'))
    p.write_text(s, encoding='utf-8')
for name in ('README.md','work/jmbatch/README.txt','work/jmbatch-android/README.txt'):
    p = ROOT/name; s = p.read_text(encoding='utf-8')
    if name == 'README.md':
        header,body=s.split('## 下载与导出',1)
        header=header.replace('0.3.14','0.3.15').replace('0.5.9','0.5.10').replace('versionCode 509','versionCode 510')
        header=header.replace('本版统一双端界面文案，优化按钮名称、操作提示和使用说明。','本版加入双端点击隐藏/恢复阅读工具栏和过渡动画。')
        s=header+'## 下载与导出'+body
    else:
        s=s.split('\nWindows 0.3.14 / Android 0.5.9 — ')[0].rstrip()+'\n'
        s=s.replace('0.3.14','0.3.15').replace('0.5.9','0.5.10')
        s+='\n'+plain
    s=s.replace('Windows 使用滚轮、方向键或页面两侧，Android 使用上下滚动、左右滑动或页面两侧。',
        '轻点漫画隐藏或恢复工具栏，并有平滑过渡。Windows 使用滚轮、方向键或左右拖动，Android 使用上下滚动或左右滑动。Windows 按 Esc、Android 隐藏时按返回也可恢复工具栏。')
    p.write_text(s,encoding='utf-8')

# Keep the proven publication verification and online-update checks for this tag.
replacements = {'0.3.14':'0.3.15','0.3.13':'0.3.14','0.5.9':'0.5.10','0.5.8':'0.5.9',
    '0314-059':'0315-0510','0314_059':'0315_0510','copy-059':'immersive-0510',
    'copy':'immersive','界面文案规范化':'沉浸阅读','<= 509':'<= 510',
    'range(1,15)':'range(1,16)','!=19':'!=20','19-release':'20-release','full_history_versions=19':'full_history_versions=20'}
pattern = re.compile('|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True)))
for old,new in (
    ('release/prepare_publication_0314_059.py','release/prepare_publication_0315_0510.py'),
    ('release/publish_0314_059.py','release/publish_0315_0510.py'),
    ('release/verify_copy_commit.py','release/verify_immersive_commit.py'),
    ('maintenance/verify_copy_online.py','maintenance/verify_immersive_online.py'),
    ('maintenance/verify_android_copy_online.py','maintenance/verify_android_immersive_online.py')):
    p=ROOT/'work/scripts'/new
    p.write_text(pattern.sub(lambda m:replacements[m[0]],(ROOT/'work/scripts'/old).read_text(encoding='utf-8')),encoding='utf-8')
print('Prepared Windows 0.3.15 / Android 0.5.10 notes and publication scripts')
