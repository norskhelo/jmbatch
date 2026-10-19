"""Prepare the download-cover refresh fix and version-specific release recipes."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.24 / Android 0.6.4 — 下载列表封面刷新修复

## 修复内容

- Android 下载列表滚出屏幕后，再滚回时立即复用仍在内存缓存中的封面，不再等待下一次后台轮询后才显示。
- Android 下载进度及定时刷新不再重复设置同一张封面，减少反复刷新和闪烁；离屏仍释放行内图片引用，保留原有有界缓存。
- 双端在下载完成清理临时图片、切换至最终成品或短暂读取失败时保留已显示的有效封面，新的封面成功读取后再替换。
- 切换任务或首个所选章节时清除旧封面，丢弃过期后台结果，避免旧请求覆盖新任务；第一页就绪、修复或变更后仍自动刷新。
- 封面继续使用本地图片和现有缩略图缓存，不增加网站图片请求，不改变下载文件、断点续传或保存结构。

## 版本与验证

- Windows 0.3.23 → 0.3.24；Android 0.6.3 → 0.6.4（versionCode 604），保留原包名、签名证书和更新公钥。
- 验证连续进度刷新、滚出滚回、离屏加载完成、清理交接、首图修复、过期回调与移除任务，执行双端回归、构建和签名核验。
- Android 使用 Android 10/15 框架及隔离测试数据验证，未连接真机。
'''
folder = ROOT / 'work/release-0324-064'
folder.mkdir(exist_ok=True)
(folder/'release-notes.md').write_text(notes,encoding='utf-8')
p=ROOT/'CHANGELOG.md';s=p.read_text(encoding='utf-8')
if not s.startswith(notes):p.write_text(notes+'\n'+s,encoding='utf-8')
for name in ('work/jmbatch/core.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java','work/jmbatch-android/app/src/main/AndroidManifest.xml','work/jmbatch-android/app/build.gradle'):
    p=ROOT/name
    s=p.read_text(encoding='utf-8').replace('0.3.23','0.3.24').replace('0.6.3','0.6.4').replace('versionCode 603','versionCode 604').replace('versionCode="603"','versionCode="604"')
    p.write_text(s,encoding='utf-8')
plain=re.sub(r'(?m)^#{1,6} ','',notes).replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p=ROOT/name
    s=re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$',lambda m:m[1]+json.dumps(plain,ensure_ascii=False)+(';' if p.suffix=='.java' else ''),p.read_text(encoding='utf-8'))
    p.write_text(s,encoding='utf-8')
for name,version in (('work/jmbatch/README.txt','0.3.24'),('work/jmbatch-android/README.txt','0.6.4')):
    p=ROOT/name
    s=re.split(r'\n(?:Windows \d+\.\d+\.\d+ / Android \d+\.\d+\.\d+|Android \d+\.\d+\.\d+) — ',p.read_text(encoding='utf-8'),maxsplit=1)[0].rstrip()+'\n'
    s=re.sub(r'^JM Batch [\d.]+','JM Batch '+version,s).replace('0.3.23','0.3.24').replace('0.6.3','0.6.4')
    p.write_text(s+'\n'+plain,encoding='utf-8')
p=ROOT/'README.md';s=p.read_text(encoding='utf-8')
s=s.replace('0.3.23','0.3.24').replace('0.6.3','0.6.4').replace('versionCode 603','versionCode 604')
s=s.replace('双端漫画库新增收藏夹，支持批量分类和夹内漫画封面预览。','修复下载列表封面反复刷新，滚回列表优先复用缓存，完成清理时保留已显示封面。')
p.write_text(s,encoding='utf-8')
replacements={'0.3.23':'0.3.24','0.6.3':'0.6.4','0323-063':'0324-064','<= 603':'<= 604','漫画库收藏夹':'下载列表封面刷新修复'}
pattern=re.compile('|'.join(map(re.escape,replacements)))
for name in ('prepare_publication','publish'):
    p=ROOT/f'work/scripts/release/{name}_0323_063.py'
    (p.parent/f'{name}_0324_064.py').write_text(pattern.sub(lambda m:replacements[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
p=ROOT/'work/scripts/release/verify_collections_commit.py'
(p.parent/'verify_download_cover_fix_commit.py').write_text(p.read_text(encoding='utf-8').replace('collections-0323-063-complete','download-cover-fix-0324-064-complete'),encoding='utf-8')
p=ROOT/'work/scripts/maintenance/verify_collections_online.py'
replacements={'0.3.23':'0.3.24','0.3.22':'0.3.23','0.6.3':'0.6.4','0.6.2':'0.6.3','0323-063':'0324-064','collections-':'download-cover-fix-', 'LiveCollectionsUpdate':'LiveDownloadCoverFixUpdate','漫画库收藏夹':'下载列表封面刷新修复','36-release':'37-release','!=36':'!=37','full_history_versions=36':'full_history_versions=37'}
pattern=re.compile('|'.join(map(re.escape,sorted(replacements,key=len,reverse=True))))
(p.parent/'verify_download_cover_fix_online.py').write_text(pattern.sub(lambda m:replacements[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
print('Prepared Windows 0.3.24 / Android 0.6.4 (604) and matching release recipes')
