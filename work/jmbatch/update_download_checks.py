"""Offline transport integration checks included in source and frozen self-tests."""
import io
import threading
from unittest.mock import patch
import update_download
from update_install import verify_file


def check_update_download(directory):
    calls, routes, counts = [], [], []
    url = 'https://github.com/owner/app/releases/download/v1/update.zip'
    class Response(io.BytesIO):
        status = 200
        headers = {'Content-Length': '5'}
    def open_request(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise TimeoutError('synthetic failure')
        return Response(b'old' if len(calls) == 2 else b'hello')
    with patch.object(update_download.urllib.request, 'build_opener') as factory:
        factory.return_value.open.side_effect = open_request
        output = io.BytesIO()
        update_download.transfer(url, output, 5, threading.Event(), counts.append, routes.append)
        assert output.getvalue() == b'hello'
        assert routes == ['GitHub', 'GHFast', 'GH-Proxy'] and counts == [0, 0, 3, 0, 5]
        cancel = threading.Event(); cancel.set()
        try:
            update_download.transfer(url, io.BytesIO(), 5, cancel)
            raise AssertionError('cancel ignored')
        except InterruptedError:
            assert len(calls) == 3
    package = dict(size=5, sha256='2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824')
    file = directory / 'mirror-check.bin'
    file.write_bytes(output.getvalue()); verify_file(file, package)
    file.write_bytes(b'Hello')
    try:
        verify_file(file, package)
        raise AssertionError('corrupt mirror content accepted')
    except ValueError:
        pass
