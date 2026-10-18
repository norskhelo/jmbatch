package app.jmbatch.android;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.*;
import android.os.Build;
import android.provider.Settings;
import java.util.List;

/** Permission facts and explicit system actions; never guesses OEM network policy. */
public final class PermissionAccess {
    public static final int NOTIFICATIONS=3301;
    private static final String PREFS="permission_requests",ASKED="notifications_asked";
    static boolean notificationGranted(Context context){return Build.VERSION.SDK_INT<33||context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED;}
    static boolean notificationAsked(Context context){return context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getBoolean(ASKED,false);}
    static boolean canRequestNotification(Activity activity){return Build.VERSION.SDK_INT>=33&&!notificationGranted(activity)&&(!notificationAsked(activity)||activity.shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS));}
    public static void requestDownloadNotifications(Activity activity){
        // First download may prompt once; a denial does not block downloads or cause repeated prompts.
        if(Build.VERSION.SDK_INT>=33&&!notificationGranted(activity)&&!notificationAsked(activity))requestNotification(activity);
    }
    static void requestNotification(Activity activity){
        activity.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putBoolean(ASKED,true).apply();
        activity.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},NOTIFICATIONS);
    }
    static Intent appSettings(Context context){return new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+context.getPackageName()));}
    static boolean open(Activity activity,Intent preferred){
        try{activity.startActivity(preferred);return true;}catch(ActivityNotFoundException|SecurityException unavailable){
            try{activity.startActivity(appSettings(activity));return true;}catch(ActivityNotFoundException|SecurityException missing){return false;}
        }
    }
    static boolean hasDirectoryGrant(String uri,List<UriPermission> grants){
        if(uri==null||uri.isEmpty())return true;
        for(UriPermission grant:grants)if(uri.equals(grant.getUri().toString())&&grant.isReadPermission()&&grant.isWritePermission())return true;
        return false;
    }
    static String notificationStatus(Context context){
        NotificationManager nm=context.getSystemService(NotificationManager.class);
        if(!notificationGranted(context))return "尚未允许通知，可申请授权；拒绝后仍可在应用内查看进度。";
        if(nm==null)return "暂时无法读取通知状态。";
        if(!nm.areNotificationsEnabled())return "系统已关闭应用通知，请在通知设置中开启。";
        NotificationChannel channel=nm.getNotificationChannel("downloads");
        if(channel!=null&&channel.getImportance()==NotificationManager.IMPORTANCE_NONE)return "应用通知已允许，但“下载进度”通知类别被关闭。";
        return "已允许通知"+(channel==null?"；下载进度类别会在首次下载时创建。":"，下载进度类别已启用。");
    }
    private PermissionAccess(){}
}
