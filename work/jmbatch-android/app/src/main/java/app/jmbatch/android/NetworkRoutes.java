package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.util.*;
import javax.net.ssl.SSLException;

/** Bounded, request-local failover. Never changes DNS, proxies or TLS verification. */
public final class NetworkRoutes {
    public static class HttpFailure extends IOException {
        public final int code;
        public HttpFailure(int code){super("HTTP "+code+(code==429?"：服务端限流，请降低线程数后稍后重试":code==401||code==403?"：访问被拒绝，请检查 Cookie 或访问权限":code==404?"：资源不存在":"：服务器请求失败"));this.code=code;}
    }
    public static class BadResponse extends IOException { public BadResponse(){super("响应为空或格式异常");} }
    public static class Exhausted extends IOException { Exhausted(String message){super(message);} }
    public interface Request<T> { T call(String host) throws Exception; }
    public interface Check { void run() throws Exception; }
    public interface Notice { void show(String message); }
    static HttpFailure httpFailure(Throwable error) {
        for(int i=0;error!=null&&i<8;i++,error=error.getCause())if(error instanceof HttpFailure)return (HttpFailure)error;
        return null;
    }
    public static List<String> merge(List<String> primary,List<String> fallback) {
        LinkedHashSet<String> result=new LinkedHashSet<>();
        // Reserve places for the built-in fallback even if the remote list is long.
        for(List<String> source:Arrays.asList(primary,fallback))for(String value:source) {
            if(value==null)continue;String host=value.toLowerCase(Locale.ROOT);
            if(host.length()<=253&&host.matches("[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\\.[a-z]{2,63}")&&!host.contains(".."))result.add(host);
            if(result.size()>= (source==primary?8:16))break;
        }
        return new ArrayList<>(result);
    }
    static String kind(Throwable error) {
        // Android appends "from /:: (port ...)" to connect errors. That is the
        // local bind address, not a DNS answer. Inspect destinations only and
        // prefer the specific OS cause over the outer ConnectException.
        List<Throwable> chain=new ArrayList<>();
        for(int i=0;error!=null&&i<8;i++,error=error.getCause()) {
            chain.add(error);
            if(error instanceof HttpFailure)return "http";
        }
        for(Throwable cause:chain)if(cause instanceof SSLException)return "tls";
        for(Throwable cause:chain) {
            String text=String.valueOf(cause.getMessage());
            if(cause instanceof SecurityException||text.matches("(?is).*(?:\\bEACCES\\b|\\bEPERM\\b|permission denied|operation not permitted).*"))return "permission";
        }
        for(Throwable cause:chain)if(cause instanceof UnknownHostException)return "dns";
        for(Throwable cause:chain) {
            String text=String.valueOf(cause.getMessage());
            if(java.util.regex.Pattern.compile("(?i)(?:^|\\bconnect to\\s+)(?:[a-z0-9_.-]+)?/(?:\\[(?:::|(?:0:){7}0)\\](?=[:\\s)]|$)|(?:::|(?:0:){7}0)(?=[\\s)]|$)|0\\.0\\.0\\.0(?=[:\\s)]|$))").matcher(text).find())return "address";
        }
        for(Throwable cause:chain) {
            String text=String.valueOf(cause.getMessage());
            if(cause instanceof SocketTimeoutException||text.matches("(?s).*\\bETIMEDOUT\\b.*"))return "timeout";
            if(text.matches("(?s).*\\bECONNREFUSED\\b.*"))return "refused";
            if(text.matches("(?s).*\\b(?:ENETUNREACH|EHOSTUNREACH)\\b.*"))return "unreachable";
        }
        for(Throwable cause:chain) {
            error=cause;
            if(error instanceof SSLException)return "tls";
            if(error instanceof ConnectException||error instanceof NoRouteToHostException||error instanceof SocketException)return "connect";
            if(error instanceof BadResponse||error instanceof EOFException)return "response";
        }
        return "other";
    }
    static String reason(Exception error) {
        switch(kind(error)) {
            case "permission":return "系统拒绝联网（EACCES / EPERM），请检查 JM Batch 的 WLAN、移动数据权限及防火墙限制";
            case "refused":return "连接被拒绝（ECONNREFUSED），可能是目标服务或网络过滤拒绝连接";
            case "unreachable":return "网络路由不可达，请切换 Wi-Fi/移动数据并检查 VPN 或代理";
            case "address":return "连接目标出现未指定地址（:: / 0.0.0.0），可能与 DNS、代理或过滤设置有关";
            case "dns":return "DNS 解析失败，未取得服务器地址";
            case "connect":return "连接被拒绝、重置或网络不可达";
            case "timeout":return "连接或读取超时";
            case "tls":return "HTTPS 握手或证书校验失败（未关闭校验）";
            case "http":return new HttpFailure(httpFailure(error).code).getMessage();
            case "response":return "服务器响应为空、不完整或格式异常";
            default:return "请求失败";
        }
    }
    public static <T> T run(List<String> hosts,int retries,String stage,Request<T> request,Check check,Notice notice)throws Exception {
        LinkedHashMap<String,String> reasons=new LinkedHashMap<>();Map<String,Integer> counts=new HashMap<>();
        Set<String> skip=new HashSet<>();int budget=hosts.size()+Math.max(0,Math.min(5,retries)), attempts=0;
        while(attempts<budget) {
            boolean tried=false;
            for(String host:hosts) {
                if(attempts>=budget)break;if(skip.contains(host))continue;
                check.run();tried=true;attempts++;
                if(attempts>1)notice.show(stage+"：切换/重试线路 "+host+"（请求 "+attempts+"/"+budget+"）");
                try {return request.call(host);}
                catch(Exception error) {
                    check.run();String kind=kind(error);
                    if(kind.equals("other"))throw error;
                    HttpFailure http=httpFailure(error);
                    if(http!=null) {
                        if(http.code<500)throw http;
                    }
                    reasons.put(host,reason(error));counts.put(host,counts.getOrDefault(host,0)+1);
                    if(Arrays.asList("address","dns","tls","connect","permission","refused","unreachable").contains(kind))skip.add(host);
                }
            }
            if(!tried)break;
        }
        check.run();StringBuilder report=new StringBuilder(stage+"：所有可用线路均失败（"+reasons.size()+" 条，"+attempts+" 次请求）。\n");
        for(String host:reasons.keySet())report.append(host).append(" ×").append(counts.get(host)).append("：").append(reasons.get(host)).append('\n');
        report.append("请检查应用联网权限，切换 Wi-Fi/移动数据对比，并核对私人 DNS、代理及过滤设置。仅凭此错误不能确定是机型故障；重试保留已下载图片。");
        throw new Exhausted(report.toString());
    }
    private NetworkRoutes(){}
}
