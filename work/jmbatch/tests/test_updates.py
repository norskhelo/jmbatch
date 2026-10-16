import threading
import io
import json
import unittest
from unittest.mock import patch
from updates import Checker, normalize_repo, select_release, update_settings, DEFAULT_REPOSITORY, fetch_release, LIMIT, announcement_text


def release(version, *, prerelease=False, draft=False, host="github.com", platform="Windows-x64.zip"):
    name=f"JMBatch-{version}-{platform}"
    return {"prerelease":prerelease,"draft":draft,"assets":[{"name":name,"state":"uploaded","size":100,
        "browser_download_url":f"https://{host}/owner/app/releases/download/release-1/{name}"}]}


class UpdateTests(unittest.TestCase):
    def test_upgrade_baseline_migrates_and_survives_restart_and_resets_next_upgrade(self):
        from updates import announcement_baseline
        current="0.3.3"
        self.assertEqual(announcement_baseline({},"0.2.2",current,"owner/app"),"0.2.2")
        saved=dict(repository="owner/app",installed_version=current,from_version="0.2.2")
        self.assertEqual(announcement_baseline(saved,current,current,"owner/app"),"0.2.2")
        self.assertEqual(announcement_baseline(saved,current,"0.3.4","owner/app"),current)
        self.assertEqual(announcement_baseline(saved,current,"0.3.1","owner/app"),"0.3.1")
        self.assertEqual(announcement_baseline(saved,current,current,"other/app"),current)
        for broken in (None,[],{},dict(saved,from_version="bad"),dict(saved,from_version="9.0.0")):
            self.assertEqual(announcement_baseline(broken,current,current,"owner/app"),current)
        self.assertEqual(announcement_baseline({},"",current,"owner/app"),current)

    def test_completed_upgrade_history_is_retained_and_separated_from_future_updates(self):
        rows=[]
        for number in ("0.3.1","0.3.2","0.3.3"):
            item=release(number);item['body']='body-'+number;rows.append(item)
        saved=select_release(rows,"owner/app","0.3.0",True)
        text=announcement_text(saved,"owner/app","0.3.2","local","0.3.0")
        completed,pending=text.split("可用更新：")
        self.assertIn("本次升级：0.3.0 → 0.3.2",completed)
        self.assertIn("body-0.3.1",completed);self.assertIn("body-0.3.2",completed)
        self.assertNotIn("body-0.3.3",completed);self.assertIn("body-0.3.3",pending)
        at_latest=announcement_text(saved,"owner/app","0.3.3","local","0.3.0")
        self.assertTrue(all(row['body'] in at_latest for row in rows))
        self.assertNotIn("可用更新：",at_latest)

    def test_upgrade_history_never_labels_incomplete_or_foreign_cache_as_complete(self):
        rows=[]
        for number in ("0.3.1","0.3.3"):
            item=release(number);item['body']='body-'+number;rows.append(item)
        missing_current=select_release(rows,"owner/app","0.3.0",True)
        for data in (None,missing_current,dict(missing_current,repository="other/app"),
                     dict(missing_current,from_version="0.3.2"),
                     dict(repository="owner/app",version="0.3.2",notes="legacy")):
            text=announcement_text(data,"owner/app","0.3.2","local","0.3.0")
            self.assertIn("完整日志尚未获取",text)
            self.assertTrue(text.endswith("local"))

    def test_upgrade_baseline_is_persisted_before_seen_marker_changes_and_used_for_fetch(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock
        from updates import UpdateUI
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);(home/'announcement-seen.txt').write_text('0.3.0',encoding='utf-8')
            app=SimpleNamespace(home=home,root=Mock(),update_button=Mock())
            with patch('core.VERSION','0.3.3'):
                first=UpdateUI(app);first.automatic=False;first.show_notes=Mock()
                first.startup()
                self.assertEqual(first.upgrade_from,'0.3.0')
                reopened=UpdateUI(app)
                self.assertEqual(reopened.upgrade_from,'0.3.0')
                reopened.refresh=Mock();reopened.checker=Mock();reopened.checker.start.return_value=True
                reopened.check()
                self.assertEqual(reopened.checker.start.call_args.args[1],'0.3.0')
                row=release('0.3.3');row['body']='newest'
                cached=select_release([row],'owner/app','0.3.0',True)
                reopened.bulletin=cached;reopened.checked_repo=reopened.repo
                reopened.checker.poll.return_value=('skipped',None)
                reopened.poll()
                self.assertIs(reopened.bulletin,cached)
            with patch('core.VERSION','0.3.4'):
                self.assertEqual(UpdateUI(app).upgrade_from,'0.3.3')

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

    def test_history_contains_every_newer_release_and_preserves_long_notes(self):
        older=release("0.1.5"); older["body"]="Old release"
        newer=release("0.1.6"); newer["body"]="# New release\n" + "x"*9000
        selected=select_release([older,newer],"owner/app","0.1.4")
        self.assertEqual(selected["version"],"0.1.6")
        self.assertTrue(selected["notes"].startswith("# New release\n"))
        self.assertEqual(selected["notes"],newer["body"])
        self.assertEqual([item["version"] for item in selected["history"]],["0.1.5","0.1.6"])
        text=announcement_text(selected,"owner/app","0.1.4","local")
        self.assertIn(newer["body"],text)
        self.assertLess(text.index("Old release"),text.index("# New release"))

    def test_range_excludes_current_and_other_platform_and_sorts_numerically(self):
        rows=[]
        for number in ("0.1.10","0.1.8","0.1.9","0.1.7"):
            item=release(number);item["body"]="changes-"+number;rows.append(item)
        rows.extend([release("9.0.0",platform="Android.apk"),release("8.0.0",draft=True),
                     release("7.0.0",prerelease=True),release("6.0.0",host="bad.example")])
        selected=select_release(rows,"owner/app","0.1.8",include_current=True)
        self.assertEqual([e["version"] for e in selected["history"]],["0.1.9","0.1.10"])
        self.assertEqual(selected["url"],rows[0]["assets"][0]["browser_download_url"])
        text=announcement_text(selected,"owner/app","0.1.8","local")
        self.assertNotIn("changes-0.1.8",text)
        self.assertNotIn("changes-0.1.7",text)
        self.assertLess(text.index("changes-0.1.9"),text.index("changes-0.1.10"))

    def test_duplicate_versions_choose_latest_published_bulletin(self):
        old=release("0.1.9");old.update(body="superseded",published_at="2026-10-13T00:00:00Z")
        new=release("0.1.9");new.update(body="corrected",published_at="2026-10-14T00:00:00Z")
        for rows in ([old,new],[new,old]):
            selected=select_release(rows,"owner/app","0.1.8")
            self.assertEqual(selected["history"],[{"version":"0.1.9","notes":"corrected"}])

    def test_missing_notes_are_visible_and_malformed_assets_are_skipped(self):
        rows=[None,{"assets":None},{"assets":[None,{"name":None}]},release("0.1.9"),release("0.1.10")]
        rows[-1]["body"]=" \n"
        selected=select_release(rows,"owner/app","0.1.8")
        self.assertEqual(len(selected["history"]),2)
        text=announcement_text(selected,"owner/app","0.1.8","local")
        self.assertEqual(text.count("发布者未填写更新日志。"),2)
        same=select_release([release("0.1.8")],"owner/app","0.1.8",True)
        self.assertEqual(announcement_text(same,"owner/app","0.1.8","local"),"local")

    def test_more_than_twenty_releases_are_not_dropped(self):
        selected=select_release([release(f"0.1.{i}") for i in range(1,32)],"owner/app","0.1.1")
        self.assertEqual(selected["version"],"0.1.31")
        self.assertEqual(len(selected["history"]),30)

    @staticmethod
    def response(data):
        response=io.BytesIO(json.dumps(data).encode());response.status=200
        return response

    def test_pagination_keeps_intermediate_versions_even_after_an_older_release(self):
        batches=[[release("0.1.10"),release("0.1.1")],[release("0.1.9"),release("0.1.8")],[]]
        responses=[self.response(data) for data in batches]
        with patch("updates.PAGE_SIZE",2),patch("updates.urllib.request.build_opener") as factory:
            factory.return_value.open.side_effect=responses
            selected=fetch_release("owner/app","0.1.8",True)
            urls=[call.args[0].full_url for call in factory.return_value.open.call_args_list]
        self.assertEqual([entry["version"] for entry in selected["history"]],["0.1.9","0.1.10"])
        self.assertEqual(urls,[f"https://api.github.com/repos/owner/app/releases?per_page=2&page={i}" for i in (1,2,3)])
        self.assertTrue(all(response.closed for response in responses))

    def test_later_page_failure_never_returns_a_partial_history(self):
        for failure in (OSError("offline"),self.response({"message":"limited"})):
            with patch("updates.PAGE_SIZE",1),patch("updates.urllib.request.build_opener") as factory:
                factory.return_value.open.side_effect=[self.response([release("0.1.10")]),failure]
                with self.assertRaises((OSError,ValueError)):
                    fetch_release("owner/app","0.1.8")

    def test_page_limit_and_total_response_limit_reject_partial_history(self):
        with patch("updates.PAGE_SIZE",1),patch("updates.MAX_PAGES",2),patch("updates.urllib.request.build_opener") as factory:
            factory.return_value.open.side_effect=[self.response([release("0.1.10")]),self.response([release("0.1.9")])]
            with self.assertRaisesRegex(ValueError,"页数"):
                fetch_release("owner/app","0.1.8")
        batch=[release("0.1.10")]
        limit=len(json.dumps(batch).encode())+1
        with patch("updates.PAGE_SIZE",1),patch("updates.LIMIT",limit),patch("updates.urllib.request.build_opener") as factory:
            factory.return_value.open.side_effect=[self.response(batch),self.response([release("0.1.9")])]
            with self.assertRaisesRegex(ValueError,"响应过大"):
                fetch_release("owner/app","0.1.8")

    def test_cached_history_rebases_after_upgrade_and_isolates_repository(self):
        rows=[]
        for number in ("0.1.9","0.1.10","0.1.11"):
            item=release(number);item["body"]="body-"+number;rows.append(item)
        cached=json.loads(json.dumps(select_release(rows,"owner/app","0.1.8")))
        text=announcement_text(cached,"owner/app","0.1.9","local")
        self.assertNotIn("body-0.1.9",text)
        self.assertIn("body-0.1.10",text)
        self.assertIn("body-0.1.11",text)
        self.assertEqual(announcement_text(cached,"owner/app","0.1.11","local"),"版本 0.1.11 更新公告\n\nbody-0.1.11")
        for repo,current in (("other/app","0.1.8"),("owner/app","0.1.12"),("owner/app","0.1.7")):
            self.assertEqual(announcement_text(cached,repo,current,"local"),"local")

    def test_invalid_or_legacy_cache_is_not_presented_as_complete(self):
        cached=select_release([release("0.1.9"),release("0.1.10")],"owner/app","0.1.8")
        for history in ([],list(reversed(cached["history"])),cached["history"][:-1],[None]):
            self.assertEqual(announcement_text(dict(cached,history=history),"owner/app","0.1.8","local"),"local")
        legacy=dict(repository="owner/app",version="0.1.10",notes="old cache")
        self.assertIn("旧缓存仅包含最新版",announcement_text(legacy,"owner/app","0.1.8","local"))

    def test_failed_check_preserves_complete_offline_bulletin(self):
        from types import SimpleNamespace
        from updates import UpdateUI
        from core import VERSION
        cached=select_release([release("9.0.0")],"owner/app",VERSION)
        ui=UpdateUI.__new__(UpdateUI)
        ui.repo=ui.checked_repo="owner/app";ui.bulletin=cached
        ui.checker=SimpleNamespace(poll=lambda:("skipped",None))
        ui.app=SimpleNamespace(update_button=SimpleNamespace(configure=lambda **kwargs:None))
        ui.refresh=lambda:None
        ui.poll()
        self.assertIs(ui.bulletin,cached)
        self.assertIn("保留离线公告",ui.status)

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
