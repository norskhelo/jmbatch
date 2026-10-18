"""Prepare the explicitly requested paired persistent-cover release."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.19 / Android 0.5.15 — 漫画库封面缓存

## 封面加载

- Windows 与 Android 将首次成功读取的封面保存为小尺寸缩略图。关闭重开漫画库、切换页面或重启软件后优先复用，减少反复扫描图片目录、解析 PDF 或复制外部 ZIP。
- 新下载漫画在完成保存、清理临时图片前直接用首图预生成封面，首次进入漫画库即可调用；已完成漫画的下载列表与漫画库共用封面缓存。
- 已有漫画首次成功读取后自动建立缓存，无需重新下载漫画。封面处理不增加网站请求，也不会向漫画成品目录添加文件。
- 按原文件和首图可用的大小、修改时间识别变化；缓存损坏时自动重建。文件缺失或暂时无法读取时保留占位，不影响漫画库管理操作，缓存写入失败不影响下载。
- 缓存最多保留 128 MiB / 4096 项，超出时淘汰较久未使用的封面；移除漫画记录时清理对应缓存。清理应用数据或缓存被淘汰后，下一次读取会重新生成。

## 版本与验证

- Windows 0.3.18 → 0.3.19；Android 0.5.14 → 0.5.15（versionCode 515）。沿用原 Android 包名、APK 签名证书和更新公钥。
- Windows 验证覆盖 220 项回归、源码与打包程序各 41 项自检；Android 覆盖完整宿主回归、新增持久缓存和生产封面加载集成 53 项检查、完整编译及原签名构建。
- 未连接 Android 真机，手机实际加载速度与外部存储行为仍需设备验证；宿主测试结果不代表手机性能。
'''
folder = ROOT / 'work/release-0319-0515'
folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes, encoding='utf-8')
p = ROOT/'CHANGELOG.md'
s = p.read_text(encoding='utf-8')
if s.startswith('# 未发布 — 漫画库封面持久缓存'):
    s = s[s.index('# Windows 0.3.18 / Android 0.5.14 — '):]
if not s.startswith(notes):
    p.write_text(notes+'\n'+s, encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java',
             'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p = ROOT/name
    s = p.read_text(encoding='utf-8').replace('0.3.18','0.3.19').replace('0.5.14','0.5.15').replace('versionCode 514','versionCode 515').replace('versionCode="514"','versionCode="515"')
    p.write_text(s, encoding='utf-8')
plain = notes.replace('## ','').replace('# ','').replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name
    s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'))
    p.write_text(s,encoding='utf-8')
for name,version in (('work/jmbatch/README.txt','0.3.19'),('work/jmbatch-android/README.txt','0.5.15')):
    p=ROOT/name
    s=re.split(r'\nWindows 0\.3\.\d+ / Android 0\.5\.\d+ — ',p.read_text(encoding='utf-8'),maxsplit=1)[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+','JM Batch '+version,s)
    s=re.sub(r'release-0\.3\.\d+-0\.5\.\d+','release-0.3.19-0.5.15',s)
    s=re.sub(r'release-android-0\.5\.\d+','release-0.3.19-0.5.15',s)
    s=re.sub(r'JMBatch-0\.3\.\d+-Windows','JMBatch-0.3.19-Windows',s)
    s=re.sub(r'JMBatch-0\.5\.\d+-Android','JMBatch-0.5.15-Android',s)
    s=s.replace('安装包下载（2026-10-17）','安装包下载（2026-10-18）')
    s=s.replace('完成后从 PDF、ZIP 或文件夹成品读取。','完成后优先使用已保存的小尺寸封面，缺失时从 PDF、ZIP 或文件夹成品读取并缓存。')
    p.write_text(s+'\n'+plain,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8');header,body=s.split('## 下载与导出',1)
header=header.replace('0.3.18','0.3.19').replace('0.5.14','0.5.15').replace('versionCode 514','versionCode 515')
header=header.replace('进入阅读后保留漫画库页面，返回继续原来的搜索、筛选、滚动位置和批量选择。','封面首次生成后持久保存，进出漫画库或重启软件均可复用；新下载漫画自动预生成封面。')
body=body.replace('完成后从 PDF、ZIP 或文件夹成品读取。','完成后优先使用已保存的小尺寸封面，缺失时从 PDF、ZIP 或文件夹成品读取并缓存。漫画库首次成功读取后持久缓存封面，关闭重开及重启软件可复用；新下载漫画在清理临时图片前预生成，减少大文件重复读取。缓存总计最多 128 MiB / 4096 项，按可用文件元数据检查变化，损坏时重建，移除记录时清理。')
p.write_text(header+'## 下载与导出'+body,encoding='utf-8')

# Copy reviewed, version-specific workflows without rewriting their historical originals.
replacements={'0.3.18':'0.3.19','0.3.17':'0.3.18','0.5.14':'0.5.15','0.5.13':'0.5.14',
              '0318-0514':'0319-0515','0318_0514':'0319_0515','library-state-0514':'cover-cache-0515',
              'library_state':'cover_cache','阅读保留漫画库':'漫画库封面缓存','<= 514':'<= 515',
              'range(1,19)':'range(1,20)','!=24':'!=25','24-release':'25-release','full_history_versions=24':'full_history_versions=25'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True)))
for old,new in (
    ('release/prepare_publication_0318_0514.py','release/prepare_publication_0319_0515.py'),
    ('release/publish_0318_0514.py','release/publish_0319_0515.py'),
    ('release/verify_library_state_commit.py','release/verify_cover_cache_commit.py'),
    ('maintenance/verify_library_state_online.py','maintenance/verify_cover_cache_online.py'),
    ('maintenance/verify_android_library_state_online.py','maintenance/verify_android_cover_cache_online.py')):
    s=pattern.sub(lambda m:replacements[m[0]],(ROOT/'work/scripts'/old).read_text(encoding='utf-8'))
    (ROOT/'work/scripts'/new).write_text(s,encoding='utf-8')
print('Prepared Windows 0.3.19 / Android 0.5.15 (515)')
