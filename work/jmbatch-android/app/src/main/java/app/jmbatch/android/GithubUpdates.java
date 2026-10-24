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
    private static final String CURRENT_NOTES="Windows 0.3.34 / Android 0.6.17 — 设置独立页与界面优化\n\n发布日期：2026-10-24\n\nWindows 0.3.33 → 0.3.34；Android 0.6.16 → 0.6.17（versionCode 617）。保留原包名、Android 签名和更新公钥，可覆盖安装。\n\n设置与导出\n\n• 主页设置入口仅保留齿轮图标，点击进入独立设置页，保留四组设置及有效修改自动保存。\n• 进入设置时从右侧滑入，原页面同步向左移出；返回时反向移动。动画配置为 0.3 秒，过渡期间锁定重复点击和页面操作，返回后保留原页面状态。Windows 支持 Esc，Android 支持系统返回。\n• 导出新增“只保留编号”圆形开关，默认关闭；开启后单本和批量 PDF / ZIP 使用漫画编号命名，保留源文件与同名保护。\n\n漫画库\n\n• 保持每行四本，放大封面、缩小标题字号；标题固定一行，过长时自动横向滚动，编号独立显示。\n• 批量选择在封面右上角显示任务同款方框动效，收藏星标自动避让；移除整张卡片变色及旧勾号。\n• 长按批量菜单保持漫画库背景清晰，修复 Windows 菜单超出可见底边、移动返回后再次长按异常。\n• 固定按收藏夹、收藏漫画、普通漫画分组；组内按所选名称、时间、大小或章节数正序排序。精简排序和新建收藏夹按钮文字。\n• 保存并复用章节数，切换排序不再逐本读取文件；旧漫画在后台补齐，删除章节后同步更新，收藏和重启后保留。\n\nAndroid 下载任务\n\n• 移除任务右上角更多菜单，长按选择后显示方框；修复批量菜单落在屏幕外的问题。\n• 清除记录支持已暂停、失败、完成和取消的任务。成功任务只移除记录并保留成品；未成功任务清理下载文件和缓存后移除记录。\n• 清理失败保留记录并可重试，重开应用继续未完成清理；运行中、排队中及正在清理的任务受到保护。\n\n验证说明\n\n• 沿用本版已完成的 Windows 实际界面与 Android BlueStacks 5 / Android 9 交互、滑动和状态保留检查，正式版本重新构建并核对签名与产物一致性。\n• 动画实际时长受系统调度影响；未测试实体手机，未扩展无关下载功能回归。\n";
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
        boolean canCheck=!checking&&!downloading&&ready==null;
        if(dialog!=null&&dialog.isShowing()){
            statusView.setText(status);announcementView.setText(notesText());
            checkButton.setEnabled(canCheck);checkButton.setText(checking?"检查中…":"检查更新");
            downloadButton.setEnabled(!checking&&(!latestUrl.isEmpty()||downloading||ready!=null));
            downloadButton.setText(downloading?"取消下载":ready!=null?"安装更新":"下载更新");
        }
        if(notesDialog!=null&&notesDialog.isShowing()){
            notesStatusView.setText(status);
            notesCheckButton.setEnabled(canCheck);notesCheckButton.setText(checking?"检查中…":"检查更新");
            String text=notesText();
            if(!text.contentEquals(notesView.getText()))notesView.setText(text);
        }
    }
    public void showAndCheck(){manualCheck();}
    public void manualCheck(){manual=true;if(ready!=null||downloading){show();return;}check();}
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
                if(newer){if(manual)Ui.confirm(activity,"检测到新版本 "+latestVersion+"\n是否更新",()->{show();download();});else Ui.notice(activity,"检测到新版本 "+latestVersion);}
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
    public void show() {
        if(dialog!=null&&dialog.isShowing())return;
        LinearLayout form=new LinearLayout(activity);form.setOrientation(LinearLayout.VERTICAL);int pad=(int)(20*activity.getResources().getDisplayMetrics().density);form.setPadding(pad,pad,pad,pad);
        TextView intro=new TextView(activity);intro.setText("当前安卓版本："+Core.VERSION+"\n\n更新来源（GitHub 用户名/仓库名，留空可停用更新检查）");form.addView(intro);
        EditText repo=new EditText(activity);repo.setSingleLine(true);repo.setHint("用户名/仓库名");repo.setText(prefs.getString("repository",""));form.addView(repo);
        CheckBox auto=new CheckBox(activity);auto.setText("启动时自动检查更新");auto.setChecked(prefs.getBoolean("automatic",true));form.addView(auto);
        statusView=new TextView(activity);statusView.setText(status);form.addView(statusView);
        announcementView=new TextView(activity);announcementView.setText(notesText());announcementView.setMaxLines(8);announcementView.setPadding(0,pad,0,0);form.addView(announcementView);
        Button notes=new ActionButton(activity);notes.setText("完整更新日志（支持离线查看）");form.addView(notes);
        notes.setOnClickListener(v->showNotes());
        TextView help=new TextView(activity);help.setText("\n修改更新来源后请先保存。关闭自动检查后，仍可手动检查。\n更新包通过签名和完整性校验后即可安装，安装时由系统再次验证应用签名。\n下载更新时请保持应用在前台，安装前请暂停漫画下载。\n检查更新不会发送漫画编号或 Cookie。\n");form.addView(help);
        checkButton=new ActionButton(activity);checkButton.setText("检查更新");form.addView(checkButton,0);
        checkButton.setOnClickListener(v->check());
        downloadButton=new ActionButton(activity);downloadButton.setText("下载更新");downloadButton.setEnabled(!latestUrl.isEmpty());form.addView(downloadButton);
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
    public void showNotes(){
        if(activity.isDestroyed()||activity.isFinishing())return;
        if(notesDialog!=null&&notesDialog.isShowing()){refresh();return;}
        int pad=(int)(20*activity.getResources().getDisplayMetrics().density);
        LinearLayout form=new LinearLayout(activity);form.setOrientation(LinearLayout.VERTICAL);form.setPadding(pad,pad,pad,pad);
        notesStatusView=new TextView(activity);notesStatusView.setText(status);form.addView(notesStatusView);
        notesCheckButton=new ActionButton(activity);notesCheckButton.setText("检查更新");form.addView(notesCheckButton);
        notesCheckButton.setOnClickListener(v->{notesDialog.dismiss();showAndCheck();});
        notesView=new TextView(activity);notesView.setPadding(0,pad,0,0);notesView.setTextIsSelectable(true);notesView.setText(notesText());form.addView(notesView);
        ScrollView content=new ScrollView(activity);content.addView(form);
        notesDialog=new AlertDialog.Builder(activity).setTitle("更新日志").setView(content).setPositiveButton("关闭",null).create();
        notesDialog.setOnDismissListener(d->{notesDialog=null;notesView=null;notesStatusView=null;notesCheckButton=null;});
        notesDialog.show();refresh();
    }
    private void download(){
        if(checking)return;
        if(downloading){cancel.set(true);status="正在取消下载，请稍候…";refresh();return;}
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
            if(!checking)status=repo.isEmpty()?"未设置更新来源":"设置已保存";refresh();return true;
        }catch(IllegalArgumentException error){field.setError(error.getMessage());return false;}
    }
}
