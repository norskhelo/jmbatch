package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;
import javax.net.ssl.*;

/** No Android dependencies; no cookies, response bodies, persistent IDs or external DNS. */
public final class NetworkProbe {
    public static final String[] HOSTS={"www.mi.com","www.cdnhjk.net","www.cdngwc.net","www.cdngwc.club","www.cdngwc.cc"};
    private static final ThreadPoolExecutor IO=new ThreadPoolExecutor(2,2,0,TimeUnit.SECONDS,
        new ArrayBlockingQueue<Runnable>(2),r->{Thread t=new Thread(r,"network-probe-io");t.setDaemon(true);return t;});
    public interface Operations {
        InetAddress[] dns(String host)throws Exception;
        String https(String host)throws Exception;
        String direct(String host,InetAddress address)throws Exception;
        default boolean hasFallback(){return false;}
        default String fallback(String host)throws Exception{return "备用解析未接入";}
        default void cancel(){}
    }
    public static class NetworkOperations implements Operations {
        public InetAddress[] dns(String host)throws Exception{return InetAddress.getAllByName(host);}
        public String https(String host)throws Exception {
            URL url=new URL("https://"+host+"/");
            HttpURLConnection c=(HttpURLConnection)url.openConnection();
            try {
                c.setConnectTimeout(4000);c.setReadTimeout(4000);c.setInstanceFollowRedirects(false);
                c.setRequestMethod("HEAD");c.setRequestProperty("User-Agent","JMBatch-Network-Check/0.6.0");
                c.setUseCaches(false);
                int code=c.getResponseCode();
                if(code<100)throw new IOException("未取得有效 HTTP 状态");
                return "HTTP "+code+"，HTTPS 已收到响应（不代表漫画接口可用）";
            } finally {c.disconnect();}
        }
        public String direct(String host,InetAddress address)throws Exception {
            try(Socket tcp=new Socket(Proxy.NO_PROXY)) {
                tcp.connect(new InetSocketAddress(address,443),4000);tcp.setSoTimeout(4000);
                try(SSLSocket tls=(SSLSocket)((SSLSocketFactory)SSLSocketFactory.getDefault()).createSocket(tcp,host,443,true)) {
                    tls.setSoTimeout(4000);
                    SSLParameters params=tls.getSSLParameters();
                    params.setEndpointIdentificationAlgorithm("HTTPS");
                    params.setServerNames(Collections.singletonList(new SNIHostName(host)));
                    tls.setSSLParameters(params);tls.startHandshake();
                    // Handshake only: default trust + original hostname + SNI; never trust-all.
                    return "TCP + TLS 通过，证书与域名校验通过（未请求漫画）";
                }
            }
        }
    }
    private final Operations operations;
    private final String[] hosts;
    private final long operationMillis, totalMillis;
    private volatile boolean cancelled;
    public NetworkProbe(){this(new NetworkOperations(),HOSTS,7000,90000);}
    public NetworkProbe(Operations ops,String[] hosts,long operationMillis,long totalMillis){
        this.operations=ops;this.hosts=hosts.clone();this.operationMillis=operationMillis;this.totalMillis=totalMillis;
    }
    public void cancel(){cancelled=true;operations.cancel();}
    private <T> T step(Callable<T> action,long deadline)throws Exception {
        return step(action,deadline,operationMillis);
    }
    private <T> T step(Callable<T> action,long deadline,long allowedMillis)throws Exception {
        if(cancelled)throw new InterruptedException("已停止");
        if(System.nanoTime()>=deadline)throw new TimeoutException("达到总时限");
        IO.purge();Future<T> future=IO.submit(action);
        long until=Math.min(deadline,System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(allowedMillis));
        try {
            while(!cancelled) {
                long remaining=until-System.nanoTime();
                if(remaining<=0)throw new TimeoutException("该阶段超时；系统 DNS 调用可能仍在退出");
                try{return future.get(Math.min(remaining,TimeUnit.MILLISECONDS.toNanos(100)),TimeUnit.NANOSECONDS);}
                catch(TimeoutException waiting){/* Check cancellation and total deadline. */}
            }
            throw new InterruptedException("已停止");
        } catch(ExecutionException e) {
            Throwable cause=e.getCause();if(cause instanceof Exception)throw (Exception)cause;throw new IOException(cause);
        } finally {future.cancel(true);IO.purge();}
    }
    public static List<InetAddress> sample(InetAddress[] addresses) {
        List<InetAddress> result=new ArrayList<>();boolean v4=false,v6=false;
        for(InetAddress address:addresses) {
            if(address.isAnyLocalAddress()||address.isLoopbackAddress()||address.isMulticastAddress()||address.isLinkLocalAddress()||address.isSiteLocalAddress())continue;
            if(address instanceof Inet4Address&&!v4){result.add(address);v4=true;}
            if(address instanceof Inet6Address&&!v6){result.add(address);v6=true;}
        }
        return result;
    }
    public static String error(Throwable cause) {
        StringBuilder out=new StringBuilder();
        for(int i=0;cause!=null&&i<6;i++,cause=cause.getCause()) {
            if(i>0)out.append(" <- ");out.append(cause.getClass().getSimpleName()).append(": ");
            // Only errors generated by fixed public probes; no user URL, token or cookie input.
            String message=String.valueOf(cause.getMessage()).replaceAll("[\\r\\n\\t]"," ");
            out.append(message.substring(0,Math.min(500,message.length())));
        }
        return out.toString();
    }
    public void run(boolean direct,Consumer<String> log) {
        long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(totalMillis);
        int wildcard=0,httpsSuccess=0;boolean permission=false,controlSuccess=false;
        try {
            for(int h=0;h<hosts.length&&!cancelled;h++) {
                if(System.nanoTime()>=deadline){log.accept("达到总时限，剩余测试未运行。");break;}
                String host=hosts[h];log.accept("\n["+(h+1)+"/"+hosts.length+"] "+host+(h==0?"（对照网站）":"（漫画线路）"));
                InetAddress[] addresses=new InetAddress[0];boolean zero=false,httpsFailed=false;
                try {
                    addresses=step(()->operations.dns(host),deadline);
                    if(addresses.length==0)log.accept("DNS：未返回地址");
                    for(int i=0;i<Math.min(addresses.length,16);i++) {
                        InetAddress a=addresses[i];if(a.isAnyLocalAddress()){wildcard++;zero=true;}
                        log.accept("DNS："+a.getHostAddress()+(a.isAnyLocalAddress()?" [异常：未指定地址]":a.isLoopbackAddress()?" [回环地址]":""));
                    }
                } catch(Exception e){String detail=error(e);log.accept("DNS 失败："+detail);permission|=denied(detail);}
                if(cancelled)break;
                try {
                    long begin=System.nanoTime();String result=step(()->operations.https(host),deadline);
                    log.accept("系统 HTTPS："+result+"，"+TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-begin)+" ms");
                    httpsSuccess++;if(h==0)controlSuccess=true;
                } catch(Exception e){httpsFailed=true;String detail=error(e);log.accept("系统 HTTPS 失败："+detail);permission|=denied(detail);}
                if(zero&&httpsFailed&&operations.hasFallback()&&!cancelled){
                    log.accept("尝试本应用备用 DNS 下载路径（保留证书校验）…");
                    try{log.accept("备用路径："+step(()->operations.fallback(host),deadline,30000));}
                    catch(Exception e){log.accept("备用路径失败："+error(e));}
                }
                if(direct)for(InetAddress address:sample(addresses)) {
                    if(cancelled||System.nanoTime()>=deadline)break;
                    try {log.accept("直连 "+address.getHostAddress()+"："+step(()->operations.direct(host,address),deadline));}
                    catch(Exception e){String detail=error(e);log.accept("直连 "+address.getHostAddress()+" 失败："+detail);permission|=denied(detail);}
                }
            }
        } finally {
            operations.cancel();
            log.accept("\n"+(cancelled?"已停止，以下为部分结果。":"本轮检测结束。"));
            if(wildcard>0)log.accept("观察到 DNS 实际返回全零地址：检查私人 DNS、广告过滤/VPN 与网络解析；换网络后重新检测。");
            if(permission)log.accept("观察到 EACCES/EPERM：检查 JM Batch 的 WLAN、移动数据联网许可及系统管理策略。");
            if(!cancelled&&httpsSuccess==0)log.accept("未取得系统 HTTPS 响应，包括对照站；优先检查当前网络、应用联网许可及代理/VPN。对照站本身也可能不可达。");
            else if(controlSuccess&&httpsSuccess==1)log.accept("对照站可达，漫画线路均未取得系统 HTTPS 响应：请结合上方备用路径结果，比较目标域名解析、过滤与线路可达性。");
            log.accept("此检测以 JM Batch 自身身份执行，但单次结果不能保证所有网络与服务器始终可用。HTTP 403/404/405 也只证明已收到 HTTPS 响应，未验证登录或漫画下载。");
            log.accept("请分别保留 Wi-Fi、移动数据两份报告；不要清理漫画或重置下载记录。");
        }
    }
    private static boolean denied(String text){return text.matches("(?is).*(?:\\bEACCES\\b|\\bEPERM\\b|permission denied|operation not permitted).*");}
}
