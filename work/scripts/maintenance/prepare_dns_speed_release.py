"""Promote the authorized Android 0.6.2 speed fix to formal release sources."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'work/jmbatch-android'
path = ROOT / 'work/release-android-062/release-notes.md'
old_notes = path.read_text(encoding='utf-8')
assert '（本地验证版）' in old_notes
notes = old_notes.replace('（本地验证版）', '').replace('本地交付，尚未推送或发布。', '')
notes += '\n## 验证范围\n\n- 1624 项宿主检查、96 组布局场景和 71 项 Android 框架用例通过，包括 14 项 TLS 专项，覆盖连接复用、跨域隔离、证书拒绝及独立读取超时。\n- 保留原包名、APK 签名和更新公钥，可覆盖安装并继续原任务；没有连接手机，尚未验证 Redmi K70 Pro 的实际移动网络吞吐。\n'
path.write_text(notes, encoding='utf-8')
path = ROOT / 'CHANGELOG.md'
text = path.read_text(encoding='utf-8')
assert text.startswith(old_notes)
path.write_text(notes + text[len(old_notes):], encoding='utf-8')
plain = re.sub(r'(?m)^#{1,6} ', '', notes).replace('- ', '• ')
path = APP / 'app/src/main/java/app/jmbatch/android/GithubUpdates.java'
text, count = re.subn(r'private static final String CURRENT_NOTES=.*?;', lambda m: 'private static final String CURRENT_NOTES=' + json.dumps(plain, ensure_ascii=False) + ';', path.read_text(encoding='utf-8'), count=1)
assert count == 1
path.write_text(text, encoding='utf-8')
path = ROOT / 'README.md'
text = path.read_text(encoding='utf-8')
old = '当前本地源码：**Windows 0.3.22 / Android 0.6.2（versionCode 602，本地验证版）**。Android 优化备用 DNS 路径的连接复用、有效地址记忆和图片读取超时。下方在线下载仍为正式版 Android 0.6.1。'
assert old in text
text = text.replace(old, '当前源码及正式版本：**Windows 0.3.22 / Android 0.6.2（versionCode 602）**。Android 修复备用 DNS 图片下载中的重复失败连接、HTTPS 复用和过短读取超时，优先使用成功地址。安装包、更新日志与镜像入口见下方。')
path.write_text(text.replace('0.6.1', '0.6.2'), encoding='utf-8')
path = APP / 'README.txt'
text = path.read_text(encoding='utf-8').replace('Android 本地验证版使用说明', 'Android 使用说明', 1)
old = '本地安装包：本目录 JMBatch-0.6.2-Android.apk，可覆盖安装。\n下列链接为历史正式版 0.6.1，不含本轮速度优化。\n历史正式包下载（2026-10-18）'
assert old in text
text = text.replace(old, '安装包下载（2026-10-19）').replace('0.6.1', '0.6.2')
path.write_text(text[:text.index('Android 0.6.2 — 备用 DNS 图片下载提速')] + plain, encoding='utf-8')

# Preserve all completed recipes; create one independently reviewable release recipe.
release = ROOT / 'work/scripts/release'
text = (release / 'prepare_publication_android_061.py').read_text(encoding='utf-8')
(release / 'prepare_publication_android_062.py').write_text(text.replace('0.6.1', '0.6.2').replace('android-061', 'android-062'), encoding='utf-8')
text = (release / 'publish_android_061.py').read_text(encoding='utf-8')
mapping = {'0.6.1': '0.6.2', '0.6.0': '0.6.1', '601': '602', '600': '601'}
text = re.sub(r'0\.6\.[01]|\b60[01]\b', lambda m: mapping[m[0]], text).replace('全零 DNS 自动备用解析', '备用 DNS 图片下载提速')
(release / 'publish_android_062.py').write_text(text, encoding='utf-8')
text = (release / 'verify_dns_fallback_commit.py').read_text(encoding='utf-8')
(release / 'verify_dns_speed_commit.py').write_text(text.replace('0.6.1', '0.6.2').replace('dns-fallback-061', 'dns-speed-062'), encoding='utf-8')
path = ROOT / 'work/scripts/maintenance/verify_dns_fallback_online.py'
text = re.sub(r'0\.6\.[01]', lambda m: mapping[m[0]], path.read_text(encoding='utf-8'))
text = text.replace('dns-fallback-061', 'dns-speed-062').replace('android-061', 'android-062').replace('LiveDnsFallbackUpdate', 'LiveDnsSpeedUpdate').replace('全零 DNS 自动备用解析', '备用 DNS 图片下载提速').replace('34', '35')
(path.parent / 'verify_dns_speed_online.py').write_text(text, encoding='utf-8')
text = (path.parent / 'audit_dns_fallback_release.py').read_text(encoding='utf-8')
for old, new in [('0.6.1', '0.6.2'), ('601', '602'), ('android-061', 'android-062'), ('_061', '_062'),
                 ('dns-fallback-061', 'dns-speed-062'), ('dns_fallback', 'dns_speed'),
                 ('FallbackDnsTest: 51', 'FallbackDnsTest: 57'), ('JmApiFallbackTest: 82', 'JmApiFallbackTest: 158'),
                 ('Tests run: 63', 'Tests run: 71'), ('host == 1542', 'host == 1624'),
                 ('fallback_dns_checks=51', 'fallback_dns_checks=57'), ('fallback_transport_checks=82', 'fallback_transport_checks=158'),
                 ('runtime_tests=63', 'runtime_tests=71'), ('tls_runtime_tests=6', 'tls_runtime_tests=14')]:
    text = text.replace(old, new)
(path.parent / 'audit_dns_speed_release.py').write_text(text, encoding='utf-8')

path = ROOT / '.agents/skills/jmbatch-maintenance/SKILL.md'
text = path.read_text(encoding='utf-8')
marker = '## 更新范围与发布权限\n'
assert marker in text
record = '\n2026-10-19 备用 DNS 下载速度修复的后续发布授权：用户明确要求“推送并发布 Android 0.6.2，把备用 DNS 下载速度修复加入正式版”，覆盖前述本地交付范围。继续使用 0.6.2/602、原包名、APK 签名和更新公钥，Windows 保持 0.3.22；将验证版文案转为正式版，同版源码/日志推送后发布五项正式附件，并核验公开更新选择、清单签名和 APK 摘要。原本地包归档到 work/builds/android-0.6.2/local-verification-backup，不把框架连接数收益视为手机吞吐实测。发布完成后补充结果。\n'
path.write_text(text.replace(marker, marker + record, 1), encoding='utf-8')
print('Prepared Android 0.6.2 formal notes, links and version-specific publication recipes.')
