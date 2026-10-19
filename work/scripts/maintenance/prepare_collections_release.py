"""Prepare matching source versions, release notes and publication recipes."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.23 / Android 0.6.3 — 漫画库收藏夹

## 更新内容

- 漫画库现在也是默认收藏夹。旧漫画和新下载仍在漫画库根层显示；自建收藏夹直接出现在原漫画列表或四列平铺区域，与漫画共用位置。
- 收藏夹卡片显示名称、漫画数量，并以夹内最近加入漫画的最多四张本地封面组成预览；空收藏夹和无法读取的封面显示占位。
- 支持新建、重命名收藏夹；长按漫画或进入“批量处理”，勾选后点击“移入收藏夹”，也可选择“漫画库”移回默认位置。每本漫画归属一个收藏夹，分类不移动实际文件。
- 点击收藏夹查看内容，点击漫画开始阅读；“返回漫画库”回到默认收藏夹。Android 返回键先退出批量处理，再返回漫画库；阅读返回或重建界面保留所在收藏夹。
- “管理收藏夹”可重命名或删除收藏夹。删除前确认，夹内漫画回到漫画库，保留漫画文件、星标、书签和阅读位置。默认漫画库不能重命名或删除。
- 原星标收藏继续保留。“仅显示收藏”可筛选星标漫画；根层搜索也能找到名称匹配或含匹配漫画的收藏夹。移动、扫描、下载记录刷新、修改星标和删除章节均保留分类。
- 收藏夹与漫画记录一起原子保存，保存失败保留原状态；封面复用现有有界后台加载与本地缓存，不增加网站请求。

## 版本与验证

- Windows 0.3.22 → 0.3.23；Android 0.6.2 → 0.6.3（versionCode 603），保留原 Android 包名、签名证书与更新公钥。
- 验证旧记录兼容、创建/移动/重命名/删除、搜索与星标、保存失败回滚、封面预览上限和真实界面导航；执行双端回归、自检、构建及签名核验。
- Android 使用 Android 10/15 框架和隔离演示数据验证，未连接真机。效果图使用演示漫画，不读取个人漫画。
'''
folder = ROOT / 'work/release-0323-063'
folder.mkdir(exist_ok=True)
(folder / 'release-notes.md').write_text(notes, encoding='utf-8')
p = ROOT / 'CHANGELOG.md'
s = p.read_text(encoding='utf-8')
if not s.startswith(notes): p.write_text(notes + '\n' + s, encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java', 'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p = ROOT / name
    s = p.read_text(encoding='utf-8').replace('0.3.22', '0.3.23').replace('0.6.2', '0.6.3').replace('versionCode 602', 'versionCode 603').replace('versionCode="602"', 'versionCode="603"')
    p.write_text(s, encoding='utf-8')
plain = re.sub(r'(?m)^#{1,6} ', '', notes).replace('- ', '• ')
for name in ('work/jmbatch/updates.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p = ROOT / name
    s = re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$', lambda m: m[1]+json.dumps(plain, ensure_ascii=False)+(';' if p.suffix=='.java' else ''), p.read_text(encoding='utf-8'))
    p.write_text(s, encoding='utf-8')
tag = 'release-0.3.23-0.6.3'
for name, version in (('work/jmbatch/README.txt', '0.3.23'), ('work/jmbatch-android/README.txt', '0.6.3')):
    p = ROOT / name
    s = re.split(r'\n(?:Windows \d+\.\d+\.\d+ / Android \d+\.\d+\.\d+|Android \d+\.\d+\.\d+) — ', p.read_text(encoding='utf-8'), maxsplit=1)[0].rstrip()+'\n'
    s = re.sub(r'^JM Batch [\d.]+', 'JM Batch '+version, s)
    s = re.sub(r'release-(?:0\.3\.22-0\.5\.21|android-0\.6\.2)', tag, s)
    s = s.replace('JMBatch-0.3.22-Windows', 'JMBatch-0.3.23-Windows').replace('JMBatch-0.6.2-Android', 'JMBatch-0.6.3-Android')
    p.write_text(s+'\n'+plain, encoding='utf-8')
p = ROOT / 'README.md'
s = p.read_text(encoding='utf-8')
head, tail = s.split('## 显示方式', 1)
head = re.sub(r'(?:release|SHA256-release)-(?:0\.3\.22-0\.5\.21|android-0\.6\.2)', lambda m: ('SHA256-' if m[0].startswith('SHA256-') else '')+tag, head)
head = head.replace('0.3.22', '0.3.23').replace('0.6.2', '0.6.3').replace('versionCode 602', 'versionCode 603')
head = head.replace('Android 修复备用 DNS 图片下载中的重复失败连接、HTTPS 复用和过短读取超时，优先使用成功地址。', '双端漫画库新增收藏夹，支持批量分类和夹内漫画封面预览。')
section = '## 收藏夹\n\n漫画库是默认收藏夹，旧漫画和新下载默认显示在这里。点击“新建收藏夹”，收藏夹卡片就会与漫画共用原列表/平铺区域，显示最多四本夹内漫画的封面及总数量。长按漫画或进入“批量处理”，勾选后“移入收藏夹”；选择“漫画库”即可移回。分类不移动实际文件，每本漫画归属一个收藏夹，原星标收藏独立保留。\n\n点击收藏夹查看内容，通过“返回漫画库”返回。使用“管理收藏夹”重命名或删除；删除收藏夹仅将漫画归回默认库，保留文件、星标、书签和阅读位置。根层搜索可找到名称匹配或包含匹配漫画的收藏夹。\n\n'
p.write_text(head+section+'## 显示方式'+tail, encoding='utf-8')
changes = {'0.3.22':'0.3.23','0.5.21':'0.6.3','0322-0521':'0323-063','<= 521':'<= 603','漫画库删除章节':'漫画库收藏夹'}
pattern = re.compile('|'.join(map(re.escape, changes)))
for name in ('prepare_publication', 'publish'):
    p = ROOT / f'work/scripts/release/{name}_0322_0521.py'
    value = pattern.sub(lambda m: changes[m[0]], p.read_text(encoding='utf-8'))
    if name == 'publish':
        value = value.replace('    released = {}', '    run(["git", "merge-base", "--is-ancestor", parent, "HEAD"])\n    released = {}')
    (p.parent / f'{name}_0323_063.py').write_text(value, encoding='utf-8')
print('Prepared Windows 0.3.23 / Android 0.6.3 (603)')
