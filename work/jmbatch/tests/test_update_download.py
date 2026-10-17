import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
import update_download as download
import update_install as install

TEST_TEMP = Path(__file__).resolve().parent / '_tmp'
TEST_TEMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEST_TEMP)

BASE = 'https://github.com/owner/app/releases/download/v1/'
URL = BASE + 'JMBatch-0.1.7-Windows-x64.zip'


class Response:
    def __init__(self, data=b'hello', length=None, status=200, type='application/octet-stream', failure=False):
        self.status = status
        self.headers = {'Content-Length': str(len(data) if length is None else length), 'Content-Type': type}
        self.stream = io.BytesIO(data)
        self.failure = failure

    def read(self, n):
        data = self.stream.read(n)
        if not data and self.failure:
            raise TimeoutError('read interrupted')
        return data

    def close(self):
        self.stream.close()


class DownloadTests(unittest.TestCase):
    def run_download(self, answers, output=None, cancel=None, **kwargs):
        self.calls = []
        self.routes = []
        self.progress = []
        self.output = output if output is not None else io.BytesIO()
        def open_request(request, timeout):
            self.calls.append(request.full_url)
            answer = answers[len(self.calls)-1]
            if isinstance(answer, Exception):
                raise answer
            return answer
        with patch.object(download.urllib.request, 'build_opener') as factory:
            factory.return_value.open.side_effect = open_request
            download.transfer(URL, self.output, 100, cancel or threading.Event(),
                              self.progress.append, self.routes.append, **kwargs)
        return self.output.getvalue()

    def test_healthy_github_does_not_contact_mirrors(self):
        self.assertEqual(self.run_download([Response()]), b'hello')
        self.assertEqual(self.calls, [URL])

    def test_route_order_and_progress_restart(self):
        self.assertEqual(self.run_download([TimeoutError(), OSError(), Response()]), b'hello')
        self.assertEqual(self.calls, [URL, 'https://ghfast.top/'+URL, 'https://gh-proxy.com/'+URL])
        self.assertEqual(self.routes, ['GitHub', 'GHFast', 'GH-Proxy'])
        self.assertEqual(self.progress, [0, 0, 0, 5])

    def test_partial_read_and_truncated_responses_are_replaced(self):
        for first in (Response(b'old bytes', failure=True), Response(b'old', length=10), Response(b''), Response(b'<html>', type='text/html')):
            self.assertEqual(self.run_download([first, Response()]), b'hello')
            self.assertEqual(len(self.calls), 2)

    def test_http_failures_fall_back(self):
        for status in (403, 404, 429, 500, 502):
            error = urllib.error.HTTPError(URL, status, 'failed', {}, None)
            self.assertEqual(self.run_download([error, Response()]), b'hello')

    def test_all_failed_leaves_no_combined_content(self):
        with self.assertRaisesRegex(download.DownloadFailure, 'GH-Proxy'):
            self.run_download([Response(b'a', failure=True), Response(b'bb', failure=True), Response(b'ccc', failure=True)])
        self.assertEqual(self.output.getvalue(), b'')
        self.assertEqual(len(self.calls), 3)

    def test_cancel_before_request(self):
        cancel = threading.Event(); cancel.set()
        with self.assertRaises(InterruptedError):
            self.run_download([], cancel=cancel)
        self.assertEqual(self.calls, [])

    def test_cancel_during_read_does_not_switch(self):
        cancel = threading.Event()
        response = Response()
        def stop(n):
            cancel.set()
            raise TimeoutError()
        response.read = stop
        with self.assertRaises(InterruptedError):
            self.run_download([response], cancel=cancel)
        self.assertEqual(len(self.calls), 1)

    def test_local_write_and_flush_errors_do_not_switch(self):
        for operation in ('write', 'flush'):
            output = io.BytesIO()
            with patch.object(output, operation, side_effect=OSError('disk unavailable')):
                with self.assertRaisesRegex(OSError, 'disk unavailable'):
                    self.run_download([Response()], output=output)
            self.assertEqual(len(self.calls), 1)

    def test_oversize_is_fatal(self):
        with self.assertRaises(ValueError):
            self.run_download([Response(b'hello', length=101)])
        self.assertEqual(len(self.calls), 1)

    def test_origins_and_redirects_are_restricted(self):
        for url in ('http://github.com/owner/app/releases/download/v1/a', 'https://user@github.com/owner/app/releases/download/v1/a',
                    'https://github.com.evil.test/owner/app/releases/download/v1/a', URL+'?token=private', URL+'#fragment',
                    URL.replace('/v1/', '/%2e%2e/'), URL.replace('/v1/', '/v1%2fother/'), 'https://ghfast.top/'+URL):
            with self.assertRaises(ValueError): download.download_routes(url)
        handler = download.SafeRedirect(URL)
        request = urllib.request.Request(URL)
        for bad in ('http://ghfast.top/'+URL, 'https://ghfast.top.evil.test/'+URL,
                    'https://ghfast.top/https://github.com/evil/app/releases/download/v1/other.zip',
                    'https://gh-proxy.com/'+URL+'?x=1', 'https://user@ghfast.top/'+URL, 'https://evil.test/file'):
            with self.assertRaises(ValueError): handler.redirect_request(request, None, 302, '', {}, bad)
        self.assertTrue(download.allowed_url('https://ghfast.top/'+URL, URL))
        self.assertTrue(download.allowed_url('https://gh-proxy.com/'+URL, URL))
        self.assertTrue(download.allowed_url('https://release-assets.githubusercontent.com/file?token=signed', URL))

    def test_mirror_tampering_still_blocks_prepare(self):
        key = RSA.generate(2048)
        package = dict(version='0.1.7', name=URL.rsplit('/', 1)[1], size=5, sha256=hashlib.sha256(b'hello').hexdigest())
        raw = json.dumps(dict(schema=1, repository='owner/app', tag='v1', packages={'windows': package})).encode()
        signature = pkcs1_15.new(key).sign(SHA256.new(raw))
        release = dict(url=URL, repository='owner/app', name=package['name'], version='0.1.7')
        for tamper in ('signature', 'package'):
            calls = []
            def open_request(request, timeout):
                url = request.full_url; calls.append(url)
                if url.startswith('https://github.com/'):
                    raise TimeoutError('GitHub unavailable')
                data = raw if url.endswith('.json') else signature if url.endswith('.sig') else b'Hello'
                if tamper == 'signature' and url.endswith('.sig'): data = b'x' * len(signature)
                return Response(data)
            with tempfile.TemporaryDirectory() as temp, patch.object(install, 'PUBLIC_KEY', base64.b64encode(key.public_key().export_key(format='DER')).decode()), patch.object(download.urllib.request, 'build_opener') as factory:
                factory.return_value.open.side_effect = open_request
                with self.assertRaisesRegex(ValueError, '签名|SHA-256'):
                    install.prepare(Path(temp), release, '0.1.6', threading.Event(), lambda _: None)
                self.assertFalse(any(Path(temp).rglob('package.zip')))
            self.assertTrue(any(url.startswith('https://ghfast.top/') for url in calls))
            if tamper == 'signature': self.assertFalse(any(url.endswith('.zip') for url in calls))


if __name__ == '__main__': unittest.main()
