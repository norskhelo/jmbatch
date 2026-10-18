package app.jmbatch.android;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import java.lang.reflect.*;
import java.net.*;
import java.util.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.android.controller.ActivityController;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w360dp-h800dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
public class PermissionRuntimeTest {
    ActivityController<? extends PermissionActivity> controller;
    PermissionActivity activity;
    @Before public void reset()throws Exception{
        Field singleton=Store.class.getDeclaredField("instance");singleton.setAccessible(true);singleton.set(null,null);
        RuntimeEnvironment.getApplication().deleteFile("queue.json");RuntimeEnvironment.getApplication().deleteFile("network-report.txt");
        RuntimeEnvironment.getApplication().getSharedPreferences("permission_requests",0).edit().clear().commit();
        shadowOf(RuntimeEnvironment.getApplication()).denyPermissions(Manifest.permission.POST_NOTIFICATIONS);
        controller=Robolectric.buildActivity(PermissionActivity.class);activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);activity.getApplicationInfo().targetSdkVersion=34;controller.setup();
    }
    @After public void close(){if(controller!=null)controller.pause().stop().destroy();shadowOf(Looper.getMainLooper()).idle();}
    static Object field(Object object,String name)throws Exception{Field f=PermissionActivity.class.getDeclaredField(name);f.setAccessible(true);return f.get(object);}
    Button find(View v,String text){if(v instanceof Button&&((Button)v).getText().toString().equals(text))return (Button)v;if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){Button b=find(((ViewGroup)v).getChildAt(i),text);if(b!=null)return b;}return null;}
    Button button(String text){Button b=find(activity.getWindow().getDecorView(),text);assertNotNull(text,b);return b;}
    @Test public void opensWithoutPromptsOrNetwork()throws Exception{
        assertNull(field(activity,"probe"));assertNull(shadowOf(activity).getLastRequestedPermission());assertNull(shadowOf(activity).getNextStartedActivity());
        assertFalse(((CheckBox)field(activity,"direct")).isChecked());assertTrue(((TextView)field(activity,"internet")).getText().toString().contains("无法可靠读取"));
        assertTrue(((TextView)field(activity,"directory")).getText().toString().contains("无需申请存储权限"));
    }
    @Test public void notificationRequestOrSettingsMatchesAndroidVersion(){
        activity.notificationAction();
        if(Build.VERSION.SDK_INT>=33){assertNotNull(shadowOf(activity).getLastRequestedPermission());assertTrue(PermissionAccess.notificationAsked(activity));}
        else assertEquals(Settings.ACTION_APP_NOTIFICATION_SETTINGS,shadowOf(activity).getNextStartedActivity().getAction());
    }
    @Test public void deniedRequestDoesNotLoopAndCanOpenSettings(){
        activity.getSharedPreferences("permission_requests",0).edit().putBoolean("notifications_asked",true).commit();
        PermissionAccess.requestDownloadNotifications(activity);assertNull(shadowOf(activity).getLastRequestedPermission());
        activity.notificationAction();assertNull(shadowOf(activity).getLastRequestedPermission());assertEquals(Settings.ACTION_APP_NOTIFICATION_SETTINGS,shadowOf(activity).getNextStartedActivity().getAction());
    }
    @Test public void notificationChannelAndReturnRefresh()throws Exception{
        shadowOf(RuntimeEnvironment.getApplication()).grantPermissions(Manifest.permission.POST_NOTIFICATIONS);
        NotificationManager manager=activity.getSystemService(NotificationManager.class);shadowOf(manager).setNotificationsEnabled(true);
        manager.createNotificationChannel(new NotificationChannel("downloads","Downloads",NotificationManager.IMPORTANCE_NONE));
        controller.pause().resume();assertTrue(((TextView)field(activity,"notifications")).getText().toString().contains("通知类别被关闭"));
    }
    @Test public void settingsIntentsTargetThisApp(){
        button("应用联网设置").performClick();assertEquals("package:"+activity.getPackageName(),shadowOf(activity).getNextStartedActivity().getDataString());
        button("安装更新权限").performClick();Intent intent=shadowOf(activity).getNextStartedActivity();assertEquals(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,intent.getAction());assertEquals("package:"+activity.getPackageName(),intent.getDataString());
    }
    @Test public void deniedDirectoryDoesNotChangeSettings()throws Exception{
        Store s=Store.get(activity);String original=s.settings.outputUri;
        activity.onActivityResult(4301,Activity.RESULT_OK,new Intent().setData(Uri.parse("content://test/tree/new")).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));
        assertEquals(original,s.settings.outputUri);assertTrue(((TextView)field(activity,"directory")).getText().toString().contains("无需申请存储权限"));
    }
    @Test public void persistedDirectoryCanBeReauthorized()throws Exception{
        String uri="content://test/tree/new";
        activity.onActivityResult(4301,Activity.RESULT_OK,new Intent().setData(Uri.parse(uri)).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION));
        assertEquals(uri,Store.get(activity).settings.outputUri);
        assertTrue(PermissionAccess.hasDirectoryGrant(uri,activity.getContentResolver().getPersistedUriPermissions()));
        assertTrue(((TextView)field(activity,"directory")).getText().toString().contains("已保留此目录的读写授权"));
    }
    @Test public void taskDirectoryCannotBeSilentlyChanged()throws Exception{
        controller.pause().stop().destroy();controller=Robolectric.buildActivity(PermissionActivity.class,new Intent().putExtra("directory","content://test/tree/original"));activity=controller.get();controller.setup();
        activity.onActivityResult(4301,Activity.RESULT_OK,new Intent().setData(Uri.parse("content://test/tree/different")).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION));
        assertEquals("",Store.get(activity).settings.outputUri);assertEquals("content://test/tree/original",field(activity,"targetUri"));
    }
    @Test public void sharingAndSavingUseUserActions()throws Exception{
        ((StringBuilder)field(activity,"report")).append("synthetic report");button("复制报告").performClick();
        assertTrue(((ClipboardManager)activity.getSystemService(Context.CLIPBOARD_SERVICE)).getPrimaryClip().getItemAt(0).getText().toString().contains("synthetic report"));
        button("分享报告").performClick();assertEquals(Intent.ACTION_CHOOSER,shadowOf(activity).getNextStartedActivity().getAction());
        button("保存报告").performClick();assertEquals(Intent.ACTION_CREATE_DOCUMENT,shadowOf(activity).getNextStartedActivityForResult().intent.getAction());
        Bundle bundle=new Bundle();controller.saveInstanceState(bundle);assertTrue(bundle.getString("pendingExport").contains("synthetic report"));
    }
    public static class FakeActivity extends PermissionActivity {
        @Override NetworkProbe createProbe(){return new NetworkProbe(new NetworkProbe.Operations(){
            public InetAddress[] dns(String h)throws Exception{return new InetAddress[]{InetAddress.getByName("203.0.113.7")};}
            public String https(String h){return "HTTP 403";}
            public String direct(String h,InetAddress a){throw new AssertionError("direct must be opt-in");}
        },new String[]{"test.example"},1000,3000);}
    }
    @Test public void manualProbeRunsAndSavesUnderSameApplication()throws Exception{
        controller.pause().stop().destroy();controller=Robolectric.buildActivity(FakeActivity.class);activity=controller.get();controller.setup();
        button("检测本应用联网").performClick();
        long deadline=System.nanoTime()+5000000000L;
        while(field(activity,"probe")!=null&&System.nanoTime()<deadline){Thread.sleep(20);shadowOf(Looper.getMainLooper()).idle();}
        assertNull(field(activity,"probe"));assertTrue(field(activity,"report").toString().contains("JM Batch 自身身份"));
        assertTrue(field(activity,"report").toString().contains("HTTP 403"));assertTrue(activity.getFileStreamPath("network-report.txt").isFile());
    }
    @Test public void homeAndFailedTaskHaveEntry()throws Exception{
        ActivityController<MainActivity> main=Robolectric.buildActivity(MainActivity.class);MainActivity home=main.get();home.setTheme(android.R.style.Theme_Material_Light_NoActionBar);main.setup();
        try{Field h=MainActivity.class.getDeclaredField("handler");h.setAccessible(true);((Handler)h.get(home)).removeCallbacksAndMessages(null);
            Button entry=find(home.getWindow().getDecorView(),"权限与联网检测");assertNotNull(entry);entry.performClick();assertEquals(PermissionActivity.class.getName(),shadowOf(home).getNextStartedActivity().getComponent().getClassName());
            Store.Task task=new Store.Task("123456",new Store.Settings());task.status="failed";task.settings.outputUri="content://test/tree/task";
            Method details=MainActivity.class.getDeclaredMethod("details",Store.Task.class);details.setAccessible(true);details.invoke(home,task);
            AlertDialog dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
            Button taskEntry=find(dialog.getWindow().getDecorView(),"权限与联网检测");assertNotNull(taskEntry);taskEntry.performClick();
            Intent taskIntent=shadowOf(home).getNextStartedActivity();assertEquals(PermissionActivity.class.getName(),taskIntent.getComponent().getClassName());assertEquals(task.settings.outputUri,taskIntent.getStringExtra("directory"));dialog.dismiss();
        }finally{main.pause().stop().destroy();}
    }
    public static class MissingSettings extends Activity {
        Intent opened;
        @Override public void startActivity(Intent intent){if(!Settings.ACTION_APPLICATION_DETAILS_SETTINGS.equals(intent.getAction()))throw new ActivityNotFoundException();opened=intent;}
    }
    @Test public void missingSystemScreenFallsBackToAppDetails(){
        ActivityController<MissingSettings> missing=Robolectric.buildActivity(MissingSettings.class).setup();
        try{assertTrue(PermissionAccess.open(missing.get(),new Intent("unsupported.settings")));assertEquals("package:"+missing.get().getPackageName(),missing.get().opened.getDataString());}finally{missing.pause().stop().destroy();}
    }
}
