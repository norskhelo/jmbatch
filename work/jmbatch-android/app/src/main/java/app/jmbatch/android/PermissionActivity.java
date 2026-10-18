package app.jmbatch.android;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.*;
import android.os.*;
import android.provider.DocumentsContract;
import android.provider.Settings;
import android.widget.*;
import java.io.*;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;

/** Application-identity permission checks and user-started, local network diagnostics. */
public class PermissionActivity extends Activity {
    private static final int DIRECTORY=4301,EXPORT=4302;
    private Store store;
    private TextView internet,notifications,directory,background,installation,reportView;
    private Button notificationButton,detect,stop;
    private CheckBox direct;
    private String targetUri,pendingExport;
    private boolean taskDirectory,destroyed;
    private final StringBuilder report=new StringBuilder();
    private volatile NetworkProbe probe;
    public static void open(Activity activity){activity.startActivity(new Intent(activity,PermissionActivity.class));}
    public static void open(Activity activity,Store.Task task){activity.startActivity(new Intent(activity,PermissionActivity.class).putExtra("directory",task.settings.outputUri));}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);store=Store.get(this);
        taskDirectory=getIntent().hasExtra("directory");targetUri=taskDirectory?getIntent().getStringExtra("directory"):store.settings.outputUri;
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);int pad=dp(16);body.setPadding(pad,pad,pad,pad);
        addText(body,"权限与联网检测",23);addText(body,"权限与系统设置仅在你选择对应操作时申请或打开；从设置返回后会自动刷新。",14);
        internet=section(body,"联网");button(body,"应用联网设置",()->openSettings(PermissionAccess.appSettings(this)));
        notifications=section(body,"下载通知");notificationButton=button(body,"申请通知权限",()->notificationAction());
        directory=section(body,taskDirectory?"此任务的保存目录":"保存目录");button(body,taskDirectory?"重新授权此目录":"选择或重新授权目录",()->chooseDirectory());
        background=section(body,"后台下载（可选）");
        body.addView(new ActionRow(this,action("省电设置",()->openSettings(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))),action("后台流量设置",()->openSettings(new Intent(Settings.ACTION_IGNORE_BACKGROUND_DATA_RESTRICTIONS_SETTINGS,Uri.parse("package:"+getPackageName()))))));
        installation=section(body,"安装应用更新（可选）");button(body,"安装更新权限",()->openSettings(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+getPackageName()))));
        button(body,"重新检测权限",()->refreshPermissions());
        addText(body,"联网诊断",20);addText(body,"以 JM Batch 自身身份检测系统 DNS、小米官网与四条漫画线路的 HTTPS。仅测试连接，不读取漫画、Cookie 或账号；报告含机型、系统版本及网络信息，仅保存在本机，可主动分享。通常数十秒，最多约 90 秒。",14);
        direct=new CheckBox(this);direct.setText("额外比较 IPv4/IPv6 直连（忽略 HTTP 代理，仍使用当前网络/VPN）");body.addView(direct);
        detect=action("检测本应用联网",()->startProbe());stop=action("停止检测",()->{if(probe!=null)probe.cancel();});stop.setEnabled(false);body.addView(new ActionRow(this,detect,stop));
        body.addView(new ActionRow(this,action("复制报告",()->{((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("JM Batch 联网报告",report.toString()));toast("报告已复制");}),action("分享报告",()->share()),action("保存报告",()->export())));
        reportView=addText(body,"",12);reportView.setTextIsSelectable(true);button(body,"返回",()->finish());
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.addView(body);setContentView(scroll);
        if(state!=null){pendingExport=state.getString("pendingExport");append(state.getString("report",""));}
        else try(FileInputStream in=openFileInput("network-report.txt")){ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] data=new byte[4096];int n;while((n=in.read(data))!=-1&&out.size()+n<=65536)out.write(data,0,n);append(new String(out.toByteArray(),StandardCharsets.UTF_8));}catch(IOException ignored){}
    }
    @Override protected void onResume(){super.onResume();refreshPermissions();}
    void refreshPermissions(){
        if(internet==null)return;
        boolean granted=checkSelfPermission(Manifest.permission.INTERNET)==PackageManager.PERMISSION_GRANTED;
        internet.setText((granted?"Android 联网权限已授予（安装时自动授予）。":"Android 联网权限不可用，请检查安装包或系统管理策略。")+"\n厂商额外的 WLAN/移动数据联网限制无法可靠读取；此项不表示实际联网已放行。可打开应用设置核对，或运行下方诊断。");
        notifications.setText(PermissionAccess.notificationStatus(this));notificationButton.setText(PermissionAccess.canRequestNotification(this)?"申请通知权限":"打开通知设置");
        if(!taskDirectory)targetUri=store.settings.outputUri;
        try{directory.setText(targetUri==null||targetUri.isEmpty()?"使用应用下载目录，无需申请存储权限。卸载应用会删除此目录的文件。":PermissionAccess.hasDirectoryGrant(targetUri,getContentResolver().getPersistedUriPermissions())?"已保留此目录的读写授权；目录是否仍存在及可写，需实际保存时确认。":"此目录的持久读写授权缺失，请重新选择原目录授权。");}
        catch(Exception error){directory.setText("无法读取目录授权状态，请重新检查或选择目录。");}
        try{
            PowerManager power=(PowerManager)getSystemService(POWER_SERVICE);ConnectivityManager cm=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
            ActivityManager am=(ActivityManager)getSystemService(ACTIVITY_SERVICE);
            int data=cm==null?0:cm.getRestrictBackgroundStatus();
            background.setText("省电优化："+(power!=null&&power.isIgnoringBatteryOptimizations(getPackageName())?"已豁免":"启用中，可按需调整")+"\n省流量："+(data==ConnectivityManager.RESTRICT_BACKGROUND_STATUS_ENABLED?"已开启，本应用后台流量受限":data==ConnectivityManager.RESTRICT_BACKGROUND_STATUS_WHITELISTED?"本应用已获后台流量豁免":data==ConnectivityManager.RESTRICT_BACKGROUND_STATUS_DISABLED?"未开启":"状态未知")+(Build.VERSION.SDK_INT>=28&&am!=null?"\n系统后台限制："+(am.isBackgroundRestricted()?"受限":"未报告限制"):"")+"\n厂商的自启动及额外省电策略需在系统中核对。无需为前台使用授予这些可选设置。");
        }catch(Exception error){background.setText("暂时无法读取后台限制状态，可前往系统设置核对。");}
        try{installation.setText(getPackageManager().canRequestPackageInstalls()?"已允许从 JM Batch 安装更新。":"尚未允许；仅在安装新版 APK 时需要，不影响下载漫画。");}catch(Exception error){installation.setText("暂时无法读取安装更新权限。");}
    }
    void notificationAction(){
        if(PermissionAccess.canRequestNotification(this))PermissionAccess.requestNotification(this);
        else openSettings(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,getPackageName()));
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==PermissionAccess.NOTIFICATIONS)refreshPermissions();}
    private void openSettings(Intent intent){if(!PermissionAccess.open(this,intent))toast("此系统不支持该入口，请在系统设置中找到 JM Batch");}
    private void chooseDirectory(){
        if(taskDirectory&&(targetUri==null||targetUri.isEmpty())){toast("此任务使用应用目录，无需外部目录授权");return;}
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION|Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        if(targetUri!=null&&!targetUri.isEmpty())try{Uri uri=Uri.parse(targetUri);intent.putExtra(DocumentsContract.EXTRA_INITIAL_URI,DocumentsContract.buildDocumentUriUsingTree(uri,DocumentsContract.getTreeDocumentId(uri)));}catch(Exception ignored){}
        try{startActivityForResult(intent,DIRECTORY);}catch(ActivityNotFoundException|SecurityException error){toast("系统目录选择器不可用，可在首页使用应用下载目录");}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request==EXPORT){String snapshot=pendingExport;pendingExport=null;if(result==RESULT_OK&&data!=null&&data.getData()!=null&&snapshot!=null)try(OutputStream out=getContentResolver().openOutputStream(data.getData())){if(out==null)throw new IOException();out.write(snapshot.getBytes(StandardCharsets.UTF_8));toast("报告已保存");}catch(Exception e){toast("保存失败，请复制报告");}return;}
        if(request!=DIRECTORY||result!=RESULT_OK||data==null||data.getData()==null)return;
        String oldUri=store.settings.outputUri,oldLabel=store.settings.outputLabel;
        try{
            Uri uri=data.getData();if(taskDirectory&&!uri.toString().equals(targetUri))throw new IOException("请选择此任务原来的保存目录；任务位置未修改");
            int flags=data.getFlags()&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            if(flags!=(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION))throw new IOException("所选目录未授予完整读写权限");
            if((getPackageName()+".documents").equals(uri.getAuthority()))throw new IOException("请返回首页选择“使用应用目录”，此浏览入口为只读");
            getContentResolver().takePersistableUriPermission(uri,flags);
            if(!taskDirectory){store.settings.outputUri=uri.toString();store.settings.outputLabel=DocumentsContract.getTreeDocumentId(uri);store.save();}
            toast(taskDirectory?"原目录已重新授权，可返回重试任务":"目录授权已保存，新任务使用此目录；已有任务的保存位置不变");
        }catch(Exception e){store.settings.outputUri=oldUri;store.settings.outputLabel=oldLabel;toast("目录授权未完成："+Core.error(e,""));}
        refreshPermissions();
    }
    void startProbe(){
        if(probe!=null)return;report.setLength(0);reportView.setText("");detect.setEnabled(false);stop.setEnabled(true);direct.setEnabled(false);
        append("JM Batch "+Core.VERSION+" / 本应用身份联网诊断\n"+new SimpleDateFormat("yyyy-MM-dd HH:mm:ss Z",Locale.ROOT).format(new Date()));
        append("机型："+Build.MANUFACTURER+" "+Build.MODEL+"；Android "+Build.VERSION.RELEASE+" / API "+Build.VERSION.SDK_INT+"；系统构建："+Build.DISPLAY);
        append("联网权限："+(checkSelfPermission(Manifest.permission.INTERNET)==PackageManager.PERMISSION_GRANTED?"已授予；厂商限制未确认":"未授予"));
        boolean compare=direct.isChecked();append("额外直连对比："+compare);NetworkProbe current=createProbe();probe=current;
        Thread worker=new Thread(()->{
            try{String initial=network();runOnUiThread(()->{if(!destroyed)append(initial);});current.run(compare,line->runOnUiThread(()->{if(!destroyed)append(line);}));}
            catch(Exception error){runOnUiThread(()->{if(!destroyed)append("诊断异常："+NetworkProbe.error(error));});}
            finally{String ending=network();runOnUiThread(()->{if(destroyed)return;append("\n结束时 "+ending+"\n若中途切换网络，请重新检测。");probe=null;detect.setEnabled(true);stop.setEnabled(false);direct.setEnabled(true);try(FileOutputStream out=openFileOutput("network-report.txt",MODE_PRIVATE)){out.write(report.toString().getBytes(StandardCharsets.UTF_8));}catch(IOException error){append("本地报告保存失败，可复制报告。");}});}
        },"jm-network-check");worker.setDaemon(true);worker.start();
    }
    NetworkProbe createProbe(){return new NetworkProbe();}
    private String network(){
        try{ConnectivityManager cm=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);Network active=cm.getActiveNetwork();if(active==null)return "当前无活动默认网络";NetworkCapabilities caps=cm.getNetworkCapabilities(active);LinkProperties lp=cm.getLinkProperties(active);StringBuilder s=new StringBuilder("当前网络：");
            if(caps!=null)s.append("Wi-Fi=").append(caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)).append("，移动数据=").append(caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)).append("，VPN=").append(caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)).append("，系统已验证联网=").append(caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED));
            if(lp!=null){s.append("\nDNS 服务器：");for(InetAddress a:lp.getDnsServers())s.append(a.getHostAddress()).append(' ');if(Build.VERSION.SDK_INT>=28)s.append("\n私人 DNS 已启用=").append(lp.isPrivateDnsActive()).append("，指定服务名=").append(lp.getPrivateDnsServerName()==null?"无/自动":lp.getPrivateDnsServerName());}
            ProxyInfo proxy=cm.getDefaultProxy();s.append("\nHTTP 代理=").append(proxy==null?"无":"有（地址未记录）");return s.toString();
        }catch(Exception e){return "网络状态读取失败："+NetworkProbe.error(e);}
    }
    private void share(){try{startActivity(Intent.createChooser(new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,report.toString()),"分享联网报告"));}catch(ActivityNotFoundException e){toast("没有可用的分享应用，请复制或保存报告");}}
    private void export(){pendingExport=report.toString();try{startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("text/plain").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"JM-network-"+new SimpleDateFormat("yyyyMMdd-HHmmss",Locale.ROOT).format(new Date())+".txt"),EXPORT);}catch(ActivityNotFoundException e){pendingExport=null;toast("系统文件选择器不可用，请复制报告");}}
    @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);state.putString("report",report.toString());state.putString("pendingExport",pendingExport);}
    @Override protected void onDestroy(){destroyed=true;if(probe!=null)probe.cancel();super.onDestroy();}
    private void append(String value){report.append(value).append('\n');reportView.setText(report.toString());}
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private void toast(String text){Toast.makeText(this,text,Toast.LENGTH_LONG).show();}
    private TextView addText(LinearLayout parent,String text,int size){TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setPadding(0,dp(6),0,dp(6));parent.addView(v);return v;}
    private TextView section(LinearLayout parent,String title){addText(parent,title,18);return addText(parent,"",14);}
    private Button action(String text,Runnable callback){Button b=new ActionButton(this);b.setText(text);b.setOnClickListener(v->callback.run());return b;}
    private Button button(LinearLayout parent,String text,Runnable callback){Button b=action(text,callback);parent.addView(b,new LinearLayout.LayoutParams(-1,-2));return b;}
}
