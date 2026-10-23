"""A process-safe shared image budget; killed workers cannot strand its lock."""
import os
import struct
import threading
import time
from pathlib import Path


class DownloadRate:
    def __init__(self, path, limit, heartbeat=lambda: None):
        self.path, self.limit, self.heartbeat = Path(path), limit, heartbeat
        self.local = threading.local()

    def acquire(self, count):
        # OS-owned locks are released even when Engine terminates a worker.
        if not self.limit.value:
            return
        with self.path.open('r+b', buffering=0) as handle:
            while count:
                kb = self.limit.value
                if kb <= 0:
                    return
                self.heartbeat()
                handle.seek(0)
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    time.sleep(.01)
                    continue
                try:
                    raw = handle.read(24)
                    previous, tokens, old_limit = struct.unpack('ddd', raw)
                    now = time.monotonic()
                    rate = kb * 1024
                    capacity = max(1024, rate * .1)
                    tokens = min(capacity, tokens + max(0, now - previous) * rate) if old_limit == kb else 0
                    grant = int(min(count, tokens))
                    count -= grant
                    handle.seek(0)
                    handle.write(struct.pack('ddd', now, tokens - grant, kb))
                finally:
                    handle.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle, fcntl.LOCK_UN)
                if count:
                    time.sleep(min(.05, max(.001, min(count, capacity) / rate)))

    def request(self, url, options, client):
        # Streaming socket reads keep the configured read timeout separate from
        # intentional token waits. Reuse one HTTPS session per image thread.
        import requests
        if not hasattr(self.local, 'session'):
            self.local.session = requests.Session()
        allowed = {'headers', 'cookies', 'params', 'auth', 'timeout', 'allow_redirects', 'proxies', 'verify', 'cert'}
        values = {k: v for k, v in client.get_meta_data().items() if k in allowed}
        values.update({k: v for k, v in options.items() if k in allowed})
        # Propagate cookies established by the original API session as well.
        postman = client.postman.get_root_postman()
        cookies = getattr(getattr(postman, 'session', None), 'cookies', None)
        if cookies is not None:
            self.local.session.cookies.update(cookies.jar)
        with self.local.session.get(url, stream=True, **values) as response:
            chunks = bytearray()
            for chunk in response.iter_content(16384):
                self.acquire(len(chunk))
                chunks.extend(chunk)
            response._content = bytes(chunks)
            response._content_consumed = True
            return response
