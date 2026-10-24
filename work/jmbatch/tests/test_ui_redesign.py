import multiprocessing as mp
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from download_rate import DownloadRate
from reader import ReaderState
from chapter_delete import remap_state
from ui_library import sorted_items


def transfer(path, limit, ready, start, results):
    rate = DownloadRate(path, limit)
    ready.put(True); start.wait()
    for _ in range(8): rate.acquire(8192)
    results.put(time.monotonic())


class RedesignTests(unittest.TestCase):
    def test_shared_limit_is_aggregate_across_processes(self):
        ctx = mp.get_context('spawn')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'rate'; path.write_bytes(bytes(24))
            limit = ctx.Value('i', 64, lock=False)
            ready, results, start = ctx.Queue(), ctx.Queue(), ctx.Event()
            jobs = [ctx.Process(target=transfer, args=(path,limit,ready,start,results)) for _ in range(3)]
            try:
                for job in jobs: job.start()
                for _ in jobs: ready.get(timeout=15)
                began=time.monotonic(); start.set()
                finished=[results.get(timeout=15) for _ in jobs]
                elapsed=max(finished)-began
                self.assertGreaterEqual(elapsed,2.85)  # 192 KiB / 64 KiB/s
                self.assertLess(elapsed,6)
            finally:
                for job in jobs:
                    job.join(2)
                    if job.is_alive(): job.kill();job.join()
                    job.close()
                ready.close();results.close()

    def test_unlimited_and_live_limit_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rate';path.write_bytes(bytes(24))
            limit=SimpleNamespace(value=0);rate=DownloadRate(path,limit)
            start=time.monotonic();rate.acquire(10**9);self.assertLess(time.monotonic()-start,.1)
            limit.value=1;thread=threading.Thread(target=lambda:rate.acquire(65536));thread.start()
            time.sleep(.1);limit.value=0;thread.join(1);self.assertFalse(thread.is_alive())

    def test_stream_throttle_preserves_payload_and_excludes_wait_from_read_timeout(self):
        payload=bytes(range(256))*256
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'rate';path.write_bytes(bytes(24));beats=[]
                rate=DownloadRate(path,SimpleNamespace(value=32),lambda:beats.append(time.monotonic()))
                client=SimpleNamespace(get_meta_data=lambda:{},postman=SimpleNamespace(get_root_postman=lambda:SimpleNamespace()))
                start=time.monotonic();response=rate.request(f'http://127.0.0.1:{server.server_port}/',{'timeout':(.5,.1)},client)
                self.assertEqual(response.content,payload);self.assertGreater(time.monotonic()-start,1.85);self.assertTrue(beats)
                rate.local.session.close()
        finally:server.shutdown();server.server_close();thread.join()

    def test_favorites_sort_ascending_before_ordinary_comics(self):
        items=[('a',{'title':'Z','favorite':True}),('b',{'title':'B','favorite':False}),('c',{'title':'A','favorite':True}),('d',{'title':'C','favorite':False})]
        view=SimpleNamespace(sort_mode='name',sort_facts={})
        self.assertEqual([k for k,_ in sorted_items(view,items)],['c','a','b','d'])

    def test_named_bookmarks_survive_restart_and_chapter_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            state=ReaderState(directory);state.put('a',4,'vertical',{1,4},{'1':'old','4':'keep'})
            saved=ReaderState(directory).get('a',6)
            mapped=remap_state(saved,[1,1,1,2,2,2],{1})
            self.assertEqual(mapped,dict(page=1,mode='vertical',bookmarks=[1],bookmarkNames={'1':'keep'}))


if __name__=='__main__':unittest.main()
