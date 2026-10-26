package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.*;

/** Optional check and user-confirmed in-app installation. */
public final class GithubUpdates {
    private static final String CURRENT_NOTES="Android 0.6.24 — 分享修复\n\n发布日期：2026-10-26\n\nAndroid 0.6.23 → 0.6.24（versionCode 624）。沿用原包名、签名及更新公钥，可覆盖安装并保留数据。Windows 正式版保持 0.3.40。\n\n• 修复单文件也按多文件发送、PDF/ZIP 统一标为通用文件导致部分分享应用不显示的问题；混合格式批量分享使用通配类型。\n• 修复大写 .PDF 在文件提供接口和保存目录分享中被误识别为 ZIP。\n• 漫画库分享前在后台检查所有选中文件的位置与读取权限；缺失或授权失效时先提示，取消或关闭后不再打开分享面板。\n• 纳入此前已验证的 Android 本地修订：取消慢速阈值触发的断连，保留无进度恢复和请求超时；下载失败直接显示原因；设置中可打开当前保存目录；修复添加下载及共用弹窗显示后的二次定位时序。\n\n验证：Android 10/15 框架 20 项分享专项通过，覆盖单/多文件、混合格式、大写扩展名、文件读取、模拟 SAF 权限失败、实际分享按钮以及取消/关闭保护。沿用此前其他修订的专项验证；本轮未测试实体手机或第三方应用实际接收。原签名与更新清单签名、安装包和源码一致性在发布前核验。\n\n安装：暂停下载后覆盖安装 APK，无需卸载或清除数据。\n";
    private static final AtomicBoolean busy=new AtomicBoolean();
    private static boolean startupChecked;
    private final Activity activity;
    private final Button indicator;
    private final SharedPreferences prefs;
    private final Handler main=new Handler(Looper.getMainLooper());
    private AlertDialog dialog;
    private AlertDialog notesDialog;
    private TextView notesView,notesStatusView;
    private TextView statusView,updateTitle;
    private ProgressBar progressBar;
    private LinearLayout progressArea;
    private Button downloadButton,dismissButton,settingsButton;
    private int downloadPercent=-1;
    private boolean downloadStarted;
    private String status="尚未配置更新仓库", latestVersion="", latestUrl="";
    private long generation;
    private boolean downloading,checking,manual;
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
        else status="未设置更新来源";
        String repo=prefs.getString("repository","");
        String from=UpdateHistory.baseline(prefs.getString("announcement_upgrade_repo",""),
            prefs.getString("announcement_installed_version",""),prefs.getString("announcement_upgrade_from",""),
            prefs.getString("announcement_seen",""),Core.VERSION,repo);
        saveHistoryBaseline(repo,from);
        indicator.setOnClickListener(v->showAndCheck());
    }
    public void startup() {
        if(!Core.VERSION.equals(prefs.getString("announcement_seen",""))){
            Ui.notice(activity,"更新完成");prefs.edit().putString("announcement_seen",Core.VERSION).apply();
        }
        if(startupChecked)return;
        startupChecked=true;
        if(prefs.getBoolean("automatic",true)&&!prefs.getString("repository","").isEmpty())check();
    }
    private void refresh() {
        if(activity.isDestroyed()||activity.isFinishing())return;
        indicator.setText(latestUrl.isEmpty()?"软件更新":"发现新版本 "+latestVersion);
        String actionText=checking?"检查中…":!latestUrl.isEmpty()||downloading||ready!=null?"更新":"检查更新";
        if(settingsButton!=null){settingsButton.setText(actionText);settingsButton.setEnabled(!checking);}
        if(dialog!=null&&dialog.isShowing()){
            boolean active=downloadStarted||downloading||ready!=null;
            Ui.setText(updateTitle,active?"更新 "+latestVersion:"检测到新版本 "+latestVersion+"\n是否更新");
            progressArea.setVisibility(active?View.VISIBLE:View.GONE);
            Ui.setText(statusView,status);
            progressBar.setIndeterminate(downloading&&downloadPercent<0);
            progressBar.setProgress(ready!=null?100:Math.max(0,downloadPercent));
            downloadButton.setEnabled(!checking&&!downloading);
            downloadButton.setText(downloading?"下载中…":ready!=null?"安装更新":downloadStarted?"重试":"确认");
            dismissButton.setText(downloading?"取消下载":active?"关闭":"取消");
            dismissButton.setEnabled(!downloading||!cancel.get());
            dialog.setCanceledOnTouchOutside(!downloading);
        }
        if(notesDialog!=null&&notesDialog.isShowing()){
            notesStatusView.setText(status);
            String text=notesText();
            if(!text.contentEquals(notesView.getText()))notesView.setText(text);
        }
    }
    public void showAndCheck(){manualCheck();}
    public void manualCheck(){
        if(ready!=null||downloading){confirmUpdate();return;}
        if(!latestUrl.isEmpty()){confirmUpdate();return;}
        manual=true;check();
    }
    void bindSettingsButton(Button button){settingsButton=button;button.setOnClickListener(v->manualCheck());refresh();}
    private void confirmUpdate(){
        if(activity.isDestroyed()||activity.isFinishing())return;
        if(dialog!=null&&dialog.isShowing()){refresh();return;}
        if(latestUrl.isEmpty()&&ready==null)return;
        LinearLayout body=Ui.column(activity);Ui.gap(body,12);
        updateTitle=Ui.text(activity,"检测到新版本 "+latestVersion+"\n是否更新",17);
        updateTitle.setGravity(Gravity.CENTER);body.addView(updateTitle);Ui.gap(body,24);
        progressArea=Ui.column(activity);
        progressBar=new ProgressBar(activity,null,android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        android.content.res.ColorStateList tint=android.content.res.ColorStateList.valueOf(Ui.ACCENT);
        progressBar.setProgressTintList(tint);progressBar.setIndeterminateTintList(tint);
        progressBar.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.LINE));
        progressArea.addView(progressBar,new LinearLayout.LayoutParams(-1,Ui.dp(activity,8)));Ui.gap(progressArea,12);
        statusView=Ui.text(activity,status,14);statusView.setGravity(Gravity.CENTER);progressArea.addView(statusView);Ui.gap(progressArea,18);
        body.addView(progressArea);progressArea.setVisibility(View.GONE);
        downloadButton=Ui.button(activity,"确认",this::download);Ui.primary(downloadButton);
        dismissButton=Ui.button(activity,"取消",this::closeUpdate);body.addView(Ui.pair(activity,downloadButton,dismissButton));
        ScrollView scroll=new ScrollView(activity);scroll.setFillViewport(true);scroll.addView(body);
        dialog=Ui.modal(activity,scroll,true);
        dialog.setOnKeyListener((d,key,event)->{
            if(key==KeyEvent.KEYCODE_BACK&&downloading){if(event.getAction()==KeyEvent.ACTION_UP)closeUpdate();return true;}return false;
        });
        dialog.setOnDismissListener(d->{dialog=null;progressBar=null;progressArea=null;statusView=null;updateTitle=null;downloadButton=null;dismissButton=null;});
        dialog.show();refresh();
    }
    private void closeUpdate(){
        if(downloading){cancel.set(true);status="正在取消下载，请稍候…";refresh();}
        else if(dialog!=null)dialog.dismiss();
    }
    private void check() {
        if(downloading||ready!=null)return;
        if(checking){refresh();return;}
        String repo=prefs.getString("repository","");
        if(repo.isEmpty()){status="请先填写更新仓库并保存，再点击检查更新";refresh();return;}
        if(!busy.compareAndSet(false,true)){status="上次检查尚未结束，请稍后重试。";refresh();return;}
        checking=true;latestUrl="";latestVersion="";
        long ticket=++generation;
        final String from=historyFrom();
        AtomicBoolean delivered=new AtomicBoolean();
        status="正在检查更新…";refresh();
        Runnable timeout=()->{
            if(delivered.compareAndSet(false,true)&&ticket==generation){checking=false;latestUrl="";status="无法获取完整更新日志。已保留本地日志，请稍后重试。";refresh();if(manual)Ui.notice(activity,status);manual=false;}
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
                status=!ok?"无法获取完整更新日志。已保留本地日志，请稍后重试。":!newer?"当前已是最新版本":"发现新版 "+latestVersion;
                refresh();
                if(newer){if(manual)confirmUpdate();else Ui.notice(activity,"检测到新版本 "+latestVersion);}
                else if(manual)Ui.notice(activity,status);manual=false;
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
    public void showNotes(){
        if(activity.isDestroyed()||activity.isFinishing())return;
        if(notesDialog!=null&&notesDialog.isShowing()){refresh();return;}
        int pad=(int)(20*activity.getResources().getDisplayMetrics().density);
        LinearLayout form=new LinearLayout(activity);form.setOrientation(LinearLayout.VERTICAL);form.setPadding(pad,pad,pad,pad);
        notesStatusView=new TextView(activity);notesStatusView.setText(status);form.addView(notesStatusView);
        notesView=new TextView(activity);notesView.setPadding(0,pad,0,0);notesView.setTextIsSelectable(true);notesView.setText(notesText());form.addView(notesView);
        ScrollView content=new ScrollView(activity);content.addView(form);
        notesDialog=new AlertDialog.Builder(activity).setTitle("更新日志").setView(content).setPositiveButton("关闭",null).create();
        notesDialog.setOnDismissListener(d->{notesDialog=null;notesView=null;notesStatusView=null;});
        notesDialog.show();refresh();
    }
    private void download(){
        if(checking)return;
        if(downloading)return;
        if(ready!=null){
            new AlertDialog.Builder(activity).setTitle("安装更新").setMessage("安装会关闭当前应用。请先暂停漫画下载任务，安装后重新打开应用继续。是否继续？")
                .setNegativeButton("取消",null).setPositiveButton("继续",(d,w)->{
                    try{UpdateInstaller.install(activity,ready);}catch(Exception e){status="无法安装："+e.getClass().getSimpleName()+": "+e.getMessage();refresh();}
                }).show();return;
        }
        if(latestUrl.isEmpty())return;
        if(!UpdateInstaller.busy.compareAndSet(false,true)){status="已有更新下载正在进行，请稍后重试";refresh();return;}
        final String url=latestUrl,version=latestVersion,repo=prefs.getString("repository","");
        downloading=true;downloadStarted=true;downloadPercent=-1;cancel.set(false);status="正在准备更新…";refresh();
        new Thread(()->{
            UpdateInstaller.Ready result=null;String failure=null;
            try{result=UpdateInstaller.download(activity.getApplicationContext(),url,repo,version,cancel,
                new UpdateInstaller.Progress(){
                    public void update(String value){main.post(()->{if(!cancel.get()){status=value;downloadPercent=-1;refresh();}});}
                    public void download(String route,long bytes,long total){main.post(()->{
                        if(!cancel.get()){
                            downloadPercent=(int)Math.max(0,Math.min(100,bytes*100/total));
                            status="下载更新 · "+route+" · "+downloadPercent+"% · "+(bytes/1024)+"/"+(total/1024)+" KB";refresh();
                        }
                    });}
                });}
            catch(Exception e){failure=e.getClass().getSimpleName()+": "+e.getMessage();}
            finally{UpdateInstaller.busy.set(false);}
            final UpdateInstaller.Ready completed=result;final String error=failure;
            main.post(()->{downloading=false;ready=completed;status=completed==null?(cancel.get()?"已取消更新下载，可点击重试。":"更新未完成："+error):completed.verificationMessage();refresh();});
        },"update-download").start();
    }
}
