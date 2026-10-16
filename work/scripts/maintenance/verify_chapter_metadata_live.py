"""Measure complete 518074 metadata loading and resume; never fetch images."""
from pathlib import Path
import json
import os
import sys
import time
from urllib.parse import urlsplit
import threading

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'work/jmbatch'))
os.environ['JM_BATCH_HOME']=str(ROOT/'work/tests/chapter-metadata-live/app-home')
from core import Settings,Task,atomic_json
from worker import run_download
from network_routes import make_strategy
import jmcomic

report=ROOT/'outputs/reports/chapter-metadata-live';report.mkdir(parents=True,exist_ok=True)
task=Task('518074',Settings(output=str(ROOT/'work/tests/chapter-metadata-live/output'),download_all_chapters=True).__dict__).to_dict()
results=[]
class BeforeImages(Exception):pass
for label in ('cold','resume'):
    requests=[];events=[];lock=threading.Lock();active=[0];peak=[0]
    def factory():
        option=jmcomic.JmOption.construct({'log':False,'client':{'impl':'api','retry_times':2,'postman':{'type':'curl_cffi_session','meta_data':{'timeout':25}}}})
        client=option.new_jm_client(domain_retry_strategy=make_strategy())
        original=client.req_api
        def req(url,*args,**kwargs):
            path=urlsplit(url).path;start=time.perf_counter()
            with lock:active[0]+=1;peak[0]=max(peak[0],active[0])
            try:return original(url,*args,**kwargs)
            finally:
                with lock:active[0]-=1;requests.append(dict(path=path,seconds=round(time.perf_counter()-start,3)))
        client.req_api=req
        client.download_by_image_detail=lambda *a,**k: (_ for _ in ()).throw(AssertionError('Images forbidden'))
        return client
    def emit(event):
        if event.get('type')=='metadata':events.append(event['message'])
        if event.get('type')=='phase' and event.get('phase')=='download':raise BeforeImages()
    started=time.perf_counter()
    try:run_download(task,'',emit,factory)
    except BeforeImages:pass
    summary=dict(mode=label,seconds=round(time.perf_counter()-started,3),chapters=len(task['selected_chapters']),
                 chapter_requests=sum(r['path']=='/chapter' for r in requests),peak_requests=peak[0],
                 last_progress=next((v for v in reversed(events) if v.startswith('读取所选章节')),None),requests=requests)
    assert peak[0]<=4
    assert summary['chapter_requests']==(len(task['selected_chapters']) if label=='cold' else 0)
    results.append(summary);atomic_json(report/'results.json',results)
    print(json.dumps({k:v for k,v in summary.items() if k!='requests'},ensure_ascii=False),flush=True)
