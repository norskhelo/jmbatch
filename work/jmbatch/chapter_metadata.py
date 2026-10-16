"""Bounded metadata prefetch with task-local, non-executable resume records."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import re
import time

from core import atomic_json

MAX_WORKERS = 4
TTL_SECONDS = 24 * 60 * 60
MAX_RECORD_BYTES = 2 * 1024 * 1024


def cache_scope(album, cookie):
    # Fresh album discovery still validates permissions and the saved selection.
    value = [str(album.id), str(album.page_count), str(album.update_date),
             list(album.episode_list), cookie.strip()]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def valid_payload(value):
    return (isinstance(value, dict)
            and isinstance(value.get('pages'), list) and 0 < len(value['pages']) <= 20000
            and all(isinstance(p, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,255}', p)
                    and p not in ('.', '..') for p in value['pages'])
            and isinstance(value.get('domain'), str)
            and re.fullmatch(r'[A-Za-z0-9.-]{1,253}', value['domain']) is not None
            and isinstance(value.get('scramble'), str) and value['scramble'].isdigit()
            and len(value['scramble']) <= 15)


class MetadataCache:
    def __init__(self, root, scope, clock=time.time):
        self.root, self.scope, self.clock = root, scope, clock

    def path(self, chapter_id):
        if re.fullmatch(r'[0-9]{1,10}', str(chapter_id)) is None:
            raise ValueError('章节编号无效')
        return self.root / (str(chapter_id) + '.json')

    def read(self, photo):
        path = self.path(photo.id)
        try:
            if path.stat().st_size > MAX_RECORD_BYTES:
                return False
            record = json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(record, dict) or record.get('schema') != 1
                    or record.get('scope') != self.scope or record.get('id') != str(photo.id)
                    or type(record.get('saved')) not in (float, int)
                    or not 0 <= self.clock() - record['saved'] < TTL_SECONDS
                    or not valid_payload(record.get('data'))):
                return False
            data = record['data']
            photo.page_arr = data['pages']
            photo.data_original_domain = data['domain']
            photo.scramble_id = data['scramble']
            return True
        except (OSError, ValueError, TypeError, OverflowError):
            return False

    def write(self, photo):
        data = dict(pages=photo.page_arr, domain=photo.data_original_domain, scramble=str(photo.scramble_id))
        if not valid_payload(data):
            raise ValueError('章节图片列表或解码参数无效，未保存缓存')
        if len(json.dumps(data, ensure_ascii=False).encode('utf-8')) > MAX_RECORD_BYTES - 4096:
            raise ValueError('章节信息过大')
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_json(self.path(photo.id), dict(schema=1, scope=self.scope, id=str(photo.id), saved=self.clock(), data=data))

    def invalidate(self, photos):
        for photo in photos:
            self.path(photo.id).unlink(missing_ok=True)


def hydrate(photos, cache, fetch, progress):
    """Workers touch separate photos; only the coordinator persists/reports results.

    At most four requests are scheduled. The first miss warms the shared API's
    album scramble cache before concurrent calls, avoiding duplicate requests.
    Windows pause terminates the isolated process; atomic records survive it.
    """
    missing, done, cached = [], 0, 0
    progress(0, len(photos), 0)
    for photo in photos:
        if cache.read(photo):
            done += 1
            cached += 1
            progress(done, len(photos), cached)
        else:
            missing.append(photo)
    if not missing:
        return cached

    def commit(photo):
        nonlocal done
        cache.write(photo)
        done += 1
        progress(done, len(photos), cached)

    fetch(missing[0])
    commit(missing[0])
    remaining = iter(missing[1:])
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix='chapter') as pool:
        pending = {}

        def submit():
            photo = next(remaining, None)
            if photo is not None:
                pending[pool.submit(fetch, photo)] = photo

        for _ in range(MAX_WORKERS):
            submit()
        try:
            while pending:
                completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                # Process every completed result before scheduling more on success.
                for future in completed:
                    photo = pending.pop(future)
                    future.result()
                    commit(photo)
                for _ in completed:
                    submit()
        finally:
            for future in pending:
                future.cancel()
    return cached
