package app.jmbatch.android;

import android.os.SystemClock;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.*;
import java.util.zip.GZIPInputStream;

/** Native HTTPS implementation of the jmcomic 2.7.8 API protocol. */
public final class JmApi {
    static final String UA = "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36";
    static final String[] DEFAULT_API = {"www.cdnhjk.net", "www.cdngwc.net", "www.cdngwc.club", "www.cdngwc.cc"};
    static final String[] IMAGE_HOSTS = {"cdn-msp3.jmapinodeudzn.net", "cdn-msp.jmapiproxy1.cc", "cdn-msp.jmapinodeudzn.net", "cdn-msp.jmapiproxy2.cc", "cdn-msp3.jmapiproxy2.cc", "cdn-msp2.jmapiproxy2.cc"};
    static final String[] DOMAIN_SERVERS = {"https://rup4a04-c03.tos-cn-beijing.bytepluses.com.cn/newsvr-2025.txt", "https://rup4a04-c01.tos-ap-southeast-1.bytepluses.com/newsvr-2025.txt", "https://rup4a04-c02.tos-cn-hongkong.bytepluses.com/newsvr-2025.txt"};
    private static volatile List<String> rememberedDomains;
    private static volatile long domainsRememberedAt;
    private static final ScheduledThreadPoolExecutor HEADER_TIMER=new ScheduledThreadPoolExecutor(1,r->{
        Thread thread=new Thread(r,"jm-header-deadline");thread.setDaemon(true);return thread;
    });
    static { HEADER_TIMER.setRemoveOnCancelPolicy(true); }
    private final CookieManager cookies = new CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER);
    private final Store.Settings settings;
    private final String userCookie;
    private final FallbackDns fallbackDns;
    private final OriginTls.Session originTls=new OriginTls.Session();
    private final Set<String> dnsConnected=ConcurrentHashMap.newKeySet();
    private List<String> domains = new ArrayList<>(Arrays.asList(DEFAULT_API));
    private volatile int preferred;
    private final ImageRoutes imageRoutes = new ImageRoutes(Arrays.asList(IMAGE_HOSTS), SystemClock::elapsedRealtime);
    public final Control control;

    public static final class Control {
        public volatile String stop = "";
        public volatile String stage = "metadata";
        public java.util.function.Consumer<String> routeMessage = message -> {};
        public volatile long lastData = SystemClock.elapsedRealtime();
        public final AtomicLong bytes = new AtomicLong();
        public final AtomicLong savedBytes = new AtomicLong();
        private final Set<Request> active = Collections.newSetFromMap(new ConcurrentHashMap<Request, Boolean>());
        public void check() throws IOException { if (!stop.isEmpty() || Thread.currentThread().isInterrupted()) throw new IOException(stop.isEmpty() ? "操作已中断" : stop); }
        public void cancel(String why) {
            stop = why;
            // disconnect() can wait on a socket/stream lock. Never run it on the
            // service's main thread, or let one connection delay closing others.
            for (Request request : active) request.close(true);
        }
        private Request register(HttpURLConnection connection) {
            Request request = new Request(connection); active.add(request); return request;
        }
        private final class Request {
            final HttpURLConnection connection;
            final AtomicBoolean closing = new AtomicBoolean();
            final AtomicInteger headerState = new AtomicInteger(); // 0 waiting, 1 received, 2 expired
            ScheduledFuture<?> headerTimer;
            volatile long networkSince;
            Request(HttpURLConnection connection) { this.connection = connection; networkSince=SystemClock.elapsedRealtime(); }
            void limitHeaders(long millis) {
                headerTimer=HEADER_TIMER.schedule(()->{if(headerState.compareAndSet(0,2))close(true);},Math.max(1,millis),TimeUnit.MILLISECONDS);
            }
            void headersReceived() throws SocketTimeoutException {
                headerState.compareAndSet(0,1);
                if(headerTimer!=null)headerTimer.cancel(false);
                if(headerState.get()==2)throw new SocketTimeoutException("备用地址响应头超时");
            }
            void close(boolean background) {
                if (!closing.compareAndSet(false, true)) return;
                Runnable disconnect = () -> {
                    try { connection.disconnect(); }
                    catch (RuntimeException ignored) { /* The request still has its own timeout. */ }
                };
                if (background) {
                    // At most one closer per in-flight request (not per page),
                    // shared by repeated cancel calls and the transfer's finally.
                    Thread thread = new Thread(disconnect, "jm-disconnect");
                    thread.setDaemon(true); thread.start();
                } else disconnect.run();
            }
            void finish(boolean success) {
                headerState.compareAndSet(0,1);if(headerTimer!=null)headerTimer.cancel(false);
                active.remove(this);
                if (!success) close(false);
            }
        }
        void received(int count) { bytes.addAndGet(count); lastData = SystemClock.elapsedRealtime(); }
        void saved(long count) { savedBytes.addAndGet(count); lastData = SystemClock.elapsedRealtime(); }
        boolean networkStalled(long now,long timeout) {
            for(Request request:active){long since=request.networkSince;if(since>0&&now-since>=timeout)return true;}
            return false;
        }
    }

    public static final class HttpError extends NetworkRoutes.HttpFailure {
        HttpError(int code) { super(code); }
    }

    public JmApi(Store.Settings settings, String cookie, Control control) { this(settings,cookie,control,new FallbackDns()); }
    JmApi(Store.Settings settings,String cookie,Control control,FallbackDns fallbackDns) { this.settings=settings;userCookie=cookie;this.control=control;this.fallbackDns=fallbackDns; }

    public void initialize() throws Exception {
        List<String> cachedDomains=rememberedDomains;
        if (cachedDomains != null && SystemClock.elapsedRealtime()-domainsRememberedAt<600000) domains = NetworkRoutes.merge(cachedDomains,Arrays.asList(DEFAULT_API));
        else {
            for (String source : DOMAIN_SERVERS) {
                control.check();
                try {
                    String body = text(source, Collections.emptyMap(), false, Math.min(8, settings.timeout));
                    while (!body.isEmpty() && body.charAt(0) > 127) body = body.substring(1);
                    JSONArray servers = new JSONObject(Core.decrypt(body, "", Core.DOMAIN_SECRET)).getJSONArray("Server");
                    List<String> fresh = new ArrayList<>();
                    for (int i = 0; i < servers.length(); i++) { String host = servers.getString(i); if (host.matches("[A-Za-z0-9.-]+") && host.contains(".")) fresh.add(host); }
                    if (!fresh.isEmpty()) { domains = NetworkRoutes.merge(fresh,Arrays.asList(DEFAULT_API)); rememberedDomains = new ArrayList<>(domains); domainsRememberedAt=SystemClock.elapsedRealtime(); break; }
                } catch (Exception error) { control.check(); }
            }
        }
        // Settings initializes the API session's server cookies, avoiding wrong-album redirects.
        rawApi("/setting", false);
        control.lastData = SystemClock.elapsedRealtime();
    }

    public JSONObject detail(String type, String id) throws Exception {
        String[] reply = rawApi("/" + type + "?id=" + id, false);
        JSONObject envelope = parseJson(reply[0]);
        if (envelope.optInt("code", 0) != 200) throw new IOException("API " + envelope.optInt("code") + "：" + envelope.optString("errorMsg", "编号不存在、无权限或服务端异常"));
        Object encoded = envelope.opt("data");
        if (!(encoded instanceof String) || ((String)encoded).isEmpty()) throw new IOException("编号不存在或当前账号不可访问：" + id);
        JSONObject data = new JSONObject(Core.decrypt((String)encoded, reply[1], Core.API_SECRET));
        if (!data.has("name")) throw new IOException("编号没有可下载内容：" + id);
        if (!id.equals(data.optString("id", id))) throw new IOException("服务器返回了不同编号，可能需要有效 Cookie；已停止以免下载错误内容");
        control.lastData = SystemClock.elapsedRealtime();
        return data;
    }

    public long scramble(String chapterId) throws Exception {
        String[] reply = rawApi("/chapter_view_template?id=" + chapterId + "&mode=vertical&page=0&app_img_shunt=1&express=off&v=" + System.currentTimeMillis()/1000, true);
        Matcher match = Pattern.compile("(?:var\\s+)?scramble_id\\s*=\\s*['\"]?([0-9]+)").matcher(reply[0]);
        if (!match.find()) throw new IOException("无法取得图片解码参数；请检查登录权限或接口是否变化。未生成可能乱码的图片。");
        control.lastData = SystemClock.elapsedRealtime();
        return Long.parseLong(match.group(1));
    }

    private String[] rawApi(String path, boolean content) throws Exception {
        List<String> routes=new ArrayList<>(domains);
        Collections.rotate(routes,-preferred);
        try {
            return NetworkRoutes.run(routes,settings.retries,"漫画接口",host->{
                String ts=Long.toString(System.currentTimeMillis()/1000);
                Map<String,String> headers=new HashMap<>();
                headers.put("token",Core.md5(ts+(content?Core.CONTENT_SECRET:Core.API_SECRET)));
                headers.put("tokenparam",ts+","+Core.APP_VERSION);
                String body=text("https://"+host+path,headers,true,settings.timeout);
                if(!content)try{parseJson(body);}catch(JSONException invalid){throw new NetworkRoutes.BadResponse();}
                preferred=domains.indexOf(host);return new String[]{body,ts};
            },control::check,control.routeMessage::accept);
        } catch(NetworkRoutes.Exhausted error) {
            // Fetch a fresh list on the next task/retry instead of reusing failed discovery forever.
            rememberedDomains=null;throw error;
        }
    }

    public void image(String chapterId, String filename, File output, int retryRound) throws Exception {
        if (!filename.matches("[A-Za-z0-9._-]+") || filename.contains("..")) throw new IOException("图片文件名无效");
        try (ImageRoutes.Plan plan = imageRoutes.plan(retryRound)) {
        NetworkRoutes.run(plan.hosts,settings.retries,"图片下载",host->{
            Map<String,String> headers=new HashMap<>();
            headers.put("Referer","https://"+domains.get(preferred));headers.put("X-Requested-With","com.JMComic3.app");
            headers.put("Accept","image/webp,image/*,*/*;q=0.8");
            if(retryRound>0)headers.put("Connection","close");
            long begin = SystemClock.elapsedRealtime();
            try(FileOutputStream stream=new FileOutputStream(output)){
                transfer("https://"+host+"/media/photos/"+chapterId+"/"+filename,headers,false,settings.timeout,stream,64L*1024*1024,true);
                // Disposable raw input: only the validated, decoded cache is durably committed.
                imageRoutes.success(host, output.length(), SystemClock.elapsedRealtime() - begin); return true;
            } catch (Exception error) { control.check(); imageRoutes.failure(host, error); throw error; }
        },control::check,message->{});
        }
    }

    private String text(String url, Map<String,String> headers, boolean api, int timeout) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        transfer(url, headers, api, timeout, output, 16L*1024*1024, false);
        return new String(output.toByteArray(), StandardCharsets.UTF_8);
    }

    private void transfer(String address, Map<String,String> headers, boolean api, int timeout, OutputStream output, long maxBytes, boolean image) throws Exception {
        URL url = new URL(address); control.check();
        Response response=openResponse(url,headers,api,timeout,image,"GET");
        HttpURLConnection connection=response.connection;Control.Request request=response.request;
        boolean success = false;
        try {
            control.check(); int status = response.status;
            cookies.put(url.toURI(), connection.getHeaderFields());
            if (status != 200) throw new HttpError(status);
            try (InputStream raw = connection.getInputStream(); InputStream input = "gzip".equalsIgnoreCase(connection.getContentEncoding()) ? new GZIPInputStream(raw) : raw) {
                byte[] buffer = new byte[32768]; int n; long total = 0;
                TransferWatch watch=new TransferWatch(image&&settings.autoReset?settings.slowKB*1024L/Math.max(1,settings.threads):0,
                        settings.window*1000L);
                while (true) {
                    control.check();long begin=SystemClock.elapsedRealtime();request.networkSince=begin;
                    try { n=input.read(buffer); }
                    catch(Exception error){response.failed(error);throw error;}
                    finally { request.networkSince=0; }
                    if(n==-1)break;
                    try{watch.read(SystemClock.elapsedRealtime()-begin,n);}
                    catch(SocketTimeoutException error){response.failed(error);throw error;}
                    control.check(); total += n; if (total > maxBytes) throw new IOException("响应过大，已停止以保护手机内存/存储");
                    output.write(buffer, 0, n); if (image) control.received(n);
                }
                if (total == 0) {NetworkRoutes.BadResponse error=new NetworkRoutes.BadResponse();response.failed(error);throw error;}
                long expected = connection.getContentLengthLong();
                if (!"gzip".equalsIgnoreCase(connection.getContentEncoding()) && expected >= 0 && total != expected){
                    EOFException error=new EOFException("响应长度不完整");response.failed(error);throw error;
                }
            }
            if(response.route!=null)response.route.connected(response.ip);
            success = true;
        } catch(Exception error){
            control.check();response.failed(error);throw error;
        } finally { request.finish(success); }
    }

    private final class Response {
        final HttpURLConnection connection;final Control.Request request;final int status;
        FallbackDns.Result route;InetAddress ip;
        Response(HttpURLConnection connection,Control.Request request,int status){this.connection=connection;this.request=request;this.status=status;}
        void failed(Exception error){if(route!=null&&(routeFailure(error)||NetworkRoutes.kind(error).equals("response")))route.failed(ip,fallbackDns.clock.getAsLong());}
    }
    String probeHttps(String host)throws Exception {
        URL url=new URL("https://"+DnsWire.host(host)+"/");Response response=openResponse(url,Collections.emptyMap(),false,4,false,"HEAD");
        try{return "HTTP "+response.status+"（仅连接测试，未验证漫画接口）";}finally{response.request.finish(false);}
    }
    private Response openResponse(URL url,Map<String,String> headers,boolean api,int timeout,boolean image,String method)throws Exception {
        boolean direct=FallbackDns.permitsDirect(url);
        FallbackDns.Result cached=direct?fallbackDns.cached(url.getHost()):null;
        if(direct&&cached==null&&fallbackDns.knownZero(url.getHost()))
            cached=fallbackDns.resolve(url.getHost(),this::dnsQuery,control::check,control.routeMessage::accept);
        if(cached!=null){
            try{return fallbackResponse(url,cached,headers,api,timeout,image,method);}
            catch(Exception error){
                control.check();if(!routeFailure(error))throw error;
                // Keep address health across requests and TTL refresh. A recently
                // confirmed zero system route cannot recover this attempt.
                if(fallbackDns.knownZero(url.getHost()))throw error;
            }
        }
        try{
            Response response=response(url,(HttpURLConnection)url.openConnection(),headers,api,timeout,image,method,Math.min(8,timeout));
            if(direct)fallbackDns.systemRecovered(url.getHost());return response;
        }
        catch(Exception original){
            control.check();if(!FallbackDns.permitsDirect(url))throw original;
            boolean zero;try{zero=fallbackDns.confirmedZero(url.getHost(),original);}catch(IOException lookupFailure){throw original;}
            control.check();if(!zero)throw original;
            FallbackDns.Result result=fallbackDns.resolve(url.getHost(),this::dnsQuery,control::check,control.routeMessage::accept);
            return fallbackResponse(url,result,headers,api,timeout,image,method);
        }
    }
    private static boolean routeFailure(Exception failure){return Arrays.asList("connect","refused","unreachable","timeout","address").contains(NetworkRoutes.kind(failure));}
    private Response fallbackResponse(URL url,FallbackDns.Result result,Map<String,String> headers,boolean api,int timeout,boolean image,String method)throws Exception {
        Exception last=new ConnectException("备用地址暂时不可用");long deadline=SystemClock.elapsedRealtime()+12000;
        for(InetAddress ip:result.routes(fallbackDns.clock.getAsLong())){
            control.check();if(SystemClock.elapsedRealtime()>=deadline)break;
            int connectSeconds=Math.min(4,timeout);
            try{
                // Short connection/handshake attempts must not shorten image-body
                // reads: retain the configured inactivity timeout for the transfer.
                Response response=response(url,originTls.open(url,ip,connectSeconds*1000),headers,api,timeout,image,method,connectSeconds,deadline);
                response.route=result;response.ip=ip;
                if(dnsConnected.add(url.getHost()))control.routeMessage.accept("备用 DNS 连接已响应："+url.getHost()+"（HTTP "+response.status+"）");return response;
            }catch(Exception failure){
                control.check();last=failure;if(!routeFailure(failure))throw failure;
                result.failed(ip,fallbackDns.clock.getAsLong());
            }
        }
        control.routeMessage.accept("备用 DNS 已取得地址，但连接仍失败："+url.getHost());throw last;
    }
    private Response response(URL url,HttpURLConnection connection,Map<String,String> headers,boolean api,int timeout,boolean image,String method,int connectSeconds)throws Exception {
        return response(url,connection,headers,api,timeout,image,method,connectSeconds,0);
    }
    private Response response(URL url,HttpURLConnection connection,Map<String,String> headers,boolean api,int timeout,boolean image,String method,int connectSeconds,long deadline)throws Exception {
        connection.setRequestMethod(method);
        connection.setConnectTimeout(connectSeconds*1000); connection.setReadTimeout(timeout*1000); connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("User-Agent", UA); connection.setRequestProperty("Accept-Encoding", image ? "identity" : "gzip");
        for (Map.Entry<String,String> header : headers.entrySet()) connection.setRequestProperty(header.getKey(), header.getValue());
        for (Map.Entry<String,List<String>> header : cookies.get(url.toURI(), Collections.emptyMap()).entrySet())
            if (header.getKey() != null && !header.getValue().isEmpty()) connection.setRequestProperty(header.getKey(), String.join("; ", header.getValue()));
        if (api && !userCookie.trim().isEmpty()) connection.setRequestProperty("Cookie", userCookie);
        Control.Request request = control.register(connection);
        boolean returned = false;
        try {
            control.check();
            // Android fixes the socket read timeout when it creates a stream;
            // changing setReadTimeout after headers does not update that stream.
            // Cancel only the header attempt; retain the configured body timeout.
            if(deadline>0)request.limitHeaders(Math.min(Math.min(4000,timeout*1000),deadline-SystemClock.elapsedRealtime()));
            int status=connection.getResponseCode();
            request.headersReceived();
            if(deadline>0&&SystemClock.elapsedRealtime()>=deadline)throw new SocketTimeoutException("备用地址响应超时");
            returned=true;return new Response(connection,request,status);
        }catch(Exception error){
            if(request.headerState.get()==2)throw new SocketTimeoutException("备用地址响应头超时");throw error;
        }finally{if(!returned)request.finish(false);}
    }
    private byte[] dnsQuery(URL url,long deadline)throws Exception {
        control.check();long remaining=deadline-fallbackDns.clock.getAsLong();if(remaining<=0)throw new SocketTimeoutException();
        HttpURLConnection connection=(HttpURLConnection)url.openConnection();
        int timeout=(int)Math.max(1,Math.min(3000,remaining/2));connection.setConnectTimeout(timeout);connection.setReadTimeout(timeout);
        connection.setInstanceFollowRedirects(false);connection.setUseCaches(false);
        connection.setRequestProperty("Accept","application/dns-message");connection.setRequestProperty("Accept-Encoding","identity");
        // DNS queries deliberately use no session cookies, API tokens or request paths.
        Control.Request request=control.register(connection);
        try{
            control.check();if(connection.getResponseCode()!=200)throw new IOException("备用 DNS 服务未响应成功");
            String type=connection.getContentType();if(type==null||!type.split(";",2)[0].trim().equalsIgnoreCase("application/dns-message"))throw new IOException("备用 DNS 响应类型错误");
            try(InputStream input=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] buffer=new byte[2048];int count;
                while((count=input.read(buffer))!=-1){control.check();if(fallbackDns.clock.getAsLong()>=deadline)throw new SocketTimeoutException();if(out.size()+count>65536)throw new IOException("备用 DNS 响应过大");out.write(buffer,0,count);}
                return out.toByteArray();
            }
        }finally{request.finish(false);}
    }

    static JSONObject parseJson(String text) throws JSONException {
        int start = text.indexOf('{'), end = text.lastIndexOf('}');
        if (start < 0 || end <= start) throw new JSONException("服务器返回了非 JSON 数据，可能是访问限制或接口变化");
        return new JSONObject(text.substring(start, end + 1));
    }
}
