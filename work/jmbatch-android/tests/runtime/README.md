# Android framework regression tests

Run from the repository root on Windows:

```powershell
.\work\venv\Scripts\python.exe work/scripts/maintenance/run_android_runtime_tests.py --run-id library-runtime
```

The runner downloads pinned Maven 3.9.9 (verified with its published SHA-512)
and Robolectric 4.14.1 dependencies into `work/android-tools`. Source copies,
test data and compiled classes stay in `work/tests/<run-id>`; logs stay in
`outputs/reports/<run-id>`. No phone, account, real comic files or release
installation is used. The normal APK build remains independent of Maven.

These tests execute the complete production library dialog and Android 10
framework widgets, with touch mode explicitly enabled and asserted. The old
`GridView.setSelectionFromTop` call crashes on populated libraries in this
mode: the framework requests adapter position -1. Host widget doubles and
keyboard-mode framework tests did not reproduce it.

The suite checks initial entry, empty/populated list and tile modes, switching
while scrolled and in batch mode, and viewport restoration after refresh and
reopening. Framework resources are used for the theme; this is not an OEM
firmware, actual APK/Dex, visual or real-device test.

Tile mode is checked for exactly four columns on normal, narrow/large-font
and landscape screens, including cases where only one row fits onscreen.
The main activity also ignores the obsolete download tile preference and uses
the vertical download list.

ReaderAlbumRuntimeTest exercises the production reader with synthetic image
folders, persistent page metadata and a counting Android content provider.
It covers opening a saved page in a 5000-page book before whole-book validation,
forward checks across chapter boundaries, jumping priorities, old and flat
layouts, missing/changed images, corrupt-index recovery and cancellation.
Both scrolling and paging are opened through ReaderActivity; the tests check
saved position, bounded image cache/request queue and worker shutdown. Provider
query counts establish lazy chapter access, not real phone storage timings.

For a before/after proof, pass `--library-source <path-to-old-LibraryScreen.java>`
and a separate run ID. The production tree is never replaced by that option.
