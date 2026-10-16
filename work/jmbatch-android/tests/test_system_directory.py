"""Run the real native-intent dispatcher against a small fake Android package manager.

This verifies intent construction and fallback order, not OEM UI behavior on a phone.
"""
from pathlib import Path
import subprocess
import sys

source = Path(__file__).resolve().parents[1] / 'app/src/main/java/app/jmbatch/android'
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
stubs = {
'android/net/Uri.java': '''package android.net; public class Uri {}''',
'android/content/ComponentName.java': '''package android.content;
public class ComponentName { public String pkg,name; public ComponentName(String p,String n){pkg=p;name=n;}
public String flattenToString(){return pkg+"/"+name;}
public static ComponentName unflattenFromString(String s){String[] a=s.split("/",2);return new ComponentName(a[0],a[1]);}}''',
'android/content/ClipData.java': '''package android.content; import android.net.Uri;
public class ClipData {public Uri uri; public static ClipData newRawUri(String s,Uri u){ClipData c=new ClipData();c.uri=u;return c;}}''',
'android/content/Intent.java': '''package android.content; import android.net.Uri; import java.util.*;
public class Intent {
public static final String ACTION_MAIN="MAIN",ACTION_VIEW="VIEW",ACTION_OPEN_DOCUMENT="OPEN",CATEGORY_APP_FILES="APP_FILES",CATEGORY_OPENABLE="OPENABLE",EXTRA_MIME_TYPES="MIME";
public static final int FLAG_GRANT_READ_URI_PERMISSION=1;
public String action,type;public Uri data;public ComponentName component;public ClipData clip;public int flags;
public Map<String,Object> extras=new HashMap<>();public Set<String> categories=new HashSet<>();
public Intent(String a){action=a;} public Intent(Intent i){action=i.action;type=i.type;data=i.data;component=i.component;clip=i.clip;flags=i.flags;extras.putAll(i.extras);categories.addAll(i.categories);}
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
public List<ResolveInfo> folders=new ArrayList<>(),files=new ArrayList<>();public Map<String,ResolveInfo> homes=new HashMap<>();
public Set<String> managers=new HashSet<>(); public boolean queryFailure;
public List<ResolveInfo> queryIntentActivities(Intent i,int flags){if(queryFailure)throw new SecurityException();return i.action.equals(Intent.ACTION_MAIN)?files:folders;}
public int checkPermission(String p,String pkg){return managers.contains(pkg)?0:-1;}
public Intent getLaunchIntentForPackage(String pkg){ResolveInfo r=homes.get(pkg);return r==null?null:new Intent(Intent.ACTION_MAIN).setComponent(new ComponentName(pkg,r.activityInfo.name));}
public ResolveInfo resolveActivity(Intent i,int flags){return homes.get(i.component.pkg);}}
''',
'android/provider/DocumentsContract.java': '''package android.provider;public class DocumentsContract {
public static final String EXTRA_INITIAL_URI="INITIAL_URI";
public static class Document {public static final String MIME_TYPE_DIR="vnd.android.document/directory";}}''',
'android/app/Activity.java': '''package android.app;import android.content.*;import android.content.pm.*;import java.util.*;
public class Activity {public PackageManager pm=new PackageManager();public List<Intent> launched=new ArrayList<>();public Set<String> rejected=new HashSet<>();
public PackageManager getPackageManager(){return pm;}public String getPackageName(){return "app.jmbatch.android";}
public int checkSelfPermission(String p){return -1;}
public void startActivity(Intent i){if(rejected.contains(i.component.flattenToString()))throw new SecurityException();launched.add(i);}}''',
'app/jmbatch/android/SystemDirectoryHostTest.java': '''package app.jmbatch.android;
import android.app.*;import android.content.*;import android.content.pm.*;import android.net.Uri;import android.provider.DocumentsContract;
public class SystemDirectoryHostTest {
static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("native dispatcher "+checks);}
static ResolveInfo app(String pkg,String name,boolean system,String mime){ResolveInfo r=new ResolveInfo();r.activityInfo=new ActivityInfo();r.activityInfo.packageName=pkg;r.activityInfo.name=name;r.activityInfo.applicationInfo.flags=system?1:0;r.filter.mime=mime;return r;}
static final String DIR=DocumentsContract.Document.MIME_TYPE_DIR;
static Activity base(){Activity a=new Activity();a.pm.folders.add(app("com.android.documentsui","Files",true,DIR));a.pm.managers.add("com.android.documentsui");return a;}
public static void main(String[] args){
Uri uri=new Uri();Activity a=base();ResolveInfo h=app("com.huawei.hidisk","Home",true,null);a.pm.homes.put(h.activityInfo.packageName,h);
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);
Intent i=a.launched.get(0);check(i.component.pkg.equals("com.huawei.hidisk"));check(i.action.equals(Intent.ACTION_MAIN));
check(i.extras.get(DocumentsContract.EXTRA_INITIAL_URI)==uri);check(i.clip.uri==uri);check(i.flags==Intent.FLAG_GRANT_READ_URI_PERMISSION);
a=base();a.pm.folders.add(app("com.huawei.hidisk","Folder",true,DIR));a.pm.homes.put(h.activityInfo.packageName,h);a.pm.managers.add("com.huawei.hidisk");
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.DIRECTORY);i=a.launched.get(0);check(i.component.name.equals("Folder"));check(i.data==uri&&i.type.equals(DIR));check(i.clip.uri==uri&&i.flags==1);
a=base();a.pm.folders.add(app("com.huawei.hidisk","Folder",true,DIR));a.pm.homes.put(h.activityInfo.packageName,h);a.rejected.add("com.huawei.hidisk/Folder");
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);check(a.launched.get(0).component.name.equals("Home"));
a=base();check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);check(a.launched.isEmpty());
check(SystemDirectory.open(a,SystemDirectory.directory(uri),true));check(a.launched.get(0).component.pkg.equals("com.android.documentsui"));
a=base();ResolveInfo generic=app("vendor.nativefiles","Home",true,null);a.pm.files.add(generic);a.pm.homes.put("vendor.nativefiles",generic);
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);check(a.launched.get(0).component.pkg.equals("vendor.nativefiles"));
a=base();ResolveInfo docs=app("com.google.android.documentsui","Home",true,null);a.pm.files.add(docs);a.pm.homes.put(docs.activityInfo.packageName,docs);
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);check(a.launched.isEmpty());
a=base();h=app("com.huawei.hidisk","Home",false,null);a.pm.homes.put(h.activityInfo.packageName,h);
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);check(a.launched.isEmpty());
h.activityInfo.applicationInfo.flags=2;h.activityInfo.exported=false;check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
h.activityInfo.exported=true;h.activityInfo.permission="restricted";check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
h.activityInfo.permission=null;h.activityInfo.applicationInfo.enabled=false;check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
h.activityInfo.applicationInfo.enabled=true;a.pm.queryFailure=true;check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.HOME);
a=base();ResolveInfo viewer=app("vendor.viewer","Generic",true,"*/*");a.pm.folders.add(viewer);
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.UNAVAILABLE);
a=base();ResolveInfo folder=app("vendor.nativefiles","Folder",true,DIR);a.pm.folders.add(folder);a.pm.files.add(folder);a.pm.managers.add("vendor.nativefiles");
check(SystemDirectory.openFileManager(a,uri)==SystemDirectory.DIRECTORY);
System.out.println("SystemDirectoryHostTest: "+checks+" checks passed (fake Android framework, no device)");}}
''',
}
paths=[]
for name, content in stubs.items():
    path=out/'stubs'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8');paths.append(str(path))
jdk=Path(sys.argv[1]);classes=out/'classes';classes.mkdir(exist_ok=True)
subprocess.run([str(jdk/'bin/javac.exe'),'-encoding','UTF-8','-d',str(classes),*paths,str(source/'DirectoryTargets.java'),str(source/'SystemDirectory.java')],check=True)
subprocess.run([str(jdk/'bin/java.exe'),'-cp',str(classes),'app.jmbatch.android.SystemDirectoryHostTest'],check=True)
