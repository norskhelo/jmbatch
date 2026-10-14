import socket
import ssl
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from network_routes import (BadResponse, HttpFailure, RoutesExhausted, failure_kind,
                            merge_hosts, make_strategy, run_routes)


class RouteTests(unittest.TestCase):
    def test_invalid_target_moves_to_backup_without_same_host_retry(self):
        calls, notices = [], []
        def request(host):
            calls.append(host)
            if host == "bad.example":
                raise ConnectionError("Failed to connect to bad.example/[::]:443; cookie=secret")
            return "ok"
        self.assertEqual(run_routes(["bad.example", "good.example"], 5, "漫画接口", request, notices.append), "ok")
        self.assertEqual(calls, ["bad.example", "good.example"])
        self.assertIn("good.example", notices[0])

    def test_all_failed_report_retains_hosts_categories_and_no_secrets(self):
        calls = []
        def request(host):
            calls.append(host)
            if host == "a.example":
                raise ConnectionError("Failed to connect to a.example/[::]:443 token=private")
            raise socket.gaierror("https://b.example/album?id=123&token=secret")
        with self.assertRaises(RoutesExhausted) as caught:
            run_routes(["a.example", "b.example"], 5, "漫画接口", request)
        text = str(caught.exception)
        for value in ("a.example", "b.example", "未指定地址", "DNS 解析失败", "2 次请求"):
            self.assertIn(value, text)
        for value in ("secret", "private", "123", "https://"):
            self.assertNotIn(value, text)
        self.assertEqual(len(calls), 2)

    def test_timeout_rotates_first_and_is_bounded(self):
        calls = []
        def request(host):
            calls.append(host)
            raise TimeoutError()
        with self.assertRaises(RoutesExhausted):
            run_routes(["a.example", "b.example"], 2, "接口", request)
        self.assertEqual(calls, ["a.example", "b.example", "a.example", "b.example"])

    def test_zero_retries_still_tries_every_route(self):
        calls = []
        def request(host):
            calls.append(host)
            raise ConnectionRefusedError()
        with self.assertRaises(RoutesExhausted):
            run_routes(["a.example", "b.example"], 0, "接口", request)
        self.assertEqual(len(calls), 2)

    def test_access_and_rate_limits_do_not_failover(self):
        for code in (401, 403, 404, 429):
            calls = []
            def request(host):
                calls.append(host)
                raise HttpFailure(code)
            with self.assertRaises(HttpFailure):
                run_routes(["a.example", "b.example"], 2, "接口", request)
            self.assertEqual(len(calls), 1)

    def test_server_error_and_bad_response_can_recover(self):
        for error in (HttpFailure(503), BadResponse()):
            def request(host):
                if host == "a.example":
                    raise error
                return 7
            self.assertEqual(run_routes(["a.example", "b.example"], 0, "接口", request), 7)

    def test_local_file_error_and_cancel_are_not_network_failure(self):
        for error in (PermissionError("disk"), OSError(28, "full")):
            with self.assertRaises(type(error)):
                run_routes(["a.example"], 2, "图片", lambda _: (_ for _ in ()).throw(error))
        calls = []
        def cancelled():
            raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            run_routes(["a.example"], 2, "接口", calls.append, check=cancelled)
        self.assertEqual(calls, [])

    def test_tls_and_curl_classification(self):
        self.assertEqual(failure_kind(ssl.SSLCertVerificationError()), "tls")
        for code, kind in ((6, "dns"), (7, "connect"), (28, "timeout"), (60, "tls"), (52, "response")):
            error = OSError("contains secret")
            error.code = code
            self.assertEqual(failure_kind(error), kind)
        wrapped = RuntimeError("wrapped")
        wrapped.__cause__ = socket.gaierror()
        self.assertEqual(failure_kind(wrapped), "dns")

    def test_merge_preserves_builtin_and_rejects_url_and_duplicate(self):
        self.assertEqual(merge_hosts(["A.EXAMPLE", "https://evil.example/", "a.example", "bad..example"], ["b.example", "a.example"]), ["a.example", "b.example"])
        self.assertIn("backup.example", merge_hosts([f"a{i}.example" for i in range(100)], ["backup.example"]))

    def test_real_client_hook_during_initialization_and_preferred_route(self):
        from jmcomic import JmApiClient, JmModuleConfig
        calls = []
        def request(url, **kwargs):
            host = urlsplit(url).hostname
            calls.append((host, kwargs))
            if host == "bad.example":
                raise ConnectionError("failed to connect/[::]:443")
            return SimpleNamespace(status_code=200)
        def initialize(client):
            client.domain_list = ["bad.example"]  # simulate remote discovery replacing defaults
            client.request_with_retry(request, "/setting")
        with patch.object(JmApiClient, "after_init", initialize), \
             patch.object(JmApiClient, "get_meta_data", return_value=25), \
             patch.object(JmApiClient, "raise_if_resp_should_retry", side_effect=lambda r, i: r), \
             patch.object(JmModuleConfig, "DOMAIN_API_LIST", ["good.example"]):
            client = JmApiClient(postman=object(), domain_list=["bad.example"], retry_times=2, domain_retry_strategy=make_strategy())
            client.request_with_retry(request, "/album", headers={"token": "secret"})
        self.assertEqual([c[0] for c in calls], ["bad.example", "good.example", "good.example"])
        self.assertEqual(calls[-1][1]["headers"]["token"], "secret")
        self.assertEqual(calls[-1][1]["timeout"], (8, 25))
        self.assertNotIn("verify", calls[-1][1])

    def test_image_failover_preserves_path_and_query(self):
        from jmcomic import JmModuleConfig
        strategy = make_strategy()
        client = SimpleNamespace(retry_times=0, get_meta_data=lambda *_: 25,
                                 update_request_with_specify_domain=lambda *args: None,
                                 raise_if_resp_should_retry=lambda r, i: r)
        urls = []
        def request(url, **kwargs):
            urls.append(url)
            if len(urls) == 1:
                raise ConnectionRefusedError()
            return SimpleNamespace(status_code=200)
        strategy(client)
        with patch.object(JmModuleConfig, "DOMAIN_IMAGE_LIST", ["backup.example"]):
            strategy(client, request, "https://image.example/media/00001.jpg?q=1", True)
        self.assertEqual(urls, ["https://image.example/media/00001.jpg?q=1", "https://backup.example/media/00001.jpg?q=1"])


if __name__ == "__main__":
    unittest.main()
