"""Generate version-specific verification recipes from the established checks."""
from pathlib import Path
root=Path(__file__).resolve().parents[3]
p=root/'work/scripts/release/audit_cleanup_release.py'
s=p.read_text(encoding='utf-8').replace('0.3.9','0.3.10').replace('0.4.9','0.5.4').replace('039-049','0310-054')
s=s.replace('cleanup-windows-complete','cancel-cleanup-windows-complete').replace('cleanup-android-verified','cancel-cleanup-android-verified')
s=s.replace('prepare_cleanup_release','prepare_cancel_cleanup_release').replace('verify_cleanup_online','verify_cancel_cleanup_online').replace('audit_cleanup_release','audit_cancel_cleanup_release').replace('verify_cleanup_commit','verify_cancel_cleanup_commit')
s=s.replace("'work/scripts/release/prepare_publication_039_049.py','work/scripts/release/publish_039_049.py'", "'work/scripts/release/prepare_publication_0310_054.py','work/scripts/release/publish_0310_054.py','work/scripts/release/make_cancel_cleanup_checks.py'")
s=s.replace('==32','==33').replace('checks=32','checks=33').replace('Ran 158 tests','Ran 167 tests').replace('windows_unit_tests=158','windows_unit_tests=167').replace('CacheCleanupTest: 42','CacheCleanupTest: 50')
s=s.replace("('0.4.8','0.5.4')","('0.5.3','0.5.4')").replace("versionCode='409'","versionCode='504'")
s=s.replace("b'Lapp/jmbatch/android/CacheCleanup;',b'Lapp/jmbatch/android/CleanupScreen;',b'cleanupNotice',b'cleanupNote',b'toRealPath'", "b'Lapp/jmbatch/android/CancelledTaskCleanup;',b'Lapp/jmbatch/android/WorkerDrain;',b'discardRequested',b'cleanupUri',b'toRealPath'")
s=s.replace("assert 'CacheCleanupTest: 50 checks passed' in alog", "assert 'CacheCleanupTest: 50 checks passed' in alog\nassert 'CancelServiceTest: 38 checks passed' in alog")
(p.parent/'audit_cancel_cleanup_release.py').write_text(s,encoding='utf-8')
p=root/'work/scripts/release/verify_cleanup_commit.py'
s=p.read_text(encoding='utf-8').replace('cleanup-039-049','cleanup-0310-054')
(p.parent/'verify_cancel_cleanup_commit.py').write_text(s,encoding='utf-8')
p=root/'work/scripts/maintenance/verify_cleanup_online.py'
s=p.read_text(encoding='utf-8').replace('cleanup-039-049','cancel-cleanup-0310-054').replace('0.3.9','0.3.10').replace('0.3.8','0.3.9').replace('0.4.9','0.5.4').replace('release-039-049','release-0310-054').replace('range(1,10)','range(1,11)').replace('手动清理下载缓存与自动清理提示','取消任务后自动删除文件与记录')
(p.parent/'verify_cancel_cleanup_online.py').write_text(s,encoding='utf-8')
# Also validate the live Android history using the actual Java production rules.
p=root/'work/scripts/maintenance/verify_android_cancel_online.py'
s=p.read_text(encoding='utf-8').replace('cancel-053','cancel-cleanup-054').replace('0.5.3','0.5.4').replace('0.5.2','0.5.3').replace('release-android-0.5.4','release-0.3.10-0.5.4').replace('release-android-053','release-0310-054').replace('下载取消响应优化','取消任务后自动删除文件与记录').replace('!=13','!=14').replace('13-release','14-release').replace('full_history_versions=13','full_history_versions=14')
s=s.replace("assert fetch_release(DEFAULT_REPOSITORY,'0.3.9') is None", "assert fetch_release(DEFAULT_REPOSITORY,'0.3.9')['version']=='0.3.10'").replace("assert fetch_bulletin(DEFAULT_REPOSITORY,'0.3.9')['version']=='0.3.9'", "assert fetch_bulletin(DEFAULT_REPOSITORY,'0.3.10')['version']=='0.3.10'").replace("windows_unchanged='0.3.9'", "windows='0.3.10'")
(p.parent/'verify_android_cancel_cleanup_online.py').write_text(s,encoding='utf-8')
# Include this separate platform check in the source/release allowlist.
p=root/'work/scripts/release/audit_cancel_cleanup_release.py'
s=p.read_text(encoding='utf-8').replace("'work/scripts/maintenance/verify_cancel_cleanup_online.py',", "'work/scripts/maintenance/verify_cancel_cleanup_online.py','work/scripts/maintenance/verify_android_cancel_cleanup_online.py',")
p.write_text(s,encoding='utf-8')
# Remove the old behavior summary; the current cancellation section follows it.
p=root/'README.md';s=p.read_text(encoding='utf-8');s='\n'.join(line for line in s.split('\n') if not line.startswith('Android 0.5.4：取消和暂停改为后台'))
p.write_text(s,encoding='utf-8')
print('Prepared source, delivery and public update verification recipes')
