package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.widget.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.*;

/** Optional check and user-confirmed in-app installation. */
public final class GithubUpdates {
    private static final String CURRENT_NOTES="Windows 0.2.0 / Android 0.3.0 — 2026-10-14\n\n下载与导出分离\n\n• 下载默认保存为可直接查看的图片目录，不再自动合成 PDF 或 ZIP。图片按章节、页码排序：0001/00001.jpg、0001/00002.jpg、0002/00001.jpg。\n• 图片目录保存下载处理后的原分辨率图片；保存和后续 ZIP/PDF 导出不额外缩放图片。上游图片的必要解码/还原沿用现有实现，并非承诺与网站原始响应逐字节一致。\n• 首页取消下载格式选择；PDF、ZIP、纯编号命名、单章节 ZIP 平铺等选项移入“导出”。图片始终保留，导出可重复进行且无需重新联网下载。\n• PDF 提供统一导出和分章节导出；分章节按章节编号生成独立 PDF，文件名附 0001、0002 等序号。ZIP 多章节始终按章节分目录。\n• 可在导出时选择保存目录；遇到同名文件停止并提示，不覆盖原有文件。取消或失败保留源图片。\n\n漫画库与兼容\n\n• 漫画库支持图片目录的扫描、打开、收藏、导出和删除；Android 应用内目录浏览与系统文档入口支持章节图片。\n• 保留已有 PDF/ZIP 记录和收藏；未完成的旧下载任务继续时改为图片保存，并复用已验证缓存。\n• 图片目录包含 .jmbatch-album.json 清单，供扫描、排序、恢复和导出使用。删除该清单或改动图片路径/大小可能导致校验失败。\n• 保留百分比、预计时间、大小与自动速度单位；文件校验并保存成功后显示 100.0% 和“下载完成”。\n\n版本与交付\n\n• Windows 0.2.0；Android 0.3.0（versionCode 300），保留原包名和签名。\n• 本次按要求推送源码与日志；安装包在本地分版本交付，未创建 GitHub Release 或上传新安装包。\n• 离线测试及本地构建用于回归；Android 真机、系统目录提供方及真实网络下载仍需实际设备验证。\n";
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
    private String latestNotes="";
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
            if(delivered.compareAndSet(false,true)&&ticket==generation){latestUrl="";status="检查失败或超时，已跳过";refresh();}
        };
        main.postDelayed(timeout,8000);
        Thread worker=new Thread(()->{
            String[] answer=null;boolean success=false;
            try{answer=fetch(repo);success=true;}catch(Exception ignored){/* Silent failure, no task changes. */}
            finally{busy.set(false);}
            final String[] result=answer;final boolean ok=success;
            main.post(()->{
                if(!delivered.compareAndSet(false,true))return;
                main.removeCallbacks(timeout);
                if(ticket!=generation||!repo.equals(prefs.getString("repository","")))return;
                boolean newer=result!=null&&UpdateRules.compare(result[0],Core.VERSION)>0;
                latestUrl=newer?result[1]:"";latestVersion=newer?result[0]:"";
                latestNotes=result==null?"":result[2];
                if(ok&&result!=null)prefs.edit().putString("announcement_repo",repo).putString("announcement_version",result[0]).putString("announcement_notes",result[2]).apply();
                status=!ok?"检查失败或超时，已跳过":!newer?"当前已是适用版本，可查看下方更新公告":"发现新版 "+latestVersion;
                refresh();
            });
        },"github-update-check");
        worker.setDaemon(true);worker.start();
    }
    private static String[] fetch(String repo) throws Exception {
        HttpURLConnection connection=(HttpURLConnection)new URL("https://api.github.com/repos/"+repo+"/releases?per_page=20").openConnection();
        connection.setConnectTimeout(4000);connection.setReadTimeout(4000);connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("User-Agent","JMBatch-Updater");connection.setRequestProperty("Accept","application/vnd.github+json");
        connection.setRequestProperty("X-GitHub-Api-Version","2022-11-28");
        long deadline=SystemClock.elapsedRealtime()+8000;
        try {
            if(connection.getResponseCode()!=200)throw new IOException("GitHub 暂不可用");
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(InputStream input=connection.getInputStream()){
                byte[] buffer=new byte[8192];int count;
                while((count=input.read(buffer))!=-1){
                    if(SystemClock.elapsedRealtime()>=deadline||bytes.size()+count>1024*1024)throw new IOException("检查超时或响应过大");
                    bytes.write(buffer,0,count);
                }
            }
            JSONArray releases=new JSONArray(new String(bytes.toByteArray(),StandardCharsets.UTF_8));
            String[] best=null;
            for(int i=0;i<Math.min(releases.length(),20);i++){
                JSONObject release=releases.getJSONObject(i);
                if(release.optBoolean("draft")||release.optBoolean("prerelease"))continue;
                JSONArray assets=release.optJSONArray("assets");if(assets==null)continue;
                for(int j=0;j<assets.length();j++){
                    JSONObject asset=assets.getJSONObject(j);String name=asset.optString("name"),version=UpdateRules.assetVersion(name),url=asset.optString("browser_download_url");
                    if(version==null||!asset.optString("state").equals("uploaded")||asset.optLong("size")<=0||!UpdateRules.validUrl(url,repo,name))continue;
                    if(UpdateRules.compare(version,Core.VERSION)>=0&&(best==null||UpdateRules.compare(version,best[0])>0)){
                        String notes=release.optString("body","");if(notes.isEmpty()||notes.equals("null"))notes="发布者未填写更新日志。";
                        best=new String[]{version,url,notes.substring(0,Math.min(notes.length(),8000))};
                    }
                }
            }
            return best;
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
