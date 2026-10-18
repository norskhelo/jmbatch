"""Production batch coordinator with storage doubles; no claim of device/SAF testing."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
stubs = {
    'android/content/Context.java': 'package android.content;public class Context {}',
    'android/net/Uri.java': '''package android.net;public class Uri {String value;private Uri(String v){value=v;}
public static Uri parse(String v){return new Uri(v);}public String toString(){return value;}}''',
    'app/jmbatch/android/AlbumStorage.java': '''package app.jmbatch.android;
public class AlbumStorage {public interface Check {void run()throws Exception;}}''',
    'app/jmbatch/android/LibraryStore.java': '''package app.jmbatch.android;
import android.content.Context;import java.util.*;
public class LibraryStore {public static final LibraryStore INSTANCE=new LibraryStore();
public static boolean fail;public static List<Entry> imported=new ArrayList<>();
public static LibraryStore get(Context c){return INSTANCE;}public void importFound(List<Entry> files)throws Exception{
if(fail)throw new java.io.IOException("catalogue locked");imported.addAll(files);}
public static class Entry {public String uri,format,id,title;public Entry(String u,String f){uri=u;format=f;id=u;title="Comic "+u;}}}''',
    'app/jmbatch/android/AlbumExporter.java': '''package app.jmbatch.android;
import android.content.Context;import android.net.Uri;import java.util.*;import java.util.function.Consumer;
public class AlbumExporter {
public static List<String> calls=new ArrayList<>();public static Set<String> saved=new HashSet<>();
public static boolean cancelInside;
public static List<LibraryStore.Entry> export(Context c,Uri uri,String source,String id,String title,String tree,String label,String fmt,
boolean numeric,boolean flat,boolean split,AlbumStorage.Check check,Consumer<String> progress)throws Exception{
check.run();calls.add(id+":"+source+":"+fmt+":"+numeric+":"+split+":"+tree+":"+label);
if(id.equals("bad"))throw new java.io.IOException("bad source");
if(id.equals("timeout"))throw new java.io.InterruptedIOException("network timeout");
if(id.equals("cancel")&&cancelInside){progress.accept("cancel now");check.run();}
String path=id+"."+fmt;if(saved.contains(path))throw new java.io.IOException("already exists");
List<LibraryStore.Entry> files=new ArrayList<>();for(int i=0;i<(split?2:1);i++)files.add(new LibraryStore.Entry(path+"-"+i,fmt));
saved.add(path);return files;
}}''',
    'BatchExportTest.java': '''import app.jmbatch.android.*;import android.content.Context;
import java.util.*;import java.util.concurrent.atomic.AtomicBoolean;
public class BatchExportTest {
static int checks;static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
static LibraryStore.Entry entry(String id,String fmt){return new LibraryStore.Entry(id,fmt);}
static void reset(){AlbumExporter.calls.clear();AlbumExporter.saved.clear();AlbumExporter.cancelInside=false;LibraryStore.imported.clear();LibraryStore.fail=false;}
static BatchExporter.Result run(List<LibraryStore.Entry> items,String fmt,boolean numeric,boolean split,AtomicBoolean cancel,List<String> messages){
return BatchExporter.export(new Context(),items,"destination","Folder",fmt,numeric,split,cancel::get,m->{messages.add(m);if(m.contains("cancel now"))cancel.set(true);});}
public static void main(String[] args){
List<LibraryStore.Entry> mixed=Arrays.asList(entry("a","images"),entry("b","zip"),entry("c","pdf"));
for(String fmt:Arrays.asList("pdf","zip","images")){
reset();List<String> messages=new ArrayList<>();BatchExporter.Result r=run(mixed,fmt,true,true,new AtomicBoolean(),messages);
check(r.succeeded==3&&r.failed==0&&r.unprocessed==0&&!r.stopped,"all mixed inputs succeed "+fmt);
check(r.files.size()==(fmt.equals("pdf")?5:3),"split output count "+fmt);
check(LibraryStore.imported.equals(r.files),"completed outputs indexed "+fmt);
for(int i=0;i<3;i++)check(AlbumExporter.calls.get(i).equals(mixed.get(i).id+":"+mixed.get(i).format+":"+fmt+":"+!fmt.equals("images")+":"+(fmt.equals("pdf")&&i<2)+":destination:Folder"),"options forwarded per source "+fmt+i);
check(messages.stream().anyMatch(m->m.contains("第 3/3 本 · JMc")),"progress identifies comic "+fmt);
}
reset();List<LibraryStore.Entry> selection=new ArrayList<>(mixed);selection.add(mixed.get(0));
BatchExporter.Result r=BatchExporter.export(new Context(),selection,"","App","zip",false,false,()->false,m->selection.clear());
check(r.succeeded==3&&AlbumExporter.calls.size()==3,"dedup and snapshot before callback");
reset();AlbumExporter.saved.add("a.zip");r=run(Arrays.asList(mixed.get(0),entry("bad","zip"),mixed.get(1)),"zip",false,false,new AtomicBoolean(),new ArrayList<>());
check(r.succeeded==1&&r.failed==2&&r.unprocessed==0,"colliding and broken comics do not stop next");
check(AlbumExporter.saved.equals(new HashSet<>(Arrays.asList("a.zip","b.zip"))),"old output retained and next saved");
check(r.errors.get(0).contains("JMa")&&r.errors.get(1).contains("bad source"),"errors identify each book");
check(LibraryStore.imported.size()==1,"only completed book indexed");
reset();AlbumExporter.cancelInside=true;r=run(Arrays.asList(mixed.get(0),entry("cancel","zip"),mixed.get(2)),"zip",false,false,new AtomicBoolean(),new ArrayList<>());
check(r.succeeded==1&&r.failed==0&&r.unprocessed==2&&r.stopped,"current and remaining unprocessed on cancellation");
check(AlbumExporter.calls.size()==2&&!AlbumExporter.saved.contains("cancel.zip"),"no later export after cancellation");
check(LibraryStore.imported.size()==1&&AlbumExporter.saved.contains("a.zip"),"prior result saved and indexed after cancellation");
check(r.summary().contains("已停止导出")&&r.summary().contains("未处理 2 本"),"cancel summary");
reset();r=run(mixed,"zip",false,false,new AtomicBoolean(true),new ArrayList<>());
check(r.stopped&&r.unprocessed==3&&AlbumExporter.calls.isEmpty()&&LibraryStore.imported.isEmpty(),"cancel before start");
reset();r=run(Arrays.asList(entry("timeout","zip"),mixed.get(1)),"zip",false,false,new AtomicBoolean(),new ArrayList<>());
check(r.failed==1&&r.succeeded==1&&!r.stopped,"IO timeout is failure not user cancellation");
reset();LibraryStore.fail=true;r=run(mixed,"pdf",false,false,new AtomicBoolean(),new ArrayList<>());
check(r.succeeded==3&&r.failed==0&&r.warnings.size()==1,"index error does not misreport saved outputs");
check(AlbumExporter.saved.size()==3&&r.warnings.get(0).contains("文件已保存"),"index error keeps files and explains recovery");
reset();r=run(Collections.emptyList(),"pdf",false,false,new AtomicBoolean(),new ArrayList<>());
check(r.unprocessed==0&&r.files.isEmpty()&&!r.stopped,"empty selection safe");
System.out.println("BatchExportTest: "+checks+" checks passed (production coordinator, storage doubles)");
}}'''
}
for name, source in stubs.items():
    path = out/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source, encoding='utf-8')
jdk = Path(sys.argv[1])/'bin'
classes = out/'classes'; classes.mkdir(exist_ok=True)
subprocess.run([str(jdk/'javac.exe'), '-encoding', 'UTF-8', '-d', str(classes),
                *[str(out/name) for name in stubs],
                str(root/'app/src/main/java/app/jmbatch/android/BatchExporter.java')], check=True)
subprocess.run([str(jdk/'java.exe'), '-cp', str(classes), 'BatchExportTest'], check=True)
source = (root/'app/src/main/java/app/jmbatch/android/LibraryScreen.java').read_text(encoding='utf-8')
assert 'if(!items.isEmpty())new ExportScreen(activity,store,items,this::load)' in source
assert 'batchButtons.addAll(Arrays.asList(export,' in source
screen = (root/'app/src/main/java/app/jmbatch/android/ExportScreen.java').read_text(encoding='utf-8')
assert 'BatchExporter.export(activity,entries,' in screen and 'finally{store.libraryBusy=false;}' in screen
assert 'progress.getButton(DialogInterface.BUTTON_NEGATIVE).setOnClickListener' in screen
assert 'if(store.running||store.libraryBusy)' in screen and 'finished.run()' in screen
print('Batch export multi-selection, download guard, stop and refresh wiring verified')
