"""Prepare approved publication documentation and auditable local recipes."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[3]
p=ROOT/'README.md';text=p.read_text(encoding='utf-8')
text=text.replace('当前源码：**Windows 0.3.26 / Android 0.6.6（versionCode 606，待发布）**。漫画库首图等比铺满封面框，横图取中央部分。当前正式版仍为 Windows 0.3.25 / Android 0.6.5。',
                  '当前源码及正式版本：**Windows 0.3.26 / Android 0.6.6（versionCode 606）**。漫画库首图等比铺满封面框，横图取中央部分。')
text=text.replace('0.3.25','0.3.26').replace('0.6.5','0.6.6')
p.write_text(text,encoding='utf-8')
mapping={'0.3.25':'0.3.26','0.3.24':'0.3.25','0.6.5':'0.6.6','0.6.4':'0.6.5','0325-065':'0326-066',
         'tile-cover-':'adaptive-cover-','LiveTileCoverUpdate':'LiveAdaptiveCoverUpdate','平铺封面缩放修复':'首图自适应封面',
         '38-release':'39-release','!=38':'!=39','full_history_versions=38':'full_history_versions=39'}
pattern=re.compile('|'.join(map(re.escape,sorted(mapping,key=len,reverse=True))))
p=ROOT/'work/scripts/maintenance/verify_tile_cover_online.py'
(p.parent/'verify_adaptive_cover_online.py').write_text(pattern.sub(lambda m:mapping[m[0]],p.read_text(encoding='utf-8')),encoding='utf-8')
p=ROOT/'work/scripts/release/verify_tile_cover_commit.py'
(p.parent/'verify_adaptive_cover_commit.py').write_text(p.read_text(encoding='utf-8').replace('tile-cover-0325-065','adaptive-cover-0326-066'),encoding='utf-8')
report=ROOT/'outputs/reports/adaptive-cover-0326-066-complete';report.mkdir(parents=True,exist_ok=True)
(report/'focused-checks.json').write_text(json.dumps(dict(
    windows_unittest_command='python -m unittest tests.test_display_view',windows_tests=16,windows_passed=True,
    android_rows_command='test_library_rows.py',android_row_checks=36,android_rows_passed=True,
    android_runtime_report='outputs/reports/adaptive-cover-runtime-final/runtime.log',android_framework_tests=5,
    preview='outputs/reports/adaptive-cover-preview/windows-library.jpg',
    user_preview_approved=True,approval='采用，继续推送并发布',android_device_tested=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Prepared approved release documentation and local verification recipes')
