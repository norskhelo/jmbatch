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
    private static final String CURRENT_NOTES="Windows 0.2.3 / Android 0.3.3 — 2026-10-15\n\n多任务同时下载\n\n• 下载队列支持同时下载多本漫画。设置中新增“同时下载任务数”，默认 2，可设为 1–4；设为 1 时按原来的顺序逐本下载。\n• “每个任务图片线程数”独立控制单本的图片并发，仍为 1–16、默认 8。并行任务越多，总网络连接和内存占用越高，手机发热或遇到限流时可调低。\n• 保存并行任务数后用于后续调度；提高上限时自动启动等待任务，降低上限时等待当前任务结束，不中断正在下载的漫画。新加入的任务也会自动补位。\n• 各任务分别记录进度、速度、预计完成时间、缓存和自动重连次数。界面显示同时运行数量及总速度；Windows 选中运行中的任务可查看该任务的详细进度，Android 通知展示多个任务。\n• 取消或失败的任务不会停止其他下载。暂停会停止全部任务并保留已验证缓存；Android 在旧请求完全退出后才释放任务名额，防止立即重试时重复写入缓存。关闭应用后重新打开，未完成任务保持暂停，点击开始继续。\n• 其他网络参数继续用于新任务和手动重试；已有任务的保存目录和下载参数保持原快照。原有图片保存、PDF/ZIP 导出、收藏及更新签名验证继续保留。\n\n版本与兼容\n\n• Windows 升至 0.2.3；Android 升至 0.3.3（versionCode 303）。保留 app.jmbatch.android 包名、原 APK 签名与更新公钥，支持覆盖安装。\n• 旧版队列和设置自动采用默认 2 个并行任务；如需串行下载，可在设置中改为 1。\n• 发布双端安装包、同版日志、SHA-256 校验文件、签名更新清单；主页原始下载与国内镜像入口同步至本版。\n\n验证范围\n\n• 验证真实 Windows 子进程同时运行、并发上限与补位、进度隔离、取消、暂停恢复、任务失败、进程崩溃和有上限的自动重连；执行完整单元测试及源码/成品离线自检。\n• 执行 Android 宿主并发测试、既有回归测试、编译与原证书签名校验。未连接 Android 真机，未进行真实网站多任务下载或各地区镜像测速；实际速度受网络、设备和服务端限制。\n";
    private static final AtomicBoolean busy=new AtomicBoolean();
    private static boolean startupChecked;
    private final Activity activity;
    private final Button indicator;
    private final SharedPreferences prefs;
    private final Handler main=new Handler(Looper.getMainLooper());
    private AlertDialog dialog;
    private TextView statusView;
    private TextView announcementView;
    private Button downloadButton;
    private String status="尚未配置更新仓库", latestVersion="", latestUrl="";
    private long generation;
    private boolean downloading;
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
        indicator.setOnClickListener(v->show());
    }
    public void startup() {
        if(!Core.VERSION.equals(prefs.getString("announcement_seen",""))){
            showNotes(true);prefs.edit().putString("announcement_seen",Core.VERSION).apply();
        }
        if(startupChecked)return;
        startupChecked=true;
        if(prefs.getBoolean("automatic",true)&&!prefs.getString("repository","").isEmpty())check();
    }
    private void refresh() {
        if(activity.isDestroyed()||activity.isFinishing())return;
        indicator.setText(latestUrl.isEmpty()?"软件更新 / 公告":"新版 "+latestVersion+" / 公告");
        if(dialog!=null&&dialog.isShowing()){statusView.setText(status);announcementView.setText(notesText());downloadButton.setEnabled(!latestUrl.isEmpty()||downloading);downloadButton.setText(downloading?"取消下载":ready!=null?"安装新版":"下载新版");}
    }
    private void check() {
        if(downloading||ready!=null)return;
        String repo=prefs.getString("repository","");
        if(repo.isEmpty()){status="仓库留空，已跳过检查";refresh();return;}
        if(!busy.compareAndSet(false,true)){status="上次检查仍在结束中，已跳过本次检查";refresh();return;}
        long ticket=++generation;
        AtomicBoolean delivered=new AtomicBoolean();
        status="正在后台检查，最多等待 8 秒…";refresh();
        Runnable timeout=()->{
            if(delivered.compareAndSet(false,true)&&ticket==generation){latestUrl="";status="未能取得完整更新日志，已保留离线公告，请稍后重试";refresh();}
        };
        main.postDelayed(timeout,8000);
        Thread worker=new Thread(()->{
            UpdateHistory.Selection answer=null;boolean success=false;
            try{answer=fetch(repo);success=true;}catch(Exception ignored){/* Silent failure, no task changes. */}
            finally{busy.set(false);}
            final UpdateHistory.Selection result=answer;final boolean ok=success;
            main.post(()->{
                if(!delivered.compareAndSet(false,true))return;
                main.removeCallbacks(timeout);
                if(ticket!=generation||!repo.equals(prefs.getString("repository","")))return;
                boolean newer=result!=null&&UpdateRules.compare(result.latest.version,Core.VERSION)>0;
                latestUrl=newer?result.latest.url:"";latestVersion=newer?result.latest.version:"";
                if(ok&&result!=null){
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
        final String repository=UpdateRules.repository(repo);
        if(repository.isEmpty())return null;
        long deadline=SystemClock.elapsedRealtime()+8000;
        int[] total={0};
        return UpdateHistory.load(page->fetchPage(repository,page,deadline,total),Core.VERSION);
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
        TextView intro=new TextView(activity);intro.setText("当前安卓版本："+Core.VERSION+"\n\nGitHub 公开仓库（用户名/仓库名；留空不检查）");form.addView(intro);
        EditText repo=new EditText(activity);repo.setSingleLine(true);repo.setHint("用户名/仓库名");repo.setText(prefs.getString("repository",""));form.addView(repo);
        CheckBox auto=new CheckBox(activity);auto.setText("启动时自动检查更新");auto.setChecked(prefs.getBoolean("automatic",true));form.addView(auto);
        statusView=new TextView(activity);statusView.setText(status);form.addView(statusView);
        announcementView=new TextView(activity);announcementView.setText(notesText());announcementView.setMaxLines(8);announcementView.setPadding(0,pad,0,0);form.addView(announcementView);
        Button notes=new Button(activity);notes.setText("查看完整更新公告（离线可用）");form.addView(notes);
        notes.setOnClickListener(v->showNotes(false));
        TextView help=new TextView(activity);help.setText("\n检查无响应时静默跳过，不影响下载任务。\n下载后先核验清单签名和 SHA-256；APK 证书先在应用内预检查，系统未提供证书时交由系统安装器核验。已知证书不匹配会阻止安装。\n下载更新时请保持应用在前台；安装前请暂停漫画下载任务。\n只信任本软件发布密钥签署的更新；不发送漫画编号或 Cookie。\n");form.addView(help);
        Button check=new Button(activity);check.setText("保存并检查");form.addView(check);
        downloadButton=new Button(activity);downloadButton.setText("下载新版");downloadButton.setEnabled(!latestUrl.isEmpty());form.addView(downloadButton);
        downloadButton.setOnClickListener(v->download());
        ScrollView scroll=new ScrollView(activity);scroll.addView(form);
        dialog=new AlertDialog.Builder(activity).setTitle("软件更新").setView(scroll).setNegativeButton("关闭",null).setPositiveButton("保存",null).create();
        dialog.setOnShowListener(d->{
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{if(save(repo,auto))dialog.dismiss();});
            check.setOnClickListener(v->{if(save(repo,auto))check();});
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
                    prefs.getString("announcement_from",""),prefs.getString("announcement_version",""),Core.VERSION,history,CURRENT_NOTES);
            }catch(JSONException error){return CURRENT_NOTES;}
        }
        return UpdateRules.announcement(prefs.getString("announcement_repo",""),prefs.getString("repository",""),
            prefs.getString("announcement_version",""),Core.VERSION,prefs.getString("announcement_notes",""),CURRENT_NOTES);
    }
    private void showNotes(boolean local){
        if(activity.isDestroyed()||activity.isFinishing())return;
        int pad=(int)(20*activity.getResources().getDisplayMetrics().density);
        TextView text=new TextView(activity);text.setPadding(pad,pad,pad,pad);text.setTextIsSelectable(true);text.setText(local?CURRENT_NOTES:notesText());
        ScrollView content=new ScrollView(activity);content.addView(text);
        new AlertDialog.Builder(activity).setTitle("更新公告").setView(content).setPositiveButton("关闭",null).show();
    }
    private void download(){
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
            if(!repo.equals(prefs.getString("repository",""))){generation++;latestUrl="";latestVersion="";}
            prefs.edit().putString("repository",repo).putBoolean("automatic",auto.isChecked()).putBoolean("repository_default_v1",true).apply();
            status=repo.isEmpty()?"仓库留空，不检查更新":"设置已保存";refresh();return true;
        }catch(IllegalArgumentException error){field.setError(error.getMessage());return false;}
    }
}
