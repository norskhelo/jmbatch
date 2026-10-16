import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from chapters import ChapterChoiceRequired, resolve_chapters, select_chapters
from core import Settings, Task, task_cache
from diagnostics import FixtureClient
from download_covers import cover_source
from engine import Engine, WorkerState
from worker import run_download, worker_entry

CATALOG = [dict(id='800001', number=1, title='One'), dict(id='800002', number=2, title='Two')]

class ChapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def task(self, fmt='images'):
        return Task('123456', Settings(output=str(self.root / fmt), format=fmt, keep_images=True).__dict__).to_dict()
    def test_default_asks_before_hydrating_or_downloading(self):
        client = FixtureClient()
        with patch.object(client, 'check_photo') as detail, patch.object(client, 'download_by_image_detail') as image:
            with self.assertRaises(ChapterChoiceRequired) as caught:
                run_download(self.task(), '', lambda e: None, lambda: client)
        self.assertEqual(len(caught.exception.chapters), 2)
        detail.assert_not_called(); image.assert_not_called()
        self.assertFalse(Settings().download_all_chapters)
    def test_worker_sends_selection_instead_of_failure(self):
        import queue
        channel=queue.Queue()
        with patch('worker.run_download', side_effect=ChapterChoiceRequired(CATALOG)):
            # worker_entry redirects process output, so restore it after the call.
            import sys
            stdout,stderr=sys.stdout,sys.stderr
            try: worker_entry(self.task(),'',channel)
            finally: sys.stdout,sys.stderr=stdout,stderr
        self.assertEqual(channel.get()['type'],'chapters')
    def test_subset_all_formats_and_cache_resume(self):
        for fmt in ('pdf','zip','images'):
            task=self.task(fmt);task['selected_chapters']=[CATALOG[1]]
            calls=[]
            class Selected(FixtureClient):
                def check_photo(inner,photo):
                    calls.append(str(photo.id));super().check_photo(photo)
            events=[];run_download(task,'',events.append,Selected)
            self.assertEqual(set(calls),{'800002'});self.assertEqual(events[-1]['total'],2)
            self.assertTrue(cover_source(task)[0].endswith('0002\\00001.jpg'))
            output=Path(events[-1]['path'])
            if fmt=='zip':
                with zipfile.ZipFile(output) as z:self.assertEqual(z.namelist(),['00001.jpg','00002.jpg'])
            elif fmt=='images':self.assertEqual(sorted(p.name for p in output.iterdir()),['00001.jpg','00002.jpg'])
            (task_cache(task)/'completed.json').unlink()
            with patch.object(FixtureClient,'download_by_image_detail',side_effect=AssertionError('cached page requested')):
                events=[];run_download(task,'',events.append,FixtureClient)
            self.assertEqual(next(e for e in events if e['type']=='progress')['cached'],2)
    def test_all_chapters_and_single_chapter_bypass(self):
        self.assertEqual(resolve_chapters(CATALOG,[],True),CATALOG)
        self.assertEqual(resolve_chapters(CATALOG[:1],[],False),CATALOG[:1])
        task=self.task();task['settings']['download_all_chapters']=True
        events=[];run_download(task,'',events.append,FixtureClient)
        self.assertEqual(events[-1]['total'],5)
    def test_nonconsecutive_chapters_keep_original_folders(self):
        import jmcomic
        class Four(FixtureClient):
            def get_album_detail(inner,album_id):
                return jmcomic.JmAlbumDetail(album_id,'220980','Four chapters',
                    [(str(800000+i),str(i),'Chapter '+str(i)) for i in range(1,5)],
                    9,'2026-01-01','2026-01-01','0','0',0,[],[],[],[])
        task=self.task('zip')
        task['selected_chapters']=[dict(id='800002',number=2,title='Two'),dict(id='800004',number=4,title='Four')]
        events=[];run_download(task,'',events.append,Four)
        with zipfile.ZipFile(events[-1]['path']) as archive:
            self.assertEqual(archive.namelist(),['0002/00001.jpg','0002/00002.jpg','0004/00001.jpg','0004/00002.jpg'])
        self.assertFalse((task_cache(task)/'images/0001').exists())
    def test_reorder_and_new_chapters_preserve_saved_choice_and_number(self):
        saved=[CATALOG[1]]
        self.assertEqual(resolve_chapters(CATALOG[::-1],saved,True),saved)
        with self.assertRaises(ValueError):resolve_chapters(CATALOG[:1],saved,True)
    def test_invalid_or_empty_choices(self):
        for ids in ([],['missing']):
            with self.assertRaises(ValueError):select_chapters(CATALOG,ids)
        self.assertEqual(select_chapters(CATALOG,['800002','800001']),CATALOG)
    def test_queue_wait_releases_slot_pause_restart_and_retry(self):
        engine=Engine(self.root/'home');engine.add(['123456'],Settings(output=str(self.root/'out')))
        task=engine.tasks[0];state=WorkerState(task);engine.active[task.key]=state
        engine._handle(state,dict(type='chapters',chapters=CATALOG),0)
        self.assertFalse(engine.active);self.assertEqual(task.status,'selecting')
        engine.pause();self.assertEqual(task.status,'paused')
        engine=Engine(self.root/'home');engine.start();task=engine.tasks[0]
        self.assertEqual(task.status,'selecting')
        engine.choose_chapters(task.key,['800002']);engine.pause()
        engine=Engine(self.root/'home');task=engine.tasks[0]
        engine.retry([task.key],Settings(output=str(self.root/'other'),download_all_chapters=True))
        self.assertEqual(task.selected_chapters,[CATALOG[1]])
        self.assertEqual(task.settings['output'],str(self.root/'out'))
    def test_settings_round_trip_and_deferred_choice(self):
        engine=Engine(self.root/'home');engine.settings.download_all_chapters=True;engine.save()
        self.assertTrue(Engine(self.root/'home').settings.download_all_chapters)
        engine.add(['123456'],Settings(output=str(self.root/'out')))
        task=engine.tasks[0];task.chapter_options=CATALOG;task.status='selecting'
        engine.postpone_chapters(task.key);engine.start()
        self.assertEqual(task.status,'selecting');self.assertFalse(task.selected_chapters)

if __name__=='__main__':unittest.main()
