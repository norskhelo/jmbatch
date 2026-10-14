import threading
import io
import json
import unittest
from unittest.mock import patch
from updates import Checker, normalize_repo, select_release, update_settings, DEFAULT_REPOSITORY, fetch_release, LIMIT


def release(version, *, prerelease=False, draft=False, host="github.com", platform="Windows-x64.zip"):
    name=f"JMBatch-{version}-{platform}"
    return {"prerelease":prerelease,"draft":draft,"assets":[{"name":name,"state":"uploaded","size":100,
        "browser_download_url":f"https://{host}/owner/app/releases/download/release-1/{name}"}]}


class UpdateTests(unittest.TestCase):
    def test_current_version_announcement_is_fetched_without_an_update(self):
        data=release("0.1.7");data["body"]="Full current release announcement"
        response=io.BytesIO(json.dumps([data]).encode());response.status=200
        with patch("updates.urllib.request.build_opener") as factory:
            factory.return_value.open.return_value=response
            result=fetch_release("owner/app","0.1.7",include_current=True)
        self.assertEqual(result["notes"],data["body"])
        self.assertIsNone(select_release([data],"owner/app","0.1.7"))

    def test_offline_announcement_fallback_and_repository_isolation(self):
        from updates import announcement_text
        bulletin=dict(repository="owner/app",version="0.1.7",notes="cached full notes")
        self.assertIn("cached full notes",announcement_text(bulletin,"owner/app","0.1.7","local"))
        self.assertEqual(announcement_text(bulletin,"other/app","0.1.7","local"),"local")
        self.assertEqual(announcement_text(bulletin,"owner/app","0.1.8","local"),"local")
        self.assertEqual(announcement_text(None,"owner/app","0.1.7","local"),"local")

    def test_notes_belong_to_selected_release_and_are_bounded(self):
        older=release("0.1.5"); older["body"]="Old release"
        newer=release("0.1.6"); newer["body"]="# New release\n" + "x"*9000
        selected=select_release([older,newer],"owner/app","0.1.4")
        self.assertEqual(selected["version"],"0.1.6")
        self.assertTrue(selected["notes"].startswith("# New release\n"))
        self.assertEqual(len(selected["notes"]),8000)

    def test_http_response_selection_and_size_limit(self):
        for payload, oversized in ((json.dumps([release("0.1.5")]).encode(), False), (b" " * (LIMIT + 1), True)):
            response = io.BytesIO(payload)
            response.status = 200
            with patch("updates.urllib.request.build_opener") as factory:
                factory.return_value.open.return_value = response
                if oversized:
                    with self.assertRaises(ValueError):
                        fetch_release("owner/app", "0.1.4")
                else:
                    self.assertEqual(fetch_release("owner/app", "0.1.4")["version"], "0.1.5")
            self.assertTrue(response.closed)

    def test_default_repository_migration_preserves_user_choices(self):
        fresh = update_settings({})
        self.assertEqual(fresh["repository"], "norskhelo/jmbatch")
        self.assertTrue(fresh["automatic"])
        legacy = update_settings({"repository": "", "automatic": False})
        self.assertEqual(legacy["repository"], DEFAULT_REPOSITORY)
        self.assertFalse(legacy["automatic"])
        custom = update_settings({"repository": "https://github.com/owner/app", "automatic": False})
        self.assertEqual(custom["repository"], "owner/app")
        self.assertFalse(custom["automatic"])
        cleared = update_settings({"repository": "", "automatic": True, "repository_default_v1": True})
        self.assertEqual(cleared["repository"], "")
        self.assertEqual(update_settings(cleared), cleared)

    def test_config_accepts_repo_and_url_but_not_other_endpoints(self):
        self.assertEqual(normalize_repo("https://github.com/owner/app.git/"),"owner/app")
        self.assertEqual(normalize_repo(""),"")
        for value in ("http://github.com/owner/app","https://other.example/owner/app","owner/app/releases","owner/..","owner/app?token=x"):
            with self.assertRaises(ValueError):normalize_repo(value)

    def test_platform_versions_sorted_numerically(self):
        result=select_release([release("0.1.9"),release("0.1.10"),release("9.0.0",platform="Android.apk")],"owner/app","0.1.3")
        self.assertEqual(result["version"],"0.1.10")
        self.assertIsNone(select_release([release("0.1.3"),release("0.1.2")],"owner/app","0.1.3"))

    def test_unpublished_and_foreign_downloads_ignored(self):
        self.assertIsNone(select_release([release("9.0.0",prerelease=True),release("9.0.0",draft=True),
                                         release("9.0.0",host="github.com.evil.example")],"owner/app","0.1.3"))
        self.assertIsNone(select_release([release("9.0.0")],"other/repo","0.1.3"))
        asset=release("9.0.0")
        asset["assets"][0]["browser_download_url"]="https://github.com/owner/app/releases/download/tag/../../JMBatch-9.0.0-Windows-x64.zip"
        self.assertIsNone(select_release([asset],"owner/app","0.1.3"))

    def test_connection_error_is_a_skipped_result(self):
        def fail(*args):raise OSError("offline")
        checker=Checker();self.assertTrue(checker.start("owner/app","0.1.3",fail));checker.thread.join(1)
        self.assertEqual(checker.poll(),("skipped",None))
        self.assertIsNone(checker.pending)

    def test_hung_check_does_not_block_and_late_result_is_ignored(self):
        gate=threading.Event()
        def hang(*args):gate.wait(2);return {"version":"9.0.0"}
        checker=Checker()
        try:
            with patch("updates.time.monotonic",return_value=100):
                self.assertTrue(checker.start("owner/app","0.1.3",hang))
                self.assertIsNone(checker.poll())
                self.assertFalse(checker.start("owner/app","0.1.3",hang))
            with patch("updates.time.monotonic",return_value=108):
                self.assertEqual(checker.poll(),("skipped",None))
            self.assertFalse(checker.start("owner/app","0.1.3",hang))
        finally:
            gate.set();checker.thread.join(1)
        self.assertIsNone(checker.poll())
        self.assertTrue(checker.start("owner/app","0.1.3",lambda *args:None))
        checker.thread.join(1)
        self.assertEqual(checker.poll(),("ok",None))

    def test_update_found_is_returned_once(self):
        checker=Checker()
        self.assertTrue(checker.start("owner/app","0.1.3",lambda *args:{"version":"0.1.4"}))
        checker.thread.join(1)
        self.assertEqual(checker.poll(),("ok",{"version":"0.1.4"}))
        self.assertIsNone(checker.poll())
