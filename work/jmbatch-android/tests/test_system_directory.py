"""Run the real native-intent dispatcher against a small fake Android package manager.

This verifies intent construction and fallback order, not OEM UI behavior on a phone.
"""
from pathlib import Path
import subprocess
import sys

source = Path(__file__).resolve().parents[1] / 'app/src/main/java/app/jmbatch/android'
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
stubs = {
'android/net/Uri.java': '''package android.net; public class Uri {public String authority="local",tree,document;public String getAuthority(){return authority;}
public static class Builder {Uri u=new Uri();public Builder scheme(String s){return this;}public Builder authority(String a){u.authority=a;return this;}public Builder appendPath(String p){return this;}public Uri build(){return u;}}}''',
'android/content/ComponentName.java': '''package android.content;
public class ComponentName { public String pkg,name; public ComponentName(String p,String n){pkg=p;name=n;}
public String getPackageName(){return pkg;} public String flattenToString(){return pkg+"/"+name;}
public static ComponentName unflattenFromString(String s){String[] a=s.split("/",2);return new ComponentName(a[0],a[1]);}}''',
'android/content/ClipData.java': '''package android.content; import android.net.Uri;
public class ClipData {public Uri uri; public static ClipData newRawUri(String s,Uri u){ClipData c=new ClipData();c.uri=u;return c;}}''',
'android/content/Intent.java': '''package android.content; import android.net.Uri; import java.util.*;
public class Intent {
public static final String ACTION_MAIN="MAIN",ACTION_VIEW="VIEW",ACTION_OPEN_DOCUMENT="OPEN",CATEGORY_APP_FILES="APP_FILES",CATEGORY_OPENABLE="OPENABLE",EXTRA_MIME_TYPES="MIME",CATEGORY_LAUNCHER="LAUNCHER",EXTRA_INITIAL_INTENTS="INITIAL_INTENTS",EXTRA_INTENT="INTENT";
public static final int FLAG_GRANT_READ_URI_PERMISSION=1,FLAG_GRANT_PREFIX_URI_PERMISSION=128;
public Intent selector;public String action,type;public Uri data;public ComponentName component;public ClipData clip;public int flags;
public Map<String,Object> extras=new HashMap<>();public Set<String> categories=new HashSet<>();
public Intent(String a){action=a;} public Intent(Intent i){selector=i.selector==null?null:new Intent(i.selector);action=i.action;type=i.type;data=i.data;component=i.component;clip=i.clip;flags=i.flags;extras.putAll(i.extras);categories.addAll(i.categories);}
public String getAction(){return action;} public void setSelector(Intent i){selector=i;}
public static Intent makeMainSelectorActivity(String action,String category){Intent i=new Intent(ACTION_MAIN).addCategory(CATEGORY_LAUNCHER);i.selector=new Intent(action).addCategory(category);return i;}
public static Intent createChooser(Intent i,String title){return new Intent("CHOOSER").putExtra(EXTRA_INTENT,i);}
public Intent setDataAndType(Uri u,String t){data=u;type=t;return this;}
public Intent putExtra(String k,Object v){extras.put(k,v);return this;}
public Intent addFlags(int f){flags|=f;return this;} public void setClipData(ClipData c){clip=c;}
public Intent setComponent(ComponentName c){component=c;return this;}
public Intent addCategory(String c){categories.add(c);return this;} public Intent setType(String t){type=t;return this;}}
''',
'android/content/IntentFilter.java': '''package android.content;import java.util.*;
public class IntentFilter {public String mime;public Iterator<String> typesIterator(){return Collections.singletonList(mime).iterator();}}''',
'android/content/pm/ApplicationInfo.java': '''package android.content.pm;
public class ApplicationInfo {public static final int FLAG_SYSTEM=1,FLAG_UPDATED_SYSTEM_APP=2;public int flags=1;public boolean enabled=true;}''',
'android/content/pm/ActivityInfo.java': '''package android.content.pm;
public class ActivityInfo {public ApplicationInfo applicationInfo=new ApplicationInfo();public String packageName,name,permission;public boolean enabled=true,exported=true;}''',
'android/content/pm/ResolveInfo.java': '''package android.content.pm; import android.content.IntentFilter;
public class ResolveInfo {public ActivityInfo activityInfo;public IntentFilter filter=new IntentFilter();}''',
'android/content/pm/PackageManager.java': '''package android.content.pm; import android.content.*;import java.util.*;
public class PackageManager {
public static final int MATCH_DEFAULT_ONLY=1,GET_RESOLVED_FILTER=2,PERMISSION_GRANTED=0;
public List<ResolveInfo> folders=new ArrayList<>(),files=new ArrayList<>();public ResolveInfo preferred;
public boolean queryFailure,mainFailure;public int launcherCalls;
public List<ResolveInfo> queryIntentActivities(Intent i,int flags){
if(queryFailure||(mainFailure&&i.action.equals(Intent.ACTION_MAIN)))throw new SecurityException();
if(i.action.equals(Intent.ACTION_MAIN)){
if(i.selector==null||!i.selector.categories.contains(Intent.CATEGORY_APP_FILES)||!i.categories.contains(Intent.CATEGORY_LAUNCHER))throw new AssertionError("native selector required");
if((flags&MATCH_DEFAULT_ONLY)!=0)throw new AssertionError("main must not require DEFAULT");return files;}
return folders;}
public int checkPermission(String p,String pkg){return 0;} // A permission alone must not qualify wildcard viewers.
public Intent getLaunchIntentForPackage(String pkg){launcherCalls++;throw new AssertionError("package front door forbidden");}
public ResolveInfo resolveActivity(Intent i,int flags){return preferred;}}
''',
'android/provider/DocumentsContract.java': '''package android.provider;public class DocumentsContract {
public static final String EXTRA_INITIAL_URI="INITIAL_URI";
public static boolean isTreeUri(android.net.Uri u){return u.tree!=null;}
public static String getTreeDocumentId(android.net.Uri u){return u.tree;}
public static android.net.Uri buildTreeDocumentUri(String a,String id){android.net.Uri u=new android.net.Uri();u.authority=a;u.tree=id;return u;}
public static android.net.Uri buildDocumentUriUsingTree(android.net.Uri tree,String id){android.net.Uri u=buildTreeDocumentUri(tree.authority,tree.tree);u.document=id;return u;}
public static class Root {public static final int FLAG_LOCAL_ONLY=1,FLAG_SUPPORTS_IS_CHILD=2;}
public static class Path {public Path(String root,java.util.List<String> path){}}
public static class Document {public static final String MIME_TYPE_DIR="vnd.android.document/directory";}}''',
'android/app/Activity.java': '''package android.app;import android.content.*;import android.content.pm.*;import java.util.*;
public class Activity {public PackageManager pm=new PackageManager();public List<Intent> launched=new ArrayList<>();public Set<String> rejected=new HashSet<>();
public PackageManager getPackageManager(){return pm;}public String getPackageName(){return "app.jmbatch.android";}
public int checkSelfPermission(String p){return -1;}
public void startActivity(Intent i){if(i.component!=null&&rejected.contains(i.component.flattenToString()))throw new SecurityException();launched.add(i);}}''',
'app/jmbatch/android/SystemDirectoryHostTest.java': '''package app.jmbatch.android;
import android.app.*;import android.content.*;import android.content.pm.*;import android.net.Uri;import android.provider.DocumentsContract;
public class SystemDirectoryHostTest {
static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("native dispatcher "+checks);}
static ResolveInfo app(String pkg,String name,boolean system,String mime){ResolveInfo r=new ResolveInfo();r.activityInfo=new ActivityInfo();r.activityInfo.packageName=pkg;r.activityInfo.name=name;r.activityInfo.applicationInfo.flags=system?1:0;r.filter.mime=mime;return r;}
static final String DIR=DocumentsContract.Document.MIME_TYPE_DIR;
static Activity base(){Activity a=new Activity();a.pm.folders.add(app("com.android.documentsui","Picker",true,DIR));return a;}
static ResolveInfo nativeApp(Activity a,String pkg,String name){ResolveInfo r=app(pkg,name,true,null);a.pm.files.add(r);return r;}
public static void main(String[] args)throws Exception{
Uri uri=new Uri();Activity a=base();
// Regression: Cloud advertises both categories and is even the OS default. It is never launched.
ResolveInfo cloud=nativeApp(a,"com.huawei.hidisk","Cloud");a.pm.preferred=cloud;a.pm.folders.add(app("com.huawei.hidisk","Folder",true,DIR));
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);check(a.launched.isEmpty());
ResolveInfo local=nativeApp(a,"vendor.files","ActualFileActivity");
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);
Intent i=a.launched.get(0);check(i.component.pkg.equals("vendor.files"));check(i.component.name.equals("ActualFileActivity"));
check(i.action.equals(Intent.ACTION_MAIN)&&i.categories.contains(Intent.CATEGORY_LAUNCHER)&&i.selector==null);
check(i.extras.isEmpty()&&i.clip==null&&i.flags==0&&i.data==null);check(a.pm.launcherCalls==0);
// An actual native files component supporting folder VIEW receives the document, not MAIN or picker.
a=base();nativeApp(a,"vendor.files","Home");a.pm.folders.add(app("vendor.files","Folder",true,DIR));
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.DIRECTORY);i=a.launched.get(0);
check(i.component.name.equals("Folder")&&i.action.equals(Intent.ACTION_VIEW));check(i.data==uri&&i.type.equals(DIR));
check(i.clip.uri==uri&&i.flags==1&&i.extras.isEmpty());
a.rejected.add("vendor.files/Folder");a.launched.clear();
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);check(a.launched.get(0).component.name.equals("Home"));
// Real native AOSP Files is valid; a stand-alone document picker remains manual.
a=base();check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
check(SystemDirectory.open(a,SystemDirectory.directory(uri),true));check(a.launched.get(0).component.name.equals("Picker"));
a=new Activity();nativeApp(a,"com.android.documentsui","Files");a.pm.folders.add(app("com.android.documentsui","Files",true,DIR));
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.DIRECTORY);check(a.launched.get(0).component.name.equals("Files"));
a.pm.folders.clear();check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);
// Wildcard and MANAGE_DOCUMENTS permission are insufficient evidence of folder support.
a=base();a.pm.folders.add(app("vendor.viewer","Generic",true,"*/*"));
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
nativeApp(a,"vendor.viewer","Home");check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);
// Older systems without APP_FILES can still expose a matching directory VIEW handler.
a=base();a.pm.mainFailure=true;a.pm.folders.add(app("vendor.files","Folder",true,DIR));
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.DIRECTORY);
a=base();a.pm.queryFailure=true;check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
// Component eligibility and fallback after startActivity failure.
a=base();ResolveInfo bad=nativeApp(a,"vendor.files","Home");bad.activityInfo.applicationInfo.flags=0;
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
bad.activityInfo.applicationInfo.flags=2;bad.activityInfo.exported=false;check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
bad.activityInfo.exported=true;bad.activityInfo.permission="restricted";check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
bad.activityInfo.permission=null;bad.activityInfo.applicationInfo.enabled=false;check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
bad.activityInfo.applicationInfo.enabled=true;bad.activityInfo.enabled=false;check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
bad.activityInfo.enabled=true;a.rejected.add("vendor.files/Home");nativeApp(a,"vendor.other","Home");a.pm.preferred=bad;
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);check(a.launched.get(0).component.pkg.equals("vendor.other"));
a=base();nativeApp(a,"app.jmbatch.android","Home");check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
// OS default is honored only when it is an actual eligible native candidate.
a=base();nativeApp(a,"a.files","Home");a.pm.preferred=nativeApp(a,"z.files","Home");
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);check(a.launched.get(0).component.pkg.equals("z.files"));
a.launched.clear();a.pm.preferred=app("android","ResolverActivity",true,null);
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);check(a.launched.get(0).component.pkg.equals("a.files"));
// SAF subtree grants preserve the target document; read-only, never write or persistable grants.
Uri tree=new Uri();tree.tree="primary:Comics";tree.authority="external.storage";i=SystemDirectory.directory(tree);
check(i.data==tree&&i.flags==129);check(i.clip.uri!=tree&&i.clip.uri.tree.equals("primary:Comics")&&i.clip.uri.authority.equals(tree.authority));
check(SystemDirectory.picker(tree).extras.get(DocumentsContract.EXTRA_INITIAL_URI)==tree);
// The chooser also excludes Cloud and generic viewers but allows explicitly selected third-party folders.
a=new Activity();a.pm.folders.add(app("com.huawei.hidisk","Cloud",true,DIR));
check(!SystemDirectory.choose(a,uri));check(!SystemDirectory.open(a,SystemDirectory.directory(uri),true));
a.pm.folders.add(app("third.party","Folder",false,DIR));a.pm.folders.add(app("vendor.files","Folder",true,DIR));a.pm.folders.add(app("wildcard","Viewer",true,"*/*"));
check(SystemDirectory.choose(a,tree));i=a.launched.get(0);check(i.action.equals("CHOOSER"));
Intent first=(Intent)i.extras.get(Intent.EXTRA_INTENT);Intent[] more=(Intent[])i.extras.get(Intent.EXTRA_INITIAL_INTENTS);
check(first.component!=null&&!first.component.pkg.equals("com.huawei.hidisk")&&first.data==tree&&first.flags==129);
check(more.length==1&&more[0].component.pkg.equals("vendor.files")&&more[0].data==tree&&more[0].flags==129);
// Exercise the real provider's root/subdirectory URI helpers with isolated local directories.
android.content.Context context=new android.content.Context();
AlbumStorage.root=new java.io.File(args[0],"exports").getAbsoluteFile();
java.io.File child=new java.io.File(AlbumStorage.root,"漫画 1/第1章");check(child.mkdirs()||child.isDirectory());
AlbumStorage.checked=child;Uri root=ExportDocumentsProvider.folder(context);
check(root.tree.equals("exports")&&root.document.equals("exports"));check(root.authority.equals("app.jmbatch.android.documents"));
Uri nested=ExportDocumentsProvider.folder(context,child);
check(nested.tree.equals("file:漫画 1/第1章")&&nested.document.equals(nested.tree));
i=SystemDirectory.directory(nested);check(i.data==nested&&i.clip.uri.tree.equals(nested.tree)&&i.flags==129);
AlbumStorage.checked=null;boolean denied=false;try{ExportDocumentsProvider.folder(context,child);}catch(java.io.IOException e){denied=true;}check(denied);
denied=false;try{ExportDocumentsProvider.folder(context,null);}catch(java.io.IOException e){denied=true;}check(denied);
System.out.println("SystemDirectoryHostTest: "+checks+" checks passed (fake Android framework, no device)");}}
''',
}
# Framework/storage doubles only model URI fields and helper responses, not Android permission enforcement.
stubs.update({
'android/content/Context.java': 'package android.content;public class Context {public String getPackageName(){return "app.jmbatch.android";}}',
'android/database/Cursor.java': 'package android.database;public interface Cursor {}',
'android/database/MatrixCursor.java': 'package android.database;public class MatrixCursor implements Cursor {String[] cols;public MatrixCursor(String[] c){cols=c;}public int getColumnCount(){return cols.length;}public String getColumnName(int i){return cols[i];}public void addRow(Object[] r){}}',
'android/os/CancellationSignal.java': 'package android.os;public class CancellationSignal {public void throwIfCanceled(){}}',
'android/os/ParcelFileDescriptor.java': 'package android.os;public class ParcelFileDescriptor {public static final int MODE_READ_ONLY=1;public static ParcelFileDescriptor open(java.io.File f,int mode){return new ParcelFileDescriptor();}}',
'android/provider/DocumentsProvider.java': 'package android.provider;public class DocumentsProvider {public android.content.Context getContext(){return new android.content.Context();}public DocumentsContract.Path findDocumentPath(String p,String c)throws java.io.FileNotFoundException{return null;}}',
'app/jmbatch/android/R.java': 'package app.jmbatch.android;public class R {public static class drawable {public static final int ic_launcher=1;}}',
'app/jmbatch/android/AlbumStorage.java': 'package app.jmbatch.android;public class AlbumStorage {public static java.io.File root,checked;public static java.io.File root(android.content.Context c){return root;}public static java.io.File local(android.content.Context c,android.net.Uri u)throws java.io.IOException{return checked;}}',
'app/jmbatch/android/ExportProvider.java': 'package app.jmbatch.android;public class ExportProvider {public static android.net.Uri uri(android.content.Context c,java.io.File f){return new android.net.Uri();}}',
'app/jmbatch/android/LibraryRules.java': 'package app.jmbatch.android;public class LibraryRules {public static boolean supported(String name){return name.endsWith(".pdf")||name.endsWith(".zip");}}',
})
paths=[]
for name, content in stubs.items():
    path=out/'stubs'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8');paths.append(str(path))
jdk=Path(sys.argv[1]);classes=out/'classes';classes.mkdir(exist_ok=True)
subprocess.run([str(jdk/'bin/javac.exe'),'-encoding','UTF-8','-d',str(classes),*paths,str(source/'DirectoryTargets.java'),str(source/'SystemDirectory.java'),str(source/'ExportDocumentsProvider.java')],check=True)
subprocess.run([str(jdk/'bin/java.exe'),'-cp',str(classes),'app.jmbatch.android.SystemDirectoryHostTest',str(out/'data')],check=True)
