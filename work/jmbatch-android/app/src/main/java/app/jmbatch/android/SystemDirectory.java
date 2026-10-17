package app.jmbatch.android;

import android.app.Activity;
import android.content.*;
import android.content.pm.*;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.util.*;

/** Resolve actual native file activities, never an assumed vendor package front door. */
final class SystemDirectory {
    static final int UNAVAILABLE=0, DIRECTORY=1, HOME=2;
    static Intent directory(Uri document) {
        Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(document,DocumentsContract.Document.MIME_TYPE_DIR)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        Uri grant=document;
        if(DocumentsContract.isTreeUri(document)) {
            grant=DocumentsContract.buildTreeDocumentUri(document.getAuthority(),DocumentsContract.getTreeDocumentId(document));
            intent.addFlags(Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        }
        intent.setClipData(ClipData.newRawUri("保存目录",grant));
        return intent;
    }
    static Intent picker(Uri document) {
        return new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
            .putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/pdf","application/zip"})
            .putExtra(DocumentsContract.EXTRA_INITIAL_URI,document);
    }
    static boolean open(Activity activity,Intent intent,boolean directory) {
        return DirectoryTargets.open(targets(activity,intent,directory),component->start(activity,intent,component));
    }
    static boolean choose(Activity activity,Uri document) {
        Intent folder=directory(document);
        List<Intent> choices=new ArrayList<>();
        Set<String> seen=new HashSet<>();
        for(DirectoryTargets.Target target:DirectoryTargets.ordered(targets(activity,folder,true),false,false,null))
            if(seen.add(target.component))choices.add(new Intent(folder).setComponent(ComponentName.unflattenFromString(target.component)));
        if(choices.isEmpty())return false;
        // Explicit filtered entries prevent Cloud re-entering through an implicit base intent.
        Intent chooser=Intent.createChooser(choices.remove(0),"选择文件管理器");
        if(!choices.isEmpty())chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS,choices.toArray(new Intent[0]));
        try { activity.startActivity(chooser);return true; }
        catch(RuntimeException unavailable) { return false; }
    }
    static int openFileManager(Activity activity,Uri document) {
        Intent files=Intent.makeMainSelectorActivity(Intent.ACTION_MAIN,Intent.CATEGORY_APP_FILES);
        List<DirectoryTargets.Target> homes=targets(activity,files,false);
        Set<String> packages=new HashSet<>();
        for(DirectoryTargets.Target target:DirectoryTargets.ordered(homes,true,false,null))
            packages.add(ComponentName.unflattenFromString(target.component).getPackageName());
        String preferred=null;
        try {
            ResolveInfo resolved=activity.getPackageManager().resolveActivity(files,0);
            if(resolved!=null&&resolved.activityInfo!=null)
                preferred=new ComponentName(resolved.activityInfo.packageName,resolved.activityInfo.name).flattenToString();
        } catch(RuntimeException ignored) { /* Still try individually matching apps. */ }
        Intent folder=directory(document);
        List<DirectoryTargets.Target> folders=targets(activity,folder,true),nativeFolders=new ArrayList<>();
        for(DirectoryTargets.Target target:folders)
            if(packages.contains(ComponentName.unflattenFromString(target.component).getPackageName()))nativeFolders.add(target);
        // Native Files (including AOSP Files) must explicitly accept directory VIEW to jump.
        if(DirectoryTargets.openNative(nativeFolders,preferred,component->start(activity,folder,component)))return DIRECTORY;
        // Older systems may advertise directory VIEW without the API 29 file-app category.
        List<DirectoryTargets.Target> others=new ArrayList<>();
        for(DirectoryTargets.Target target:folders)if(!nativeFolders.contains(target))others.add(target);
        if(DirectoryTargets.openManagers(others,component->start(activity,folder,component)))return DIRECTORY;
        return DirectoryTargets.openNative(homes,preferred,component->start(activity,files,component))?HOME:UNAVAILABLE;
    }
    private static void start(Activity activity,Intent intent,String component) {
        Intent explicit=new Intent(intent);
        // Resolve via APP_FILES, then deliver normal MAIN/LAUNCHER to that exact activity.
        explicit.setSelector(null);
        activity.startActivity(explicit.setComponent(ComponentName.unflattenFromString(component)));
    }
    private static DirectoryTargets.Target target(Activity activity,ActivityInfo info,boolean supported) {
        ApplicationInfo app=info.applicationInfo;
        boolean system=app!=null&&(app.flags&(ApplicationInfo.FLAG_SYSTEM|ApplicationInfo.FLAG_UPDATED_SYSTEM_APP))!=0;
        boolean permission=info.permission==null||activity.checkSelfPermission(info.permission)==PackageManager.PERMISSION_GRANTED;
        return new DirectoryTargets.Target(new ComponentName(info.packageName,info.name).flattenToString(),system,
            info.enabled&&app!=null&&app.enabled&&permission,info.exported,supported,DirectoryTargets.documentsUi(info.packageName,info.name));
    }
    private static List<DirectoryTargets.Target> targets(Activity activity,Intent intent,boolean directory) {
        List<DirectoryTargets.Target> candidates=new ArrayList<>();
        // MAIN category filters need not declare CATEGORY_DEFAULT.
        int flags=PackageManager.GET_RESOLVED_FILTER|(Intent.ACTION_MAIN.equals(intent.getAction())?0:PackageManager.MATCH_DEFAULT_ONLY);
        try {
            for(ResolveInfo resolved:activity.getPackageManager().queryIntentActivities(intent,flags)) {
                ActivityInfo info=resolved.activityInfo;
                if(info==null||info.applicationInfo==null||activity.getPackageName().equals(info.packageName))continue;
                boolean exactDirectory=false;
                Iterator<String> types=resolved.filter==null?null:resolved.filter.typesIterator();
                while(types!=null&&types.hasNext())if(DocumentsContract.Document.MIME_TYPE_DIR.equals(types.next()))exactDirectory=true;
                // MANAGE_DOCUMENTS or a wildcard MIME filter alone proves no navigation support.
                candidates.add(target(activity,info,!directory||exactDirectory));
            }
        } catch(RuntimeException unavailable) { /* Keep candidates already discovered. */ }
        return candidates;
    }
    private SystemDirectory() {}
}
