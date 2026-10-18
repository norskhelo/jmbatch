"""Prepare the paired list/tile display release and its version-specific workflows."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
notes='''# Windows 0.3.20 / Android 0.5.17 — 列表与平铺显示

## 漫画库与下载列表

- 新增“列表 / 平铺”显示切换。默认保留原列表，漫画库和下载列表分别记住选择，关闭重开和重启后继续使用。
- 平铺以封面卡片排列漫画，按窗口或屏幕可用宽度自动调整列数。Android 大字号下减少列数，操作按钮继续自动换行。
- 切换显示时保留搜索、收藏筛选、批量模式与已选漫画，并尽量保持当前可见漫画的位置。漫画库继续支持点击阅读、长按批量处理、收藏、导出及删除。
- 下载卡片继续显示任务状态、进度与大小，下载任务和暂停续传不受显示切换影响。Android 卡片长文字可在“详情”中查看完整内容。
- 两种显示共用现有封面缓存，切换无需重新解析漫画；Windows 仅绘制可见卡片，避免为全部漫画创建界面控件。

## 版本与验证

- Windows 0.3.19 → 0.3.20；Android 0.5.16 → 0.5.17（versionCode 517）。沿用原 Android 包名、APK 签名证书和更新公钥。
- 验证覆盖列表和平铺的点击、长按、滚动取消、跨列选择、显示切换、浏览位置、进度刷新与独立设置保存；执行 Windows 完整回归及源码/打包自检、Android 宿主回归、字体/宽度布局检查和原签名构建。
- 未连接 Android 真机；手机上的手势和视觉效果仍需设备验证，宿主测试不代替真机验收。
'''
folder=ROOT/'work/release-0320-0517';folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=ROOT/'CHANGELOG.md';s=p.read_text(encoding='utf-8')
if not s.startswith(notes):p.write_text(notes+'\n'+s,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=ROOT/name;s=p.read_text(encoding='utf-8').replace('0.3.19','0.3.20').replace('0.5.16','0.5.17').replace('versionCode 516','versionCode 517').replace('versionCode="516"','versionCode="517"')
    p.write_text(s,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name;s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'));p.write_text(s,encoding='utf-8')
for name,number in (('work/jmbatch/README.txt','0.3.20'),('work/jmbatch-android/README.txt','0.5.17')):
    p=ROOT/name;s=p.read_text(encoding='utf-8')
    s=re.split(r'\n(?:Windows 0\.3\.\d+ / Android 0\.5\.\d+|Android 0\.5\.\d+) — ',s,maxsplit=1)[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+','JM Batch '+number,s)
    s=re.sub(r'release-(?:0\.3\.\d+-0\.5\.\d+|android-0\.5\.\d+)','release-0.3.20-0.5.17',s)
    s=re.sub(r'JMBatch-0\.3\.\d+-Windows','JMBatch-0.3.20-Windows',s)
    s=re.sub(r'JMBatch-0\.5\.\d+-Android','JMBatch-0.5.17-Android',s)
    p.write_text(s+'\n'+plain,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8');header,body=s.split('## 下载与导出',1)
header=re.sub(r'release-(?:0\.3\.\d+-0\.5\.\d+|android-0\.5\.\d+)','release-0.3.20-0.5.17',header)
header=header.replace('0.3.19','0.3.20').replace('0.5.16','0.5.17').replace('versionCode 516','versionCode 517')
header=header.replace('Android 修复漫画库批量选择时滑动或封面刷新导致的勾选动画闪动。','漫画库和下载列表新增“列表 / 平铺”切换，分别记住显示方式，并保留选择与浏览位置。')
s=header+'## 显示方式\n\n漫画库和下载列表均可选择“列表”或“平铺”，默认列表，各页面独立保存。平铺按可用宽度排列封面卡片；切换保留筛选、批量选择，并尽量保持当前浏览位置。下载不中断，封面继续复用缓存。Android 长任务信息可在“详情”查看。\n\n## 下载与导出'+body
p.write_text(s,encoding='utf-8')
changes={'0.3.19':'0.3.20','0.3.18':'0.3.19','0.5.15':'0.5.17','0.5.14':'0.5.16',
         '0319-0515':'0320-0517','0319_0515':'0320_0517','cover-cache-0515':'display-0517','cover_cache':'display',
         '漫画库封面缓存':'列表与平铺显示','<= 515':'<= 517','range(1,20)':'range(1,21)',
         '!=25':'!=27','25-release':'27-release','full_history_versions=25':'full_history_versions=27'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(changes,key=len,reverse=True)))
for old,new in (
    ('release/prepare_publication_0319_0515.py','release/prepare_publication_0320_0517.py'),
    ('release/publish_0319_0515.py','release/publish_0320_0517.py'),
    ('release/verify_cover_cache_commit.py','release/verify_display_commit.py'),
    ('maintenance/verify_cover_cache_online.py','maintenance/verify_display_online.py'),
    ('maintenance/verify_android_cover_cache_online.py','maintenance/verify_android_display_online.py')):
    s=pattern.sub(lambda m:changes[m[0]],(ROOT/'work/scripts'/old).read_text(encoding='utf-8'))
    (ROOT/'work/scripts'/new).write_text(s,encoding='utf-8')
print('Prepared Windows 0.3.20 / Android 0.5.17 (517)')
