package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.widget.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.*;

/** Optional check and user-confirmed in-app installation. */
public final class GithubUpdates {
    private static final String CURRENT_NOTES="Android 0.5.1 — 2026-10-17\n\n默认使用系统文件管理器\n\n• “打开保存目录”改用安卓原生 Intent，默认优先启动手机自带的文件管理应用；不再自动优先打开左侧菜单显示“JM Batch”的文档管理界面。\n• 支持目录查看的系统文件管理器会收到保存目录地址；仅提供应用入口时，直接打开文件管理器主界面，并提示手动定位。返回 JM Batch 后可查看、复制保存位置或选择备用打开方式。\n• 使用 Android 原生文件应用类别发现组件，并兼容旧款华为／荣耀文件管理器入口；仅自动启动可用的系统组件。组件受限或启动失败时继续尝试其他入口。\n• 文档管理改为手动备用选项，保留选择其他应用和软件内查看。首页、任务详情、漫画库和软件内子目录的系统打开入口使用同一逻辑。\n• 不移动已有文件，不更改保存目录或目录授权。部分文件管理器不能浏览应用目录，或会忽略指定位置；此时可用备用入口，或在首页为以后下载选择可见的公共文件夹。\n\n版本与验证\n\n• Android 0.5.0 → 0.5.1，versionCode 501；Windows 保持 0.3.9。保留原包名、APK 签名证书与更新公钥，支持覆盖安装。\n• 回归默认文件管理器选择、文档管理仅手动回退、原生 Intent 参数、启动失败备用入口、禁用/非导出组件及第三方组件过滤；执行 Android 宿主回归、编译与签名核验。\n• 用户设备为荣耀 Play5 / Android 10。未连接该手机；宿主模拟检查不能证明厂商界面实际跳转，未承诺所有系统都能直达保存目录。\n• 同步源码、应用内说明、同版更新日志、APK、SHA-256 校验文件及原密钥签名更新清单，正式发布 Android 0.5.1。\n";
    private static final AtomicBoolean busy=new AtomicBoolean();
    private static boolean startupChecked;
    private final Activity activity;
    private final Button indicator;
    private final SharedPreferences prefs;
    private final Handler main=new Handler(Looper.getMainLooper());
    private AlertDialog dialog;
    private AlertDialog notesDialog;
    private TextView notesView,notesStatusView;
    private TextView statusView;
    private TextView announcementView;
    private Button downloadButton,checkButton,notesCheckButton;
    private String status="尚未配置更新仓库", latestVersion="", latestUrl="";
    private long generation;
    private boolean downloading,checking;
    private final AtomicBoolean cancel=new AtomicBoolean();
    private UpdateInstaller.Ready ready;

    public GithubUpdates(Activity activity, Button indicator) {
        this.activity=activity;this.indicator=indicator;
        prefs=activity.getSharedPreferences("updates",Context.MODE_PRIVATE);
        if(!prefs.getBoolean("repository_default_v1",false)){
            String repo=UpdateRules.initialRepository(prefs.getString("repository",""),false);
            prefs.edit().putString("repository",repo).putBoolean("repository_default_v1",true).apply();
        }
        if(!prefs.getString("repository","").isEmpty())status="等待检查";
        else status="仓库留空，不检查更新";
        String repo=prefs.getString("repository","");
        String from=UpdateHistory.baseline(prefs.getString("announcement_upgrade_repo",""),
            prefs.getString("announcement_installed_version",""),prefs.getString("announcement_upgrade_from",""),
            prefs.getString("announcement_seen",""),Core.VERSION,repo);
        saveHistoryBaseline(repo,from);
        indicator.setOnClickListener(v->showAndCheck());
    }
    public void startup() {
        if(!Core.VERSION.equals(prefs.getString("announcement_seen",""))){
            showNotes();prefs.edit().putString("announcement_seen",Core.VERSION).apply();
        }
        if(startupChecked)return;
        startupChecked=true;
        if(prefs.getBoolean("automatic",true)&&!prefs.getString("repository","").isEmpty())check();
    }
    private void refresh() {
        if(activity.isDestroyed()||activity.isFinishing())return;
        indicator.setText(latestUrl.isEmpty()?"检查更新 / 公告":"新版 "+latestVersion+" / 公告");
        boolean canCheck=!checking&&!downloading&&ready==null;
        if(dialog!=null&&dialog.isShowing()){
            statusView.setText(status);announcementView.setText(notesText());
            checkButton.setEnabled(canCheck);checkButton.setText(checking?"检查中…":"检查更新");
            downloadButton.setEnabled(!checking&&(!latestUrl.isEmpty()||downloading||ready!=null));
            downloadButton.setText(downloading?"取消下载":ready!=null?"安装新版":"下载新版");
        }
        if(notesDialog!=null&&notesDialog.isShowing()){
            notesStatusView.setText(status);
            notesCheckButton.setEnabled(canCheck);notesCheckButton.setText(checking?"检查中…":"检查更新");
            String text=notesText();
            if(!text.contentEquals(notesView.getText()))notesView.setText(text);
        }
    }
    public void showAndCheck(){show();check();}
    private void check() {
        if(downloading||ready!=null)return;
        if(checking){refresh();return;}
        String repo=prefs.getString("repository","");
        if(repo.isEmpty()){status="请先填写更新仓库并保存，再点击检查更新";refresh();return;}
        if(!busy.compareAndSet(false,true)){status="上次检查仍在结束中，请稍后点击检查更新重试";refresh();return;}
        checking=true;latestUrl="";latestVersion="";
        long ticket=++generation;
        final String from=historyFrom();
        AtomicBoolean delivered=new AtomicBoolean();
        status="正在后台检查，最多等待 8 秒…";refresh();
        Runnable timeout=()->{
            if(delivered.compareAndSet(false,true)&&ticket==generation){checking=false;latestUrl="";status="未能取得完整更新日志，已保留离线公告，请稍后重试";refresh();}
        };
        main.postDelayed(timeout,8000);
        Thread worker=new Thread(()->{
            UpdateHistory.Selection answer=null;boolean success=false;
            try{answer=fetch(repo,from);success=true;}catch(Exception ignored){/* Silent failure, no task changes. */}
            finally{busy.set(false);}
            final UpdateHistory.Selection result=answer;final boolean ok=success;
            main.post(()->{
                if(!delivered.compareAndSet(false,true))return;
                main.removeCallbacks(timeout);
                if(ticket!=generation||!repo.equals(prefs.getString("repository","")))return;
                checking=false;
                boolean newer=result!=null&&UpdateRules.compare(result.latest.version,Core.VERSION)>0;
                latestUrl=newer?result.latest.url:"";latestVersion=newer?result.latest.version:"";
                if(ok&&result!=null&&UpdateRules.compare(result.latest.version,Core.VERSION)>=0){
                    JSONArray history=new JSONArray();
                    for(UpdateHistory.Entry entry:result.history)
                        history.put(new JSONArray().put(entry.version).put(entry.notes));
                    prefs.edit().putString("announcement_repo",repo).putString("announcement_version",result.latest.version)
                        .putString("announcement_notes",result.latest.notes).putString("announcement_from",result.fromVersion)
                        .putString("announcement_history",history.toString()).putInt("announcement_schema",2).apply();
                }
                status=!ok?"未能取得完整更新日志，已保留离线公告，请稍后重试":!newer?"当前已是适用版本，可查看下方更新公告":"发现新版 "+latestVersion;
                refresh();
            });
        },"github-update-check");
        worker.setDaemon(true);worker.start();
    }
    static UpdateHistory.Selection fetch(String repo) throws Exception {
        return fetch(repo,Core.VERSION);
    }
    static UpdateHistory.Selection fetch(String repo,String from) throws Exception {
        final String repository=UpdateRules.repository(repo);
        if(repository.isEmpty())return null;
        long deadline=SystemClock.elapsedRealtime()+8000;
        int[] total={0};
        return UpdateHistory.load(page->fetchPage(repository,page,deadline,total),from);
    }
    private static UpdateHistory.Page fetchPage(String repo,int page,long deadline,int[] total) throws Exception {
        long remaining=deadline-SystemClock.elapsedRealtime();
        if(remaining<=0)throw new IOException("完整更新日志读取超时");
        HttpURLConnection connection=(HttpURLConnection)new URL("https://api.github.com/repos/"+repo+"/releases?per_page="+UpdateHistory.PAGE_SIZE+"&page="+page).openConnection();
        int timeout=(int)Math.max(1,Math.min(4000,remaining));
        connection.setConnectTimeout(timeout);connection.setReadTimeout(timeout);connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("User-Agent","JMBatch-Updater");connection.setRequestProperty("Accept","application/vnd.github+json");
        connection.setRequestProperty("X-GitHub-Api-Version","2022-11-28");
        try {
            if(connection.getResponseCode()!=200)throw new IOException("GitHub 暂不可用");
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(InputStream input=connection.getInputStream()){
                byte[] buffer=new byte[8192];int count;
                while((count=input.read(buffer))!=-1){
                    total[0]+=count;
                    if(SystemClock.elapsedRealtime()>=deadline||total[0]>UpdateHistory.MAX_BYTES)throw new IOException("完整更新日志读取超时或响应过大");
                    bytes.write(buffer,0,count);
                }
            }
            JSONArray releases=new JSONArray(new String(bytes.toByteArray(),StandardCharsets.UTF_8));
            List<UpdateHistory.Entry> entries=new ArrayList<>();
            for(int i=0;i<releases.length();i++){
                JSONObject release=releases.optJSONObject(i);if(release==null)continue;
                if(release.optBoolean("draft")||release.optBoolean("prerelease"))continue;
                JSONArray assets=release.optJSONArray("assets");if(assets==null)continue;
                for(int j=0;j<assets.length();j++){
                    JSONObject asset=assets.optJSONObject(j);if(asset==null)continue;
                    String notes=release.isNull("body")?"":release.optString("body","");
                    UpdateHistory.Entry entry=UpdateHistory.candidate(repo,asset.optString("name"),asset.optString("browser_download_url"),
                        asset.optString("state"),asset.optLong("size"),false,false,notes,
                        release.optString("published_at","")+"\n"+release.optString("tag_name",""));
                    if(entry!=null)entries.add(entry);
                }
            }
            return new UpdateHistory.Page(releases.length(),entries);
        }finally{connection.disconnect();}
    }
    public void show() {
        if(dialog!=null&&dialog.isShowing())return;
        LinearLayout form=new LinearLayout(activity);form.setOrientation(LinearLayout.VERTICAL);int pad=(int)(20*activity.getResources().getDisplayMetrics().density);form.setPadding(pad,pad,pad,pad);
        TextView intro=new TextView(activity);intro.setText("当前安卓版本："+Core.VERSION+"\n\nGitHub 公开仓库（用户名/仓库名；修改后先保存，留空不检查）");form.addView(intro);
        EditText repo=new EditText(activity);repo.setSingleLine(true);repo.setHint("用户名/仓库名");repo.setText(prefs.getString("repository",""));form.addView(repo);
        CheckBox auto=new CheckBox(activity);auto.setText("启动时自动检查更新");auto.setChecked(prefs.getBoolean("automatic",true));form.addView(auto);
        statusView=new TextView(activity);statusView.setText(status);form.addView(statusView);
        announcementView=new TextView(activity);announcementView.setText(notesText());announcementView.setMaxLines(8);announcementView.setPadding(0,pad,0,0);form.addView(announcementView);
        Button notes=new Button(activity);notes.setText("查看完整更新公告（离线可用）");form.addView(notes);
        notes.setOnClickListener(v->showNotes());
        TextView help=new TextView(activity);help.setText("\n检查更新使用已保存的仓库，关闭自动检查后也可手动检查。\n失败或超时可再次点击重试，不影响下载任务。\n下载后先核验清单签名和 SHA-256；APK 证书先在应用内预检查，系统未提供证书时交由系统安装器核验。已知证书不匹配会阻止安装。\n下载更新时请保持应用在前台；安装前请暂停漫画下载任务。\n只信任本软件发布密钥签署的更新；不发送漫画编号或 Cookie。\n");form.addView(help);
        checkButton=new Button(activity);checkButton.setText("检查更新");form.addView(checkButton,0);
        checkButton.setOnClickListener(v->check());
        downloadButton=new Button(activity);downloadButton.setText("下载新版");downloadButton.setEnabled(!latestUrl.isEmpty());form.addView(downloadButton);
        downloadButton.setOnClickListener(v->download());
        ScrollView scroll=new ScrollView(activity);scroll.addView(form);
        dialog=new AlertDialog.Builder(activity).setTitle("软件更新").setView(scroll).setNegativeButton("关闭",null).setPositiveButton("保存",null).create();
        dialog.setOnShowListener(d->{
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->save(repo,auto));
        });dialog.show();refresh();
    }
    private String notesText(){
        if(prefs.getInt("announcement_schema",0)==2){
            try{
                JSONArray saved=new JSONArray(prefs.getString("announcement_history","[]"));
                List<UpdateHistory.Entry> history=new ArrayList<>();
                for(int i=0;i<saved.length();i++){
                    JSONArray item=saved.getJSONArray(i);
                    history.add(new UpdateHistory.Entry(item.getString(0),"","",item.getString(1),""));
                }
                return UpdateHistory.announcement(prefs.getString("announcement_repo",""),prefs.getString("repository",""),
                    prefs.getString("announcement_from",""),prefs.getString("announcement_version",""),Core.VERSION,history,CURRENT_NOTES,historyFrom());
            }catch(JSONException error){return UpdateHistory.pendingAnnouncement(Core.VERSION,historyFrom(),CURRENT_NOTES);}
        }
        if(UpdateRules.compare(historyFrom(),Core.VERSION)<0)return UpdateHistory.pendingAnnouncement(Core.VERSION,historyFrom(),CURRENT_NOTES);
        return UpdateRules.announcement(prefs.getString("announcement_repo",""),prefs.getString("repository",""),
            prefs.getString("announcement_version",""),Core.VERSION,prefs.getString("announcement_notes",""),CURRENT_NOTES);
    }
    private void saveHistoryBaseline(String repo,String from){
        prefs.edit().putString("announcement_upgrade_repo",repo).putString("announcement_installed_version",Core.VERSION)
            .putString("announcement_upgrade_from",from).apply();
    }
    private String historyFrom(){
        return UpdateHistory.baseline(prefs.getString("announcement_upgrade_repo",""),
            prefs.getString("announcement_installed_version",""),prefs.getString("announcement_upgrade_from",""),
            Core.VERSION,Core.VERSION,prefs.getString("repository",""));
    }
    private void showNotes(){
        if(activity.isDestroyed()||activity.isFinishing())return;
        if(notesDialog!=null&&notesDialog.isShowing()){refresh();return;}
        int pad=(int)(20*activity.getResources().getDisplayMetrics().density);
        LinearLayout form=new LinearLayout(activity);form.setOrientation(LinearLayout.VERTICAL);form.setPadding(pad,pad,pad,pad);
        notesStatusView=new TextView(activity);notesStatusView.setText(status);form.addView(notesStatusView);
        notesCheckButton=new Button(activity);notesCheckButton.setText("检查更新");form.addView(notesCheckButton);
        notesCheckButton.setOnClickListener(v->{notesDialog.dismiss();showAndCheck();});
        notesView=new TextView(activity);notesView.setPadding(0,pad,0,0);notesView.setTextIsSelectable(true);notesView.setText(notesText());form.addView(notesView);
        ScrollView content=new ScrollView(activity);content.addView(form);
        notesDialog=new AlertDialog.Builder(activity).setTitle("更新公告").setView(content).setPositiveButton("关闭",null).create();
        notesDialog.setOnDismissListener(d->{notesDialog=null;notesView=null;notesStatusView=null;notesCheckButton=null;});
        notesDialog.show();refresh();
    }
    private void download(){
        if(checking)return;
        if(downloading){cancel.set(true);status="正在取消，当前网络请求结束后停止…";refresh();return;}
        if(ready!=null){
            new AlertDialog.Builder(activity).setTitle("安装更新").setMessage("安装会关闭当前应用。请先暂停漫画下载任务，安装后重新打开应用继续。是否继续？")
                .setNegativeButton("取消",null).setPositiveButton("继续",(d,w)->{
                    try{UpdateInstaller.install(activity,ready);}catch(Exception e){status="无法安装："+e.getClass().getSimpleName()+": "+e.getMessage();refresh();}
                }).show();return;
        }
        if(latestUrl.isEmpty())return;
        if(!UpdateInstaller.busy.compareAndSet(false,true)){status="已有更新下载正在进行，请稍后重试";refresh();return;}
        final String url=latestUrl,version=latestVersion,repo=prefs.getString("repository","");
        downloading=true;cancel.set(false);status="正在准备更新…";refresh();
        new Thread(()->{
            UpdateInstaller.Ready result=null;String failure=null;
            try{result=UpdateInstaller.download(activity.getApplicationContext(),url,repo,version,cancel,
                value->main.post(()->{status=value;refresh();}));}
            catch(Exception e){failure=e.getClass().getSimpleName()+": "+e.getMessage();}
            finally{UpdateInstaller.busy.set(false);}
            final UpdateInstaller.Ready completed=result;final String error=failure;
            main.post(()->{downloading=false;ready=completed;status=completed==null?"更新未完成："+error:completed.verificationMessage();refresh();});
        },"update-download").start();
    }
    private boolean save(EditText field,CheckBox auto) {
        if(downloading||ready!=null){Toast.makeText(activity,"当前更新完成前不能更改仓库",Toast.LENGTH_LONG).show();return false;}
        try{
            String repo=UpdateRules.repository(field.getText().toString());
            if(!repo.equals(prefs.getString("repository",""))){generation++;checking=false;latestUrl="";latestVersion="";saveHistoryBaseline(repo,Core.VERSION);}
            prefs.edit().putString("repository",repo).putBoolean("automatic",auto.isChecked()).putBoolean("repository_default_v1",true).apply();
            if(!checking)status=repo.isEmpty()?"仓库留空，不检查更新":"设置已保存";refresh();return true;
        }catch(IllegalArgumentException error){field.setError(error.getMessage());return false;}
    }
}
