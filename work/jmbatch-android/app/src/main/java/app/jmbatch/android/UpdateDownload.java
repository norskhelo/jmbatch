package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Public release transport only. Signed manifests and APK validation remain mandatory. */
public final class UpdateDownload {
    private static final String[] NAMES={"GitHub","GHFast","GH-Proxy"};
    private static final String[] PREFIXES={"","https://ghfast.top/","https://gh-proxy.com/"};
    public interface Destination { OutputStream open() throws IOException; }
    public interface Progress { void update(String route,long bytes); }
    private interface Network<T> { T run() throws IOException; }
    private static final class RemoteFailure extends IOException {
        RemoteFailure(String message){super(message);}
        RemoteFailure(IOException cause){super("更新线路连接或读取失败",cause);}
    }
    private static <T> T network(Network<T> operation)throws IOException {
        try{return operation.run();}catch(IOException error){throw new RemoteFailure(error);}
    }
    public static boolean allowed(URL url,String original) {
        if(!url.getProtocol().equals("https")||url.getUserInfo()!=null||url.getRef()!=null||(url.getPort()!=-1&&url.getPort()!=443))return false;
        if(Arrays.asList("github.com","release-assets.githubusercontent.com","objects.githubusercontent.com","github-releases.githubusercontent.com").contains(url.getHost()))return true;
        return original!=null&&(url.toExternalForm().equals(PREFIXES[1]+original)||url.toExternalForm().equals(PREFIXES[2]+original));
    }
    public static void validate(String address)throws IOException {
        try {
            URI uri=new URI(address);String[] parts=uri.getPath().split("/",-1);
            if(!"https".equals(uri.getScheme())||!"github.com".equals(uri.getRawAuthority())||uri.getRawQuery()!=null||uri.getRawFragment()!=null
                ||parts.length!=7||!parts[3].equals("releases")||!parts[4].equals("download"))throw new SecurityException("更新源必须是 GitHub Release 的固定附件地址");
            for(int i=1;i<parts.length;i++)if(parts[i].isEmpty()||parts[i].equals(".")||parts[i].equals("..")||parts[i].contains("\\"))throw new SecurityException("更新源路径无效");
        }catch(URISyntaxException error){throw new SecurityException("更新源地址无效",error);}
    }
    private static void check(AtomicBoolean cancel,long start)throws IOException {
        if(cancel.get()||Thread.currentThread().isInterrupted())throw new InterruptedIOException("已取消更新下载");
        if(System.nanoTime()-start>1800000000000L)throw new InterruptedIOException("更新下载超时，请重试");
    }
    public static void transfer(String address,Destination target,long limit,AtomicBoolean cancel,Progress progress)throws IOException {
        validate(address);long start=System.nanoTime();
        for(int route=0;route<PREFIXES.length;route++) {
            check(cancel,start);
            // A fresh/truncated destination prevents bytes from different routes being joined.
            OutputStream output=target.open();RemoteFailure failure=null;
            try {
                progress.update(NAMES[route],0);
                transferOne(new URL(PREFIXES[route]+address),address,output,limit,cancel,progress,NAMES[route],start);
                check(cancel,start);output.flush();
            }catch(RemoteFailure error){failure=error;}
            finally{output.close();}
            if(failure==null)return;
            check(cancel,start);
        }
        throw new IOException("GitHub、GHFast、GH-Proxy 更新下载均失败，请检查网络后重试");
    }
    private static void transferOne(URL url,String original,OutputStream output,long limit,AtomicBoolean cancel,Progress progress,String route,long start)throws IOException {
        for(int redirects=0;redirects<=5;redirects++) {
            check(cancel,start);
            if(!allowed(url,original))throw new SecurityException("更新下载重定向到不可信地址，已阻止");
            final URL current=url;
            HttpURLConnection connection=network(()->(HttpURLConnection)current.openConnection());
            connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(15000);connection.setReadTimeout(15000);
            connection.setRequestProperty("User-Agent","JMBatch-Updater");connection.setRequestProperty("Accept-Encoding","identity");
            try {
                int code=network(connection::getResponseCode);check(cancel,start);
                if(code==301||code==302||code==303||code==307||code==308) {
                    String location=connection.getHeaderField("Location");
                    if(location==null)throw new RemoteFailure("更新重定向地址缺失");
                    url=new URL(url,location);continue;
                }
                if(code!=200)throw new RemoteFailure("更新下载 HTTP "+code);
                String type=connection.getContentType();
                if(type!=null&&type.toLowerCase(Locale.ROOT).contains("text/html"))throw new RemoteFailure("更新线路返回网页而非文件");
                long expected=connection.getContentLengthLong();
                if(expected>limit)throw new SecurityException("更新文件超过允许大小");
                try(InputStream input=network(connection::getInputStream)) {
                    byte[] buffer=new byte[65536];long total=0,last=0;
                    while(true) {
                        check(cancel,start);int count=network(()->input.read(buffer));check(cancel,start);
                        if(count==-1)break;
                        total+=count;if(total>limit)throw new SecurityException("更新文件超过允许大小");
                        // Local write errors are not caught as network failures.
                        output.write(buffer,0,count);
                        if(System.nanoTime()-last>150000000L){last=System.nanoTime();progress.update(route,total);}
                    }
                    if(total==0||(expected>=0&&total!=expected))throw new RemoteFailure("更新响应为空或下载不完整");
                    progress.update(route,total);
                }
                return;
            }finally{connection.disconnect();}
        }
        throw new RemoteFailure("更新重定向次数过多");
    }
    private UpdateDownload(){}
}
