"""Create this release's verification recipes from the established audited flow."""
from pathlib import Path

root=Path(__file__).resolve().parents[3]
release=root/'work/scripts/release';maintenance=root/'work/scripts/maintenance'
s=(release/'audit_cancel_cleanup_release.py').read_text(encoding='utf-8')
for old,new in [('0.3.10','0.3.11'),('0.5.4','0.5.5'),('0.5.3','0.5.4'),('0310-054','0311-055'),
                ('cleanup-0311-055-complete','paging-0311-055-complete'),
                ('cancel-cleanup-windows-complete','paging-windows-final'),('cancel-cleanup-android-verified','paging-android-final'),
                ('prepare_cancel_cleanup_release','prepare_paging_release'),('verify_cancel_cleanup_online','verify_paging_online'),
                ('verify_android_cancel_cleanup_online','verify_android_paging_online'),('audit_cancel_cleanup_release','audit_paging_release'),
                ('verify_cancel_cleanup_commit','verify_paging_commit'),('0310_054','0311_055'),('make_cancel_cleanup_checks','make_paging_checks'),
                ('==33','==35'),('checks=33','checks=35'),('Ran 167 tests','Ran 179 tests'),('windows_unit_tests=167','windows_unit_tests=179'),
                ("versionCode='504'","versionCode='505'")]:s=s.replace(old,new)
s=s.replace("assert 'CancelServiceTest: 38 checks passed' in alog", "assert 'CancelServiceTest: 38 checks passed' in alog\nassert 'ReaderPagerTest: 29 checks passed' in alog")
s=s.replace("b'cleanupUri',b'toRealPath'", "b'cleanupUri',b'toRealPath',b'Lapp/jmbatch/android/ReaderPager;',b'Lapp/jmbatch/android/ReaderRequests;',b'setTranslationX'")
s=s.replace("assert any('cache cleanup UI' in check for check in data['checks'])", "assert any('cache cleanup UI' in check for check in data['checks'])\n    assert data['reader_paging']['transitions']==100 and data['reader_paging']['failure_retains_display']")
(release/'audit_paging_release.py').write_text(s,encoding='utf-8')
s=(release/'verify_cancel_cleanup_commit.py').read_text(encoding='utf-8').replace('cleanup-0310-054','paging-0311-055')
(release/'verify_paging_commit.py').write_text(s,encoding='utf-8')
s=(maintenance/'verify_cancel_cleanup_online.py').read_text(encoding='utf-8')
for old,new in [('cancel-cleanup-0310-054','paging-0311-055'),('0.3.10','0.3.11'),('0.3.9','0.3.10'),('0.5.4','0.5.5'),
                ('release-0310-054','release-0311-055'),('range(1,11)','range(1,12)'),('取消任务后自动删除文件与记录','左右翻页流畅度修复')]:s=s.replace(old,new)
(maintenance/'verify_paging_online.py').write_text(s,encoding='utf-8')
s=(maintenance/'verify_android_cancel_cleanup_online.py').read_text(encoding='utf-8')
for old,new in [('cancel-cleanup-054','paging-055'),('0.3.10','0.3.11'),('0.3.9','0.3.10'),('0.5.4','0.5.5'),('0.5.3','0.5.4'),
                ('release-0310-054','release-0311-055'),('取消任务后自动删除文件与记录','左右翻页流畅度修复'),('!=14','!=15'),('14-release','15-release'),('full_history_versions=14','full_history_versions=15')]:s=s.replace(old,new)
(maintenance/'verify_android_paging_online.py').write_text(s,encoding='utf-8')
print('Prepared package/source/commit/signature/public-update verification recipes')
