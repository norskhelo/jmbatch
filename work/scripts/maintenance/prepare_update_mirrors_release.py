"""Prepare the dual-platform update download mirror release and matching recipes."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[3]
notes = '''# Windows 0.3.13 / Android 0.5.7 — 应用内更新下载自动切换镜像

## 更新下载

- 双端下载更新清单、清单签名和安装包时，先使用 GitHub；连接失败、超时、HTTP 错误、返回网页或响应不完整时，依次尝试 GHFast、GH-Proxy。
- 下载进度显示当前线路。切换线路时重新下载当前文件，清除上一次不完整内容并重置进度；三条线路均失败后明确提示重试。
- 继续使用原更新公钥验证 RSA-SHA256 签名，核对仓库、版本、发布标签、文件名、大小与 SHA-256；Android 保留 APK 证书校验。签名或摘要不匹配会阻止安装。
- 取消下载或本地写入失败不会触发镜像重试。镜像仅接收公开 GitHub Release 附件地址，保留 HTTPS 校验与重定向限制。
- 版本查询仍使用 GitHub API；本次新增的是更新文件下载的镜像回退。旧版尚未具备此功能，升级到本版后生效。

## 版本与验证

- Windows 0.3.12 → 0.3.13；Android 0.5.6 → 0.5.7（versionCode 507），沿用包名、APK 原签名证书与更新公钥。
- 验证直连成功、两级回退、部分下载、HTTP 错误、取消、磁盘错误、重定向限制、签名及摘要篡改；执行 Windows 回归与源码/冻结成品自检、Android 宿主测试与签名构建。
- 未连接 Android 真机，宿主测试和编译不代表手机实测；第三方镜像可用性仍取决于当前网络。
'''
folder = root / 'work/release-0313-057'; folder.mkdir(exist_ok=True)
(folder / 'release-notes.md').write_text(notes, encoding='utf-8')
p = root / 'CHANGELOG.md'; text = p.read_text(encoding='utf-8')
if not text.startswith(notes): p.write_text(notes + '\n' + text, encoding='utf-8')
for name in ('work/jmbatch/core.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java', 'work/jmbatch-android/app/src/main/AndroidManifest.xml', 'work/jmbatch-android/app/build.gradle'):
    p = root / name
    text = p.read_text(encoding='utf-8').replace('0.3.12', '0.3.13').replace('0.5.6', '0.5.7').replace('versionCode 506', 'versionCode 507').replace('versionCode="506"', 'versionCode="507"')
    p.write_text(text, encoding='utf-8')
plain = notes.replace('## ', '').replace('# ', '').replace('- ', '• ')
for name in ('work/jmbatch/updates.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    p = root / name
    text = re.sub(r'(?m)^(\s*(?:private static final String )?CURRENT_NOTES\s*=).*$', lambda m: m[1] + json.dumps(plain, ensure_ascii=False) + (';' if name.endswith('.java') else ''), p.read_text(encoding='utf-8'))
    p.write_text(text, encoding='utf-8')
for name in ('README.md', 'work/jmbatch/README.txt', 'work/jmbatch-android/README.txt'):
    p = root / name; text = p.read_text(encoding='utf-8')
    if name != 'README.md': text = re.split(r'\nWindows 0\.3\.(?:12|13) / Android 0\.5\.(?:6|7) — ', text)[0].rstrip() + '\n'
    text = text.replace('0.3.12', '0.3.13').replace('0.5.6', '0.5.7').replace('versionCode 506', 'versionCode 507')
    text = text.replace('本版上下滚动阅读的相邻图片无间隔直接相接，页码保留在状态栏。', '本版应用内更新下载在 GitHub 失败后自动尝试 GHFast、GH-Proxy，保留签名和 SHA-256 校验。')
    text = text.replace('镜像用于手动下载，应用内更新仓库仍填写', '镜像同时用于手动下载及本版应用内更新文件下载的自动回退，版本查询仍使用 GitHub API，应用内更新仓库填写')
    text = text.replace('安装包下载（2026-10-16）', '安装包下载（2026-10-17）')
    if name != 'README.md': text += '\n' + plain
    p.write_text(text, encoding='utf-8')
replacements = {
    '0.3.12': '0.3.13', '0.3.11': '0.3.12', '0.5.6': '0.5.7', '0.5.5': '0.5.6',
    '0312-056': '0313-057', '0312_056': '0313_057', 'scroll-056': 'update-mirrors-057',
    'scroll-windows-verified': 'update-mirrors-windows-verified', 'scroll-android-verified': 'update-mirrors-android-verified',
    'scroll-0312-056': 'update-mirrors-0313-057', 'prepare_scroll_release': 'prepare_update_mirrors_release',
    'verify_scroll_online': 'verify_update_mirrors_online', 'verify_android_scroll_online': 'verify_android_update_mirrors_online',
    'audit_scroll_release': 'audit_update_mirrors_release', 'verify_scroll_commit': 'verify_update_mirrors_commit',
    '上下滚动无缝阅读': '应用内更新下载自动切换镜像', '<= 506': '<= 507', "versionCode='506'": "versionCode='507'",
    '==36': '==37', '== 36': '== 37', 'checks=36': 'checks=37', '179': '190',
    'range(1,13)': 'range(1,14)', '!=16': '!=17', '16-release': '17-release', 'full_history_versions=16': 'full_history_versions=17'
}
pattern = re.compile('|'.join(re.escape(k) for k in sorted(replacements, key=len, reverse=True)))
for old, new in (
    ('release/prepare_publication_0312_056.py', 'release/prepare_publication_0313_057.py'),
    ('release/publish_0312_056.py', 'release/publish_0313_057.py'),
    ('release/audit_scroll_release.py', 'release/audit_update_mirrors_release.py'),
    ('release/verify_scroll_commit.py', 'release/verify_update_mirrors_commit.py'),
    ('maintenance/verify_scroll_online.py', 'maintenance/verify_update_mirrors_online.py'),
    ('maintenance/verify_android_scroll_online.py', 'maintenance/verify_android_update_mirrors_online.py')
):
    text = pattern.sub(lambda m: replacements[m[0]], (root / 'work/scripts' / old).read_text(encoding='utf-8'))
    (root / 'work/scripts' / new).write_text(text, encoding='utf-8')
print('Prepared Windows 0.3.13 / Android 0.5.7, versionCode 507')
