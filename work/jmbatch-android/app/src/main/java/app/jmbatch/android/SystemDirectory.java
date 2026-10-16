package app.jmbatch.android;

import android.app.Activity;
import android.content.*;
import android.content.pm.*;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.util.*;

/** Native file-manager launch; DocumentsUI is an explicit fallback only. */
final class SystemDirectory {
    static final int UNAVAILABLE=0, DIRECTORY=1, HOME=2;
    static Intent directory(Uri document) {
        Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(document,DocumentsContract.Document.MIME_TYPE_DIR)
            .putExtra(DocumentsContract.EXTRA_INITIAL_URI,document).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.setClipData(ClipData.newRawUri("保存目录",document));
        return intent;
    }
    static Intent picker(Uri document) {
        return new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
            .putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/pdf","application/zip"})
            .putExtra(DocumentsContract.EXTRA_INITIAL_URI,document);
    }
    static boolean open(Activity activity,Intent intent,boolean directory) {
        return DirectoryTargets.open(targets(activity,intent,directory,Collections.emptySet()),
            component->activity.startActivity(new Intent(intent).setComponent(ComponentName.unflattenFromString(component))));
    }
    static int openFileManager(Activity activity,Uri document) {
        PackageManager pm=activity.getPackageManager();
        Set<String> packages=new LinkedHashSet<>(DirectoryTargets.LEGACY_MANAGERS);
        // Query the native file-app category, then use its real launcher intent.
        try {
            Intent files=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_APP_FILES);
            for(ResolveInfo resolved:pm.queryIntentActivities(files,0)) {
                ActivityInfo info=resolved.activityInfo;
                if(info!=null&&!DirectoryTargets.documentsUi(info.packageName,info.name))packages.add(info.packageName);
            }
        } catch(RuntimeException ignored) { /* Try the legacy and directory handlers. */ }
        Intent folder=directory(document);
        if(DirectoryTargets.openManagers(targets(activity,folder,true,packages),
                component->activity.startActivity(new Intent(folder).setComponent(ComponentName.unflattenFromString(component)))))return DIRECTORY;
        List<DirectoryTargets.Target> homes=new ArrayList<>();
        Map<String,Intent> intents=new HashMap<>();
        for(String name:packages)try {
            if(name.equals(activity.getPackageName()))continue;
            Intent launch=pm.getLaunchIntentForPackage(name);
            if(launch==null)continue;
            ResolveInfo resolved=pm.resolveActivity(launch,0);
            if(resolved==null||resolved.activityInfo==null)continue;
            ActivityInfo info=resolved.activityInfo;
            DirectoryTargets.Target target=target(activity,info,true,DirectoryTargets.documentsUi(info.packageName,info.name));
            homes.add(target);
            // A launcher may ignore the initial URI. Callers report HOME, never a successful directory jump.
            Intent home=new Intent(launch).setComponent(new ComponentName(info.packageName,info.name))
                .putExtra(DocumentsContract.EXTRA_INITIAL_URI,document)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            home.setClipData(ClipData.newRawUri("保存目录",document));
            intents.put(target.component,home);
        } catch(RuntimeException ignored) { /* One missing/restricted package must not block the others. */ }
        return DirectoryTargets.openManagers(homes,component->activity.startActivity(intents.get(component)))?HOME:UNAVAILABLE;
    }
    private static DirectoryTargets.Target target(Activity activity,ActivityInfo info,boolean supported,boolean documents) {
        ApplicationInfo app=info.applicationInfo;
        boolean system=app!=null&&(app.flags&(ApplicationInfo.FLAG_SYSTEM|ApplicationInfo.FLAG_UPDATED_SYSTEM_APP))!=0;
        boolean permission=info.permission==null||activity.checkSelfPermission(info.permission)==PackageManager.PERMISSION_GRANTED;
        return new DirectoryTargets.Target(new ComponentName(info.packageName,info.name).flattenToString(),system,
            info.enabled&&app!=null&&app.enabled&&permission,info.exported,supported,documents);
    }
    private static List<DirectoryTargets.Target> targets(Activity activity,Intent intent,boolean directory,Set<String> managers) {
        PackageManager pm=activity.getPackageManager();
        List<DirectoryTargets.Target> candidates=new ArrayList<>();
        try {
            for(ResolveInfo resolved:pm.queryIntentActivities(intent,PackageManager.MATCH_DEFAULT_ONLY|PackageManager.GET_RESOLVED_FILTER)) {
                ActivityInfo info=resolved.activityInfo;
                if(info==null||info.applicationInfo==null||activity.getPackageName().equals(info.packageName))continue;
                boolean managesDocuments=pm.checkPermission("android.permission.MANAGE_DOCUMENTS",info.packageName)==PackageManager.PERMISSION_GRANTED;
                boolean documents=DirectoryTargets.documentsUi(info.packageName,info.name)||
                    (managesDocuments&&!managers.contains(info.packageName));
                boolean exactDirectory=false;
                Iterator<String> types=resolved.filter==null?null:resolved.filter.typesIterator();
                while(types!=null&&types.hasNext())if(DocumentsContract.Document.MIME_TYPE_DIR.equals(types.next()))exactDirectory=true;
                // Generic wildcard viewers are not evidence of folder navigation support.
                boolean supported=!directory||managesDocuments||exactDirectory;
                candidates.add(target(activity,info,supported,documents));
            }
        } catch(RuntimeException unavailable) { /* Keep any candidates already discovered. */ }
        return candidates;
    }
    private SystemDirectory() {}
}
