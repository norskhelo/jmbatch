# Android framework regression tests

PermissionRuntimeTest checks the permissions/network screen on Android 10 and
Android 15: no automatic network probe on entry, notification requests and
denial handling, disabled notification channels, return-from-settings refresh,
persisted directory grants and wrong-directory protection, original-app settings
intents and fallback, explicit report export/share, both home and failed-task
entry points, and a synthetic network probe under the same application identity.
It does not validate a particular manufacturer's permission UI or real network.

FallbackTlsRuntimeTest checks the production OriginTls adapter through Android's
HttpsURLConnection implementation on Android 10 and 15. A separate local JVM
TLS fixture verifies original-domain SNI, Host and path; wrong-domain and
untrusted certificates must fail before HTTP headers or cookies are sent.
Conscrypt provides the Android test client's sockets and PKIX trust manager;
the fixture uses an isolated temporary certificate and never a release key.
This checks TLS identity preservation, not a phone's mobile network or API 36.
Use --tests FallbackTlsRuntimeTest for a focused run.

The fallback suite also compares eight same-origin requests: per-request TLS
policies require eight connections, while the task-local policy permits one
keep-alive connection. A pooled socket must never authenticate a different
origin, even at the same IP and port. A delayed response body checks that the
configured read timeout is independent of the shorter TLS handshake budget.
These are loopback protocol checks, not real mobile-network speed measurements.

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

ChapterDeletionRuntimeTest covers the actual chapter-delete backend and synthetic
SAF publication. A 151-chapter / 7227-page fixture bounds directory listing and
document query counts both with and without an internal index. Retained pages
are each opened once at the source, written once, and read back once at the
target. It also checks absent timestamps, legacy manifests, foreign files,
mid-operation timestamp changes, corrupted target readback, cancellation,
record-save failures, rename failure and old-file cleanup failure. The complete
LibraryScreen test invokes the chapter picker and destructive confirmation.
The batch-mode switch test advances a frame after showing the batch toolbar
before simulating the next action, so consecutive actions use the laid-out UI.

CollectionRuntimeTest covers legacy catalogue loading, persistent folder
membership, rename/delete/move, save failure rollback, searches, stars, task and
chapter replacement, bounded previews, and corrupt metadata on Android 10/15.
On this Windows host, Java File.renameTo cannot replace an existing destination;
Android 15 AtomicFile expects Linux replacement semantics. The test-only shadow
bridges its private rename primitive with Files.move(REPLACE_EXISTING), leaving
the framework write/sync/close/recovery logic intact. An independent AtomicFile
replacement test checks this adapter. This is not an Android production change.
The library dialog tests also exercise folder cards, batch selection exclusion,
navigation, state restoration, moving back to the default library, and deletion.
