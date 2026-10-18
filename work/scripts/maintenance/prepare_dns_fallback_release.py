"""Promote the authorized Android 0.6.1 local build to formal release sources."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'work/jmbatch-android'
notes_path = ROOT / 'work/release-android-061/release-notes.md'
old_notes = notes_path.read_text(encoding='utf-8')
assert '（本地验证版）' in old_notes
notes = old_notes.replace('（本地验证版）', '').replace('本地交付，尚未推送或发布到 GitHub。', '')
notes += '\n## 验证范围\n\n- 1542 项宿主检查、96 组布局场景和 63 项 Android 框架用例通过，包括 Android 10/15 下的备用连接、原域名 SNI/Host 和证书拒绝测试。\n- Windows 本机对阿里、DNSPod 的 8 项公开 DNS 查询通过；没有连接手机，以上不代表 Redmi K70 Pro 的实际移动网络已恢复。\n'
notes_path.write_text(notes, encoding='utf-8')
path = ROOT / 'CHANGELOG.md'
text = path.read_text(encoding='utf-8')
assert text.startswith(old_notes)
path.write_text(notes + text[len(old_notes):], encoding='utf-8')
plain = re.sub(r'(?m)^#{1,6} ', '', notes).replace('- ', '• ')
path = APP / 'app/src/main/java/app/jmbatch/android/GithubUpdates.java'
text = path.read_text(encoding='utf-8')
text, count = re.subn(r'private static final String CURRENT_NOTES=.*?;', lambda m: 'private static final String CURRENT_NOTES=' + json.dumps(plain, ensure_ascii=False) + ';', text, count=1)
assert count == 1
path.write_text(text, encoding='utf-8')
path = ROOT / 'README.md'
text = path.read_text(encoding='utf-8')
old = '当前本地源码：**Windows 0.3.22 / Android 0.6.1（versionCode 601，本地验证版，尚未发布）**。Android 新增全零 DNS 自动备用解析，保留 HTTPS 验证和代理策略，并在内置诊断中比较系统与备用路径。下方在线下载仍为已发布的 Android 0.6.0。'
assert old in text
text = text.replace(old, '当前源码及正式版本：**Windows 0.3.22 / Android 0.6.1（versionCode 601）**。Android 新增全零 DNS 自动备用解析，保留 HTTPS 验证和代理策略，并在内置诊断中比较系统与备用路径。安装包、更新日志与镜像入口见下方。')
text = text.replace('Android 0.6.0', 'Android 0.6.1').replace('release-android-0.6.0', 'release-android-0.6.1').replace('JMBatch-0.6.0-Android.apk', 'JMBatch-0.6.1-Android.apk')
path.write_text(text, encoding='utf-8')
path = APP / 'README.txt'
text = path.read_text(encoding='utf-8')
text = text.replace('Android 本地验证版使用说明', 'Android 使用说明', 1)
text = text.replace('本地安装包：本目录 JMBatch-0.6.1-Android.apk，可覆盖安装。\n下列在线地址为历史正式版 0.6.0，不含本次备用 DNS 功能。\n历史正式包下载（2026-10-18）', '安装包下载（2026-10-18）')
text = text.replace('release-android-0.6.0', 'release-android-0.6.1').replace('JMBatch-0.6.0-Android.apk', 'JMBatch-0.6.1-Android.apk')
text = text[:text.index('Android 0.6.1 — 全零 DNS 自动备用解析')] + plain
path.write_text(text, encoding='utf-8')

# Derive a new version-specific recipe; leave completed release recipes intact.
release = ROOT / 'work/scripts/release'
text = (release / 'prepare_publication_android_060.py').read_text(encoding='utf-8')
(release / 'prepare_publication_android_061.py').write_text(text.replace('0.6.0', '0.6.1').replace('android-060', 'android-061'), encoding='utf-8')
text = (release / 'publish_android_060.py').read_text(encoding='utf-8')
text = text.replace('0.6.0', '0.6.1').replace('0.5.22', '0.6.0').replace('600', '601').replace('522', '600').replace('权限检测与申请', '全零 DNS 自动备用解析')
(release / 'publish_android_061.py').write_text(text, encoding='utf-8')
text = (release / 'verify_permissions_commit.py').read_text(encoding='utf-8')
text = text.replace('0.6.0', '0.6.1').replace('permissions-060', 'dns-fallback-061-release')
(release / 'verify_dns_fallback_commit.py').write_text(text, encoding='utf-8')
text = (ROOT / 'work/scripts/maintenance/verify_permissions_online.py').read_text(encoding='utf-8')
text = text.replace('0.6.0', '0.6.1').replace('0.5.22', '0.6.0').replace('permissions-060', 'dns-fallback-061').replace('android-060', 'android-061').replace('LivePermissionsUpdate', 'LiveDnsFallbackUpdate').replace('权限检测与申请', '全零 DNS 自动备用解析').replace('33', '34')
(ROOT / 'work/scripts/maintenance/verify_dns_fallback_online.py').write_text(text, encoding='utf-8')

path = ROOT / '.agents/skills/jmbatch-maintenance/SKILL.md'
text = path.read_text(encoding='utf-8')
old = '按持续 Android 上下文处理单端，已完成本地 0.6.1/601 构建与交付，Windows 保持 0.3.22；本次未要求新一轮推送/正式发布，未推送或发布。'
assert old in text
text = text.replace(old, '按持续 Android 上下文处理单端，首轮完成本地 0.6.1/601 构建与交付，Windows 保持 0.3.22；用户随后明确要求“推送并发布 Android 0.6.1，把备用 DNS 功能加入正式版”，覆盖首轮本地交付范围。正式版继续使用 0.6.1/601、原包名/签名/更新公钥，推送同版源码和日志，发布正式 Release 并核验公开更新入口；发布完成后补充结果。', 1)
path.write_text(text, encoding='utf-8')
print('Prepared Android 0.6.1 formal notes, links, and version-specific publication recipes.')
