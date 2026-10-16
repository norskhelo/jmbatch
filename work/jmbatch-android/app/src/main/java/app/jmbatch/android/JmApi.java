package app.jmbatch.android;

import android.os.SystemClock;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
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
    private final CookieManager cookies = new CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER);
    private final Store.Settings settings;
    private final String userCookie;
    private List<String> domains = new ArrayList<>(Arrays.asList(DEFAULT_API));
    private volatile int preferred;
    public final Control control;

    public static final class Control {
        public volatile String stop = "";
        public volatile String stage = "metadata";
        public java.util.function.Consumer<String> routeMessage = message -> {};
        public volatile long lastData = SystemClock.elapsedRealtime();
        public final AtomicLong bytes = new AtomicLong();
        private final Set<HttpURLConnection> active = Collections.newSetFromMap(new ConcurrentHashMap<HttpURLConnection, Boolean>());
        public void check() throws IOException { if (!stop.isEmpty() || Thread.currentThread().isInterrupted()) throw new IOException(stop.isEmpty() ? "操作已中断" : stop); }
        public void cancel(String why) { stop = why; for (HttpURLConnection connection : active) connection.disconnect(); }
        void received(int count) { bytes.addAndGet(count); lastData = SystemClock.elapsedRealtime(); }
    }

    public static final class HttpError extends NetworkRoutes.HttpFailure {
        HttpError(int code) { super(code); }
    }

    public JmApi(Store.Settings settings, String cookie, Control control) { this.settings = settings; userCookie = cookie; this.control = control; }

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
        List<String> routes=new ArrayList<>(Arrays.asList(IMAGE_HOSTS));Collections.rotate(routes,-retryRound);
        NetworkRoutes.run(routes,settings.retries,"图片下载",host->{
            Map<String,String> headers=new HashMap<>();
            headers.put("Referer","https://"+domains.get(preferred));headers.put("X-Requested-With","com.JMComic3.app");
            headers.put("Accept","image/webp,image/*,*/*;q=0.8");
            if(retryRound>0)headers.put("Connection","close");
            try(FileOutputStream stream=new FileOutputStream(output)){
                transfer("https://"+host+"/media/photos/"+chapterId+"/"+filename,headers,false,settings.timeout,stream,64L*1024*1024,true);
                stream.getFD().sync();return true;
            }
        },control::check,message->{});
    }

    private String text(String url, Map<String,String> headers, boolean api, int timeout) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        transfer(url, headers, api, timeout, output, 16L*1024*1024, false);
        return new String(output.toByteArray(), StandardCharsets.UTF_8);
    }

    private void transfer(String address, Map<String,String> headers, boolean api, int timeout, OutputStream output, long maxBytes, boolean image) throws Exception {
        URL url = new URL(address); control.check();
        HttpURLConnection connection = (HttpURLConnection)url.openConnection();
        connection.setConnectTimeout(Math.min(8,timeout)*1000); connection.setReadTimeout(timeout*1000); connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("User-Agent", UA); connection.setRequestProperty("Accept-Encoding", "gzip");
        for (Map.Entry<String,String> header : headers.entrySet()) connection.setRequestProperty(header.getKey(), header.getValue());
        for (Map.Entry<String,List<String>> header : cookies.get(url.toURI(), Collections.emptyMap()).entrySet())
            if (header.getKey() != null && !header.getValue().isEmpty()) connection.setRequestProperty(header.getKey(), String.join("; ", header.getValue()));
        if (api && !userCookie.trim().isEmpty()) connection.setRequestProperty("Cookie", userCookie);
        control.active.add(connection);
        boolean success = false;
        try {
            control.check(); int status = connection.getResponseCode();
            cookies.put(url.toURI(), connection.getHeaderFields());
            if (status != 200) throw new HttpError(status);
            try (InputStream raw = connection.getInputStream(); InputStream input = "gzip".equalsIgnoreCase(connection.getContentEncoding()) ? new GZIPInputStream(raw) : raw) {
                byte[] buffer = new byte[32768]; int n; long total = 0;
                while ((n = input.read(buffer)) != -1) {
                    control.check(); total += n; if (total > maxBytes) throw new IOException("响应过大，已停止以保护手机内存/存储");
                    output.write(buffer, 0, n); if (image) control.received(n);
                }
                if (total == 0) throw new NetworkRoutes.BadResponse();
            }
            success = true;
        } finally {
            control.active.remove(connection);
            // Closing the response permits Android's HTTP stack to reuse keep-alive connections.
            if (!success) connection.disconnect();
        }
    }

    static JSONObject parseJson(String text) throws JSONException {
        int start = text.indexOf('{'), end = text.lastIndexOf('}');
        if (start < 0 || end <= start) throw new JSONException("服务器返回了非 JSON 数据，可能是访问限制或接口变化");
        return new JSONObject(text.substring(start, end + 1));
    }
}
