"""Prepare the paired download-list / four-column library release."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.21 / Android 0.5.19 — 下载列表与漫画库四列平铺

## 显示调整

- 下载页移除平铺显示及显示方式切换，统一使用列表。升级前保存的下载平铺设置不再生效，原任务、下载进度及操作保留。
- 漫画库继续支持“列表 / 平铺”切换；平铺固定每行 4 本，卡片宽度随窗口或屏幕调整，末行不足 4 本时按实际数量显示。
- 漫画库保留搜索、收藏筛选、批量选择和浏览位置，以及 Android 触摸模式下进入漫画库的闪退修复。

## 版本与验证

- Windows 0.3.20 → 0.3.21；Android 0.5.18 → 0.5.19（versionCode 519）。沿用原 Android 包名、APK 签名证书及更新公钥。
- 验证下载列表、漫画库四列布局、显示切换与选择保留；执行 Windows 回归及源码/成品自检、Android 宿主回归、Android 10 触摸模式框架回归及原签名构建。
- Android 框架回归覆盖窄屏、大字号及横屏布局；未连接 Android 真机，手机视觉和手势效果仍需设备验证。
'''
folder = ROOT/'work/release-0321-0519'
folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes, encoding='utf-8')
p = ROOT/'CHANGELOG.md'
s = p.read_text(encoding='utf-8')
if not s.startswith(notes): p.write_text(notes+'\n'+s, encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p=ROOT/name
    s=p.read_text(encoding='utf-8').replace('0.3.20','0.3.21').replace('0.5.18','0.5.19').replace('versionCode 518','versionCode 519').replace('versionCode="518"','versionCode="519"')
    p.write_text(s,encoding='utf-8')
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name
    s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'))
    p.write_text(s,encoding='utf-8')
for name,number in (('work/jmbatch/README.txt','0.3.21'),('work/jmbatch-android/README.txt','0.5.19')):
    p=ROOT/name;s=p.read_text(encoding='utf-8')
    s=re.split(r'\n(?:Windows 0\.3\.\d+ / Android 0\.5\.\d+|Android 0\.5\.\d+) — ',s,maxsplit=1)[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+','JM Batch '+number,s)
    s=re.sub(r'release-(?:0\.3\.\d+-0\.5\.\d+|android-0\.5\.\d+)','release-0.3.21-0.5.19',s)
    s=re.sub(r'JMBatch-0\.3\.\d+-Windows','JMBatch-0.3.21-Windows',s)
    s=re.sub(r'JMBatch-0\.5\.\d+-Android','JMBatch-0.5.19-Android',s)
    p.write_text(s+'\n'+plain,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8')
s=re.sub(r'release-(?:0\.3\.20-0\.5\.17|android-0\.5\.18)','release-0.3.21-0.5.19',s)
s=s.replace('SHA256-release-android-0.5.18.txt','SHA256-release-0.3.21-0.5.19.txt').replace('SHA256-release-0.3.20-0.5.17.txt','SHA256-release-0.3.21-0.5.19.txt')
s=s.replace('0.3.20','0.3.21').replace('0.5.18','0.5.19').replace('versionCode 518','versionCode 519')
s=s.replace('Android 修复点开漫画库立即闪退，保留列表/平铺切换、批量选择与浏览位置。','下载页统一列表显示，漫画库平铺固定每行 4 本，保留列表切换、批量选择与浏览位置。')
s=re.sub(r'(## 显示方式\n\n).*?(\n\n## 下载与导出)',r'\1下载页统一使用列表，旧版下载平铺设置不再生效。漫画库可选择“列表”或“平铺”，默认列表并记住选择；平铺固定每行 4 本，卡片宽度随窗口或屏幕调整。切换保留筛选、批量选择，并尽量保持当前浏览位置。封面继续复用缓存。\2',s,flags=re.S)
p.write_text(s,encoding='utf-8')
changes={'0.3.20':'0.3.21','0.3.19':'0.3.20','0.5.17':'0.5.19','0.5.16':'0.5.18',
         '0320-0517':'0321-0519','0320_0517':'0321_0519','display-0517':'four-columns-0519',
         'display':'four_columns','列表与平铺显示':'下载列表与漫画库四列平铺','<= 517':'<= 519',
         'range(1,21)':'range(1,22)','!=27':'!=29','27-release':'29-release','full_history_versions=27':'full_history_versions=29'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(changes,key=len,reverse=True)))
for old,new in (
    ('release/prepare_publication_0320_0517.py','release/prepare_publication_0321_0519.py'),
    ('release/publish_0320_0517.py','release/publish_0321_0519.py'),
    ('release/verify_display_commit.py','release/verify_four_columns_commit.py'),
    ('maintenance/verify_display_online.py','maintenance/verify_four_columns_online.py'),
    ('maintenance/verify_android_display_online.py','maintenance/verify_android_four_columns_online.py')):
    s=pattern.sub(lambda m:changes[m[0]],(ROOT/'work/scripts'/old).read_text(encoding='utf-8'))
    (ROOT/'work/scripts'/new).write_text(s,encoding='utf-8')
print('Prepared Windows 0.3.21 / Android 0.5.19 (519)')
