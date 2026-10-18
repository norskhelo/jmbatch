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

For a before/after proof, pass `--library-source <path-to-old-LibraryScreen.java>`
and a separate run ID. The production tree is never replaced by that option.
