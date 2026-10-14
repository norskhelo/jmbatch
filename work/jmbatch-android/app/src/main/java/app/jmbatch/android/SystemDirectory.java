package app.jmbatch.android;

import android.app.Activity;
import android.content.*;
import android.content.pm.*;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.util.*;

/** Resolve the directory intent itself, never the file manager's home/launcher activity. */
final class SystemDirectory {
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
        PackageManager pm=activity.getPackageManager();
        List<DirectoryTargets.Target> candidates=new ArrayList<>();
        try {
            for(ResolveInfo resolved:pm.queryIntentActivities(intent,PackageManager.MATCH_DEFAULT_ONLY|PackageManager.GET_RESOLVED_FILTER)) {
                ActivityInfo info=resolved.activityInfo;
                if(info==null||info.applicationInfo==null||activity.getPackageName().equals(info.packageName))continue;
                boolean system=(info.applicationInfo.flags&(ApplicationInfo.FLAG_SYSTEM|ApplicationInfo.FLAG_UPDATED_SYSTEM_APP))!=0;
                boolean documents=pm.checkPermission("android.permission.MANAGE_DOCUMENTS",info.packageName)==PackageManager.PERMISSION_GRANTED;
                boolean exactDirectory=false;
                Iterator<String> types=resolved.filter==null?null:resolved.filter.typesIterator();
                while(types!=null&&types.hasNext())if(DocumentsContract.Document.MIME_TYPE_DIR.equals(types.next()))exactDirectory=true;
                // Generic wildcard viewers are not evidence of folder navigation support.
                boolean supported=!directory||documents||exactDirectory;
                boolean permission=info.permission==null||activity.checkSelfPermission(info.permission)==PackageManager.PERMISSION_GRANTED;
                candidates.add(new DirectoryTargets.Target(new ComponentName(info.packageName,info.name).flattenToString(),system,
                    info.enabled&&info.applicationInfo.enabled&&permission,info.exported,supported,documents));
            }
        } catch(RuntimeException unavailable) { return false; }
        return DirectoryTargets.open(candidates,component->activity.startActivity(new Intent(intent).setComponent(ComponentName.unflattenFromString(component))));
    }
    private SystemDirectory() {}
}
