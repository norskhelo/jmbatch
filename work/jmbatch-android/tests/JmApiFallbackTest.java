package app.jmbatch.android;

import java.io.*;
import java.lang.reflect.Method;
import java.lang.reflect.InvocationTargetException;
import java.net.*;
import java.security.Principal;
import java.security.cert.Certificate;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import javax.net.ssl.*;

/** Deterministic end-to-end production transfer with synthetic wire DNS and HTTP. */
public final class JmApiFallbackTest {
    static int checks,dnsCalls,originCalls,ipCalls;
    static String mode="ok";static final List<String> notices=new ArrayList<>();
    static final List<Connection> connections=new ArrayList<>();
    static CountDownLatch entered,closed;
    static AtomicLong time;static int systemDelay,failedIpDelay;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("fallback transport check "+checks);}
    static class Connection extends HttpsURLConnection {
        final boolean dns;byte[] body;
        Connection(URL url){super(url);dns=url.getHost().equals("dns.alidns.com")||url.getHost().equals("doh.pub");connections.add(this);}
        public void connect(){}public boolean usingProxy(){return false;}
        public void disconnect(){if(dns&&mode.equals("cancel"))closed.countDown();}
        public int getResponseCode()throws IOException {
            if(dns){
                dnsCalls++;check(getRequestProperty("Cookie")==null&&getRequestProperty("token")==null&&getRequestProperty("Referer")==null);
                check(!getInstanceFollowRedirects()&&getRequestMethod().equals("GET"));
                if(mode.equals("cancel")){entered.countDown();try{closed.await(4,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}throw new IOException("cancelled DNS");}
                try{body=mode.equals("bad-dns")?FallbackDnsTest.answer(FallbackDnsTest.query(url),"0.0.0.0",60):FallbackDnsTest.reply(url,60);}catch(Exception e){throw new IOException(e);}return 200;
            }
            if(url.getHost().equals("api.test")){
                originCalls++;
                if(systemDelay>0)try{Thread.sleep(systemDelay);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
                if(mode.equals("normal")||mode.equals("recover-system"))return 200;
                if(mode.equals("denied"))return 429;
                if(mode.equals("tls"))throw new SSLHandshakeException("certificate rejected");
                if(mode.equals("local-zero"))throw new ConnectException("Failed to connect to api.test/93.184.216.34 from /:: (port 0)");
                throw new ConnectException("Failed to connect to api.test/[::]:443");
            }
            ipCalls++;check(getRequestProperty("Host").equals("api.test"));check(getSSLSocketFactory() instanceof OriginTls);
            check(url.getFile().equals("/data?id=123&flag=a%20b"));
            check(getRequestProperty("token").equals("test-token"));check(getRequestProperty("Cookie").contains("session=private"));
            if(mode.equals("first-ip")&&url.getHost().equals("93.184.216.34")){
                if(failedIpDelay>0)try{Thread.sleep(failedIpDelay);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
                throw new ConnectException("refused");
            }
            if(mode.equals("recover-system"))throw new ConnectException("network changed");
            if(mode.equals("fallback-tls"))throw new SSLHandshakeException("certificate rejected");
            return mode.equals("fallback-denied")?403:200;
        }
        public String getContentType(){return dns?"application/dns-message":"text/plain";}
        public String getContentEncoding(){return null;}
        public long getContentLengthLong(){return mode.equals("short")?8:2;}
        public Map<String,List<String>> getHeaderFields(){return Collections.emptyMap();}
        public InputStream getInputStream(){return new ByteArrayInputStream(dns?body:new byte[]{79,75});}
        public String getCipherSuite(){return "TLS_TEST";}
        public Certificate[] getLocalCertificates(){return null;}
        public Certificate[] getServerCertificates(){return new Certificate[0];}
        public Principal getPeerPrincipal(){return null;}public Principal getLocalPrincipal(){return null;}
    }
    static JmApi api(String scenario){
        mode=scenario;dnsCalls=originCalls=ipCalls=0;notices.clear();connections.clear();
        time=new AtomicLong(1000);systemDelay=failedIpDelay=0;
        JmApi.Control control=new JmApi.Control();control.routeMessage=notices::add;
        FallbackDns dns=new FallbackDns(host->new InetAddress[]{InetAddress.getByAddress(mode.equals("local-zero")?new byte[]{93,(byte)184,(byte)216,34}:new byte[4])},time::get);
        return new JmApi(new Store.Settings(),"session=private",control,dns);
    }
    static String request(JmApi api)throws Exception {
        Method method=JmApi.class.getDeclaredMethod("text",String.class,Map.class,boolean.class,int.class);method.setAccessible(true);
        try{return (String)method.invoke(api,"https://api.test/data?id=123&flag=a%20b",Collections.singletonMap("token","test-token"),true,25);}
        catch(InvocationTargetException e){throw (Exception)e.getCause();}
    }
    static void rejected(JmApi api,Class<?> expected)throws Exception{try{request(api);throw new AssertionError("unexpected success");}catch(Exception error){check(expected.isInstance(error));}}
    public static void main(String[] args)throws Exception {
        URL.setURLStreamHandlerFactory(protocol->new URLStreamHandler(){protected URLConnection openConnection(URL url){return new Connection(url);}});
        if(args.length>0&&args[0].equals("benchmark")){
            JmApi measured=api("first-ip");systemDelay=15;failedIpDelay=25;long start=System.nanoTime();
            for(int i=0;i<40;i++)request(measured);
            Set<Object> factories=Collections.newSetFromMap(new IdentityHashMap<>());
            for(Connection connection:connections)if(!connection.dns&&!connection.getURL().getHost().equals("api.test"))factories.add(connection.getSSLSocketFactory());
            System.out.println("Synthetic 40-request overhead only: ms="+(System.nanoTime()-start)/1000000+", system="+originCalls+", DNS="+dnsCalls+", IP="+ipCalls+", TLS policies="+factories.size());return;
        }
        JmApi api=api("normal");check(request(api).equals("OK"));check(dnsCalls==0&&ipCalls==0);
        api=api("ok");check(request(api).equals("OK"));check(dnsCalls==2&&originCalls==1&&ipCalls==1);check(request(api).equals("OK"));check(dnsCalls==2&&originCalls==1&&ipCalls==2);
        Connection first=connections.get(connections.size()-2),second=connections.get(connections.size()-1);
        check(first.getSSLSocketFactory()==second.getSSLSocketFactory());check(first.getHostnameVerifier()==second.getHostnameVerifier());
        check(second.getReadTimeout()==25000&&second.getConnectTimeout()==4000);
        check(notices.stream().filter(s->s.contains("连接已响应")).count()==1);
        api=api("denied");rejected(api,NetworkRoutes.HttpFailure.class);check(dnsCalls==0&&ipCalls==0);
        api=api("tls");rejected(api,SSLHandshakeException.class);check(dnsCalls==0&&ipCalls==0);
        api=api("local-zero");rejected(api,ConnectException.class);check(dnsCalls==0&&ipCalls==0);
        api=api("fallback-denied");rejected(api,NetworkRoutes.HttpFailure.class);check(ipCalls==1);
        api=api("first-ip");check(request(api).equals("OK"));check(ipCalls==2);
        check(request(api).equals("OK"));check(ipCalls==3&&originCalls==1&&dnsCalls==2);
        time.addAndGet(60001);check(request(api).equals("OK"));check(originCalls==2&&dnsCalls==4&&ipCalls==5);
        api=api("ok");request(api);mode="recover-system";check(request(api).equals("OK"));check(originCalls==2&&dnsCalls==2&&ipCalls==3);
        check(request(api).equals("OK"));check(originCalls==3&&ipCalls==3);
        api=api("ok");request(api);mode="fallback-tls";rejected(api,SSLHandshakeException.class);check(originCalls==1&&dnsCalls==2&&ipCalls==2);
        api=api("short");rejected(api,EOFException.class);check(ipCalls==1);
        api=api("bad-dns");rejected(api,FallbackDns.Failure.class);check(dnsCalls==4&&ipCalls==0);
        ProxySelector previous=ProxySelector.getDefault();
        JmApi cachedProxy=api("ok");request(cachedProxy);
        try{ProxySelector.setDefault(new ProxySelector(){public List<Proxy> select(URI uri){return Collections.singletonList(new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",8080)));}public void connectFailed(URI u,SocketAddress a,IOException e){}});rejected(cachedProxy,ConnectException.class);check(originCalls==2&&ipCalls==1&&dnsCalls==2);}finally{ProxySelector.setDefault(previous);}
        try{ProxySelector.setDefault(new ProxySelector(){public List<Proxy> select(URI uri){return Collections.singletonList(new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",8080)));}public void connectFailed(URI u,SocketAddress a,IOException e){}});api=api("ok");rejected(api,ConnectException.class);check(dnsCalls==0&&ipCalls==0);}finally{ProxySelector.setDefault(previous);}
        JmApi cancelling=api("cancel");entered=new CountDownLatch(1);closed=new CountDownLatch(1);AtomicReference<Throwable> failure=new AtomicReference<>();
        Thread worker=new Thread(()->{try{request(cancelling);failure.set(new AssertionError("cancel returned success"));}catch(Throwable e){failure.set(e);}});
        worker.start();check(entered.await(2,TimeUnit.SECONDS));cancelling.control.cancel("STOP");worker.join(2000);
        check(!worker.isAlive()&&failure.get() instanceof IOException&&failure.get().getMessage().equals("STOP"));check(dnsCalls==1&&ipCalls==0);
        System.out.println("JmApiFallbackTest: "+checks+" checks passed");
    }
}
