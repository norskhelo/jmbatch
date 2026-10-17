package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.content.pm.*;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.*;

/** Downloads signed release assets. Installation is always confirmed by Android. */
public final class UpdateInstaller {
    public interface Progress { void update(String value); }
    public static final AtomicBoolean busy=new AtomicBoolean();
    public static File apk(Context context){return new File(context.getCacheDir(),"app-update/update.apk");}
    public static final class Ready {
        final File file;final String version,sha;final long size;
        boolean certificateMatched;
        Ready(File f,String v,String h,long s){file=f;version=v;sha=h;size=s;}
        String verificationMessage(){return certificateMatched?"清单签名、SHA-256 和 APK 证书校验通过，可以安装":
            "清单签名与 SHA-256 校验通过。此系统未提供完整 APK 证书信息，安装时由安卓系统核验；可以继续安装。";}
    }
    public static boolean allowed(URL url){return UpdateDownload.allowed(url,null);}
    private static byte[] metadata(String address,long limit,AtomicBoolean cancel,Progress progress,String label)throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        UpdateDownload.transfer(address,()->{bytes.reset();return bytes;},limit,cancel,(route,n)->progress.update(label+" · "+route));
        return bytes.toByteArray();
    }
    public static Ready download(Context context,String url,String repo,String version,AtomicBoolean cancel,Progress progress)throws Exception{
        String name="JMBatch-"+version+"-Android.apk";
        if(!UpdateRules.validUrl(url,repo,name))throw new SecurityException("更新地址不匹配");
        String base=url.substring(0,url.lastIndexOf('/')+1);
        String path=new URI(base).getPath();String tag=path.substring(0,path.length()-1);tag=tag.substring(tag.lastIndexOf('/')+1);
        byte[] manifest=metadata(base+"update-manifest.json",65536,cancel,progress,"下载更新清单");
        byte[] signature=metadata(base+"update-manifest.sig",4096,cancel,progress,"下载清单签名");
        progress.update("正在验证更新清单签名…");
        UpdateCrypto.verify(manifest,signature);
        JSONObject data=new JSONObject(new String(manifest,StandardCharsets.UTF_8));
        if(data.getInt("schema")!=1||!data.getString("repository").equals(repo)||!data.getString("tag").equals(tag))throw new SecurityException("更新清单与仓库或发布版本不匹配");
        JSONObject pkg=data.getJSONObject("packages").getJSONObject("android");
        if(!pkg.getString("name").equals(name)||!pkg.getString("version").equals(version)||UpdateRules.compare(version,Core.VERSION)<=0)throw new SecurityException("更新包版本不匹配或不是新版");
        long size=pkg.getLong("size");String hash=pkg.getString("sha256");
        if(size<=0||size>512L*1024*1024||!hash.matches("[0-9a-f]{64}"))throw new SecurityException("更新包大小或摘要无效");
        File file=apk(context);file.getParentFile().mkdirs();
        try{
            UpdateDownload.transfer(url,()->new FileOutputStream(file),size,cancel,(route,n)->progress.update("下载更新 · "+route+" · "+(n*100/size)+"% · "+(n/1024)+"/"+(size/1024)+" KB"));
            UpdateCrypto.verifyFile(file,size,hash);
            if(cancel.get())throw new InterruptedIOException("已取消更新下载");
            Ready ready=new Ready(file,version,hash,size);verifyApk(context,ready);return ready;
        }catch(Exception error){file.delete();throw error;}
    }
    @SuppressWarnings("deprecation")
    private static void verifyApk(Context context,Ready ready)throws Exception{
        PackageManager pm=context.getPackageManager();
        // Metadata and certificates are requested separately: some ROMs return
        // valid metadata but a null SigningInfo even with the documented flag.
        PackageInfo installed=pm.getPackageInfo(context.getPackageName(),0),candidate=pm.getPackageArchiveInfo(ready.file.getAbsolutePath(),0);
        if(installed==null)throw new IOException("系统未提供当前应用信息，请手动覆盖安装官方 APK");
        if(candidate==null||!context.getPackageName().equals(candidate.packageName)||!ready.version.equals(candidate.versionName))throw new SecurityException("APK 无法解析，或包名、版本不匹配");
        long oldCode=Build.VERSION.SDK_INT>=28?installed.getLongVersionCode():installed.versionCode;
        long newCode=Build.VERSION.SDK_INT>=28?candidate.getLongVersionCode():candidate.versionCode;
        if(newCode<=oldCode)throw new SecurityException("APK versionCode 未递增，拒绝降级或重复安装");
        String[] oldS=readCertificates(pm,context.getPackageName(),null);
        String[] newS=readCertificates(pm,context.getPackageName(),ready.file);
        // Called only after the signed-manifest package hash has been verified.
        // Missing metadata defers certificate validation to the system installer;
        // a known mismatch remains a hard failure, without any fallback.
        ready.certificateMatched=UpdateCertificateCheck.matches(oldS,newS);
    }
    @SuppressWarnings("deprecation")
    private static String[] readCertificates(PackageManager pm,String packageName,File archive){
        return UpdateCertificateCheck.read(()->{
            if(Build.VERSION.SDK_INT<28)return null;
            PackageInfo info=archive==null?pm.getPackageInfo(packageName,PackageManager.GET_SIGNING_CERTIFICATES):pm.getPackageArchiveInfo(archive.getAbsolutePath(),PackageManager.GET_SIGNING_CERTIFICATES);
            return info==null||info.signingInfo==null?null:certificateStrings(info.signingInfo.getApkContentsSigners());
        },()->{
            PackageInfo info=archive==null?pm.getPackageInfo(packageName,PackageManager.GET_SIGNATURES):pm.getPackageArchiveInfo(archive.getAbsolutePath(),PackageManager.GET_SIGNATURES);
            return info==null?null:certificateStrings(info.signatures);
        });
    }
    private static String[] certificateStrings(android.content.pm.Signature[] signatures){
        if(signatures==null)return null;
        String[] result=new String[signatures.length];
        for(int i=0;i<signatures.length;i++)result[i]=signatures[i]==null?null:signatures[i].toCharsString();
        return result;
    }
    public static void install(Activity activity,Ready ready)throws Exception{
        Store store=Store.get(activity);
        if(store.running)throw new IllegalStateException("请先在首页暂停全部漫画下载，再安装更新");
        for(Store.Task task:store.snapshot())if(task.status.equals("running")||task.status.equals("resetting"))throw new IllegalStateException("下载请求正在结束，请等待任务变为已暂停再安装");
        UpdateCrypto.verifyFile(ready.file,ready.size,ready.sha);verifyApk(activity,ready);
        if(!activity.getPackageManager().canRequestPackageInstalls()){
            new AlertDialog.Builder(activity).setTitle("允许安装更新").setMessage("请允许 JM Batch 安装应用。返回后再次点击“安装新版”，由系统确认安装。")
                .setNegativeButton("取消",null).setPositiveButton("前往设置",(d,w)->{
                    try{activity.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+activity.getPackageName())));}
                    catch(ActivityNotFoundException error){android.widget.Toast.makeText(activity,"请在系统设置中允许 JM Batch 安装未知应用",1).show();}
                }).show();return;
        }
        Uri uri=Uri.parse("content://"+activity.getPackageName()+".updates/update.apk");
        Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.setClipData(ClipData.newRawUri("JM Batch update",uri));activity.startActivity(intent);
    }
}
