"""Adapt existing release verification to this exact version combination."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
p=ROOT/'work/scripts/release/verify_chapter_delete_commit.py'
(p.parent/'verify_collections_commit.py').write_text(p.read_text(encoding='utf-8').replace('chapter-delete-0322-0521-complete','collections-0323-063-complete'),encoding='utf-8')
p=ROOT/'work/scripts/maintenance/verify_dns_speed_online.py'
changes={'release-android-0.6.2':'release-0.3.23-0.6.3','work/release-android-062':'work/release-0323-063',
    'dns-speed-062':'collections-0323-063','0.6.2':'0.6.3','0.6.1':'0.6.2','0.3.22':'0.3.23','0.3.21':'0.3.22',
    'LiveDnsSpeedUpdate':'LiveCollectionsUpdate','备用 DNS 图片下载提速':'漫画库收藏夹','35-release':'36-release','!=35':'!=36','full_history_versions=35':'full_history_versions=36'}
pattern=re.compile('|'.join(map(re.escape,sorted(changes,key=len,reverse=True))))
s=pattern.sub(lambda m:changes[m[0]],p.read_text(encoding='utf-8'))
s=s.replace('from update_install import transfer','from update_install import transfer,prepare')
s=s.replace("assert fetch_release(DEFAULT_REPOSITORY,'0.3.22')['version']=='0.3.23'", "windows=fetch_release(DEFAULT_REPOSITORY,'0.3.22')\nassert windows['version']=='0.3.23'\nassert fetch_release(DEFAULT_REPOSITORY,'0.3.23') is None\nready=prepare(scratch,windows,'0.3.22',threading.Event(),lambda text:print(text,flush=True) if '%' not in text else None)")
s=s.replace('production_android_rules_checked=True,public_apk_download_verified=True', 'production_android_rules_checked=True,public_apk_download_verified=True,windows_download_verified=True,windows_staged=True')
(p.parent/'verify_collections_online.py').write_text(s,encoding='utf-8')
print('Prepared source and public update verification')
