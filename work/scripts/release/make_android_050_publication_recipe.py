"""Derive this release's explicit recipe from the verified previous workflow."""
from pathlib import Path
root=Path(__file__).resolve().parent
text=(root/'publish_039_049.py').read_text(encoding='utf-8')
text=text.replace('Explicitly authorized Windows 0.3.9 / Android 0.4.9','Explicitly authorized Android 0.5.0')
text=text.replace("TAG = 'release-0.3.9-0.4.9'","TAG = 'release-android-0.5.0'")
text=text.replace("'android': '0.4.9'","'android': '0.5.0'")
text=text.replace('builds/windows-0.3.9-android-0.4.9/packages','builds/android-0.5.0/packages')
text=text.replace('publication/windows-0.3.9-android-0.4.9','publication/android-0.5.0')
text=text.replace('release-notes-0.3.9-0.4.9.md','release-notes-android-0.5.0.md')
text=text.replace("['JMBatch-0.3.9-Windows-x64.zip', 'JMBatch-0.4.9-Android.apk', NOTES,","['JMBatch-0.5.0-Android.apk', NOTES,")
text=text.replace('SHA256-release-0.3.9-0.4.9.txt','SHA256-release-android-0.5.0.txt')
text=text.replace('verify_manifest(OUT, VERSIONS)',"verify_manifest(OUT, {'android': '0.5.0'})")
text=text.replace('Windows 0.3.9 / Android 0.4.9 — 缓存清理与结果提示','Android 0.5.0 — 图片并行、CDN 选择与下载提速')
text=text.replace('all six assets','all five assets')
assert '0.4.9' not in text
(root/'publish_android_050.py').write_text(text,encoding='utf-8')
