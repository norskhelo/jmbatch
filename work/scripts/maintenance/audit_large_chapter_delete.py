"""Measure chapter-delete work on generated 151-chapter / 7227-page fixtures.

Only diagnostic fixtures are changed; no downloaded/user manga is accessed.
Android uses the existing Android 10 framework harness and a counted SAF provider.
"""
from pathlib import Path
import argparse
from collections import Counter
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser()
parser.add_argument('platform', choices=['windows', 'android'])
parser.add_argument('--run-id', required=True)
args = parser.parse_args()
if not args.run_id.replace('-', '').replace('_', '').isalnum():
    parser.error('Use a simple run ID')
run = ROOT / 'work/tests' / args.run_id
run.mkdir(parents=True, exist_ok=False)
report = ROOT / 'outputs/reports' / args.run_id
report.mkdir(parents=True, exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def windows():
    sys.path.insert(0, str(ROOT / 'work/jmbatch'))
    os.environ['JM_BATCH_HOME'] = str(run / 'app-home')
    from PIL import Image
    import albums
    import chapter_delete
    from core import Task, Settings, atomic_json
    from engine import Engine

    home = run / 'app-home'
    home.mkdir()
    output = run / 'books'
    output.mkdir()
    source = output / 'JM123-generated-12345678'
    source.mkdir()
    buffer = io.BytesIO()
    Image.new('RGB', (2, 3), (20, 40, 60)).save(buffer, 'JPEG')
    payload = buffer.getvalue()
    records = []
    for chapter in range(1, 152):
        for page in range(1, (48 if chapter <= 130 else 47) + 1):
            relative = albums.image_name(chapter, page, 151)
            path = source / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(payload)
            records.append(dict(chapter=chapter, page=page, file=relative, size=len(payload)))
    assert len(records) == 7227
    atomic_json(albums.album_index(source), dict(version=2, id='123', title='generated', entries=records))
    engine = Engine(home)
    task = Task('123', Settings(output=str(output), format='images').__dict__)
    task.status, task.title, task.result = 'done', 'generated', str(source)
    engine.tasks.append(task)
    engine.library.sync([task])
    engine.save()
    key = engine.library.key(source)
    phases = {}
    original_read, original_copy, original_stat = albums.read_album, chapter_delete._copy, Path.stat
    counters = Counter()

    def read(*a, **kw):
        counters['full_album_loads'] += 1
        return original_read(*a, **kw)

    def copy(incoming, target, cancelled):
        counters['retained_pages_copied'] += 1
        return original_copy(incoming, target, cancelled)

    def stat(path, *a, **kw):
        counters['path_stat_calls'] += 1
        return original_stat(path, *a, **kw)

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(albums, 'read_album', read))
        stack.enter_context(patch.object(chapter_delete, 'read_album', read))
        stack.enter_context(patch.object(chapter_delete, '_copy', copy))
        stack.enter_context(patch.object(Path, 'stat', stat))
        start = time.perf_counter()
        plan = chapter_delete.inspect(engine.library, key)
        phases['open_chapter_list'] = dict(counters, seconds=time.perf_counter() - start)
        assert len(plan['chapters']) == 151 and len(plan['pages']) == 7227
        counters.clear()
        start = time.perf_counter()
        new_key, message = chapter_delete.delete_chapters(engine, key, [76], plan)
        phases['delete_one_48_page_chapter'] = dict(counters, seconds=time.perf_counter() - start)
    remaining = albums.read_album(Path(engine.library.entries[new_key]['path']))[1]
    assert len(remaining) == 7179
    result = dict(chapters=151, pages=7227, removed_pages=48, retained_pages=7179,
                  synthetic_page_bytes=len(payload), phases=phases, message=message,
                  note='Desktop synthetic metadata/copy measurement; not user storage or phone timing.')
    (report / 'measurement.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


JAVA = r'''package app.jmbatch.android;
import android.content.pm.ProviderInfo;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.json.*;
import org.junit.Test;
import org.robolectric.shadows.ShadowContentResolver;
import static org.junit.Assert.*;

public class LargeChapterDeleteProbe extends ChapterDeletionRuntimeTest {
    static class Counted extends TreeProvider {
        int documents, children, imageStamps;
        Counted(File base) {super(base);}
        public Cursor queryDocument(String id,String[] projection)throws FileNotFoundException {
            documents++;
            if(id.endsWith(".jpg") && Arrays.asList(projection).contains("last_modified"))imageStamps++;
            return super.queryDocument(id,projection);
        }
        public Cursor queryChildDocuments(String id,String[] projection,String sort)throws FileNotFoundException {
            children++;return super.queryChildDocuments(id,projection,sort);
        }
    }
    @Test public void measureLargeFolderInspection()throws Exception {
        JSONArray records=new JSONArray();
        for(int c=1;c<=151;c++)for(int p=1;p<=(c<=130?48:47);p++){
            String name=String.format(Locale.ROOT,"%04d/%05d.jpg",c,p);
            File page=new File(root,name);page.getParentFile().mkdirs();Files.write(page.toPath(),new byte[]{1,2,3});
            records.put(new JSONObject().put("chapter",c).put("page",p).put("file",name).put("size",3));
        }
        Counted counted=new Counted(root.getParentFile());
        ProviderInfo info=new ProviderInfo();info.authority="large.chapters.test";info.exported=true;info.grantUriPermissions=true;info.readPermission=info.writePermission="android.permission.MANAGE_DOCUMENTS";
        counted.attachInfo(context,info);Bridge bridge=new Bridge(counted);bridge.attachInfo(context,info);ShadowContentResolver.registerProviderInternal(info.authority,bridge);
        String tree="content://large.chapters.test/tree/root";
        Uri uri=DocumentsContract.buildDocumentUriUsingTree(Uri.parse(tree),"root/"+root.getName());
        AlbumStorage.remember(context,uri,new JSONObject().put("version",2).put("id","123").put("title","generated").put("entries",records));
        LibraryStore.Entry item=new LibraryStore.Entry("123","generated",uri.toString(),tree,"generated","images",false);
        long started=System.nanoTime();ChapterDeletion.Plan plan=ChapterDeletion.inspect(context,item,()->false);
        double seconds=(System.nanoTime()-started)/1e9;
        assertEquals(151,plan.counts.size());assertEquals(7227,plan.chapters.size());
        JSONObject result=new JSONObject().put("chapters",151).put("pages",7227).put("directory_queries",counted.children)
            .put("document_queries",counted.documents).put("individual_image_stamp_queries",counted.imageStamps)
            .put("total_queries",counted.children+counted.documents).put("host_framework_seconds",seconds)
            .put("note","One inspection with existing internal index; synthetic Android 10 provider, not device timing.");
        Files.write(Paths.get(System.getProperty("probe.report")),result.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        System.out.println(result.toString(2));
    }
}
'''


def android():
    source = run / 'src/main/java'
    shutil.copytree(ROOT / 'work/jmbatch-android/app/src/main/java', source)
    (source / 'app/jmbatch/android/R.java').write_text('package app.jmbatch.android; public final class R { public static class style { public static final int AppTheme=android.R.style.Theme_Material_Light_NoActionBar; } public static class drawable {public static final int ic_launcher=android.R.drawable.ic_menu_gallery;} }', encoding='utf-8')
    tests = run / 'src/test/java/app/jmbatch/android'
    tests.mkdir(parents=True)
    shutil.copyfile(ROOT / 'work/jmbatch-android/tests/runtime/src/test/java/app/jmbatch/android/ChapterDeletionRuntimeTest.java', tests / 'ChapterDeletionRuntimeTest.java')
    (tests / 'LargeChapterDeleteProbe.java').write_text(JAVA, encoding='utf-8')
    shutil.copytree(ROOT / 'work/tests/chapter-delete-runtime-ui-final/aar-classes', run / 'aar-classes')
    pom = (ROOT / 'work/jmbatch-android/tests/runtime/pom.xml').read_text(encoding='utf-8')
    (run / 'pom.xml').write_text(pom.replace('${project.basedir}/src/test/java', '${run.dir}/src/test/java'), encoding='utf-8')
    toolchain = ROOT / 'work/android-tools'
    env = os.environ.copy()
    env['JAVA_HOME'] = str(toolchain / 'jdk-17.0.20.1+1')
    env['JAVA_TOOL_OPTIONS'] = '-Dfile.encoding=UTF-8'
    (run / 'temp').mkdir()
    env['TEMP'] = env['TMP'] = str(run / 'temp')
    command = [str(toolchain / 'apache-maven-3.9.9/bin/mvn.cmd'), '-o', '-B', '-ntp', '-f', str(run / 'pom.xml'),
               '-Dmaven.repo.local=' + str(toolchain / 'maven-repository'), '-Dsdk.jar=' + str(toolchain / 'android-35/android.jar'),
               '-Drun.dir=' + str(run), '-Dprobe.report=' + str(report / 'measurement.json'),
               '-Dtest=LargeChapterDeleteProbe#measureLargeFolderInspection', 'test']
    with (report / 'runtime.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
    print((report / 'runtime.log').read_text(encoding='utf-8', errors='replace')[-5000:])
    if result.returncode:
        raise SystemExit(result.returncode)


globals()[args.platform]()
