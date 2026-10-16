"""Keep the final Android bulletin and readme byte-for-text aligned with notes."""
from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[3]
notes=(root/'work/release-android-050/release-notes.md').read_text(encoding='utf-8')
plain=re.sub(r'^#{1,2} ', '', notes, flags=re.M).replace('- ','• ')
path=root/'work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'
text=path.read_text(encoding='utf-8')
text=re.sub(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";',lambda m:'private static final String CURRENT_NOTES='+json.dumps(plain,ensure_ascii=False)+';',text)
path.write_text(text,encoding='utf-8')
path=root/'work/jmbatch-android/README.txt'
text=path.read_text(encoding='utf-8').split('Android 0.5.0 — 2026-10-16')[0]
path.write_text(text+plain,encoding='utf-8')
