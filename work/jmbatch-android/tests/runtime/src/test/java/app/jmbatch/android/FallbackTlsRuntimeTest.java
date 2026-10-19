package app.jmbatch.android;

import static org.junit.Assert.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import javax.net.ssl.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Real loopback TLS with Android's HTTPS stack, synthetic trust only in tests. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk={29,35},manifest=Config.NONE,instrumentedPackages={"com.android.okhttp"})
public class FallbackTlsRuntimeTest {
    static SSLContext clientContext,untrustedContext;static Path fixtureStore;
    @BeforeClass public static void fixture()throws Exception {
        Path directory=Files.createTempDirectory("jm-dns-tls-fixture"),store=directory.resolve("fixture.p12");fixtureStore=store;
        String keytool=Paths.get(System.getProperty("java.home"),"bin","keytool.exe").toString();
        Process process=new ProcessBuilder(keytool,"-genkeypair","-alias","fixture","-keyalg","RSA","-keysize","2048","-validity","2","-dname","CN=tls-fixture.test","-ext","SAN=dns:tls-fixture.test","-storetype","PKCS12","-keystore",store.toString(),"-storepass","test-fixture-only","-keypass","test-fixture-only","-noprompt").redirectErrorStream(true).redirectOutput(directory.resolve("keytool.log").toFile()).start();
        assertTrue(process.waitFor(20,TimeUnit.SECONDS));assertEquals(0,process.exitValue());
        KeyStore keys=KeyStore.getInstance("PKCS12");try(InputStream in=Files.newInputStream(store)){keys.load(in,"test-fixture-only".toCharArray());}
        KeyManagerFactory km=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());km.init(keys,"test-fixture-only".toCharArray());
        Object builder=Class.forName("org.conscrypt.Conscrypt").getMethod("newProviderBuilder").invoke(null);
        builder.getClass().getMethod("provideTrustManager",boolean.class).invoke(builder,true);
        Provider conscrypt=(Provider)builder.getClass().getMethod("build").invoke(builder);
        TrustManagerFactory tm=TrustManagerFactory.getInstance("PKIX",conscrypt);tm.init(keys);
        clientContext=SSLContext.getInstance("TLS",conscrypt);clientContext.init(null,tm.getTrustManagers(),null);
        TrustManagerFactory systemTrust=TrustManagerFactory.getInstance("PKIX",conscrypt);systemTrust.init((KeyStore)null);
        untrustedContext=SSLContext.getInstance("TLS",conscrypt);untrustedContext.init(null,systemTrust.getTrustManagers(),null);
    }
    static HttpsURLConnection androidConnection(URL url,SSLSocketFactory sockets)throws Exception {
        Class<?> type=Class.forName("com.android.okhttp.OkHttpClient");Object client=type.getConstructor().newInstance();
        type.getMethod("setSslSocketFactory",SSLSocketFactory.class).invoke(client,sockets);
        type.getMethod("setProxy",Proxy.class).invoke(client,Proxy.NO_PROXY);
        Class<?> factory=Class.forName("com.android.okhttp.OkUrlFactory");Object opener=factory.getConstructor(type).newInstance(client);
        return (HttpsURLConnection)factory.getMethod("open",URL.class).invoke(opener,url);
    }
    static final class Server implements AutoCloseable {
        final Process process;final int port;final Path report;final Properties result=new Properties();
        Server()throws Exception{this(1,0);}
        Server(int requests,int bodyDelay)throws Exception{
            report=Files.createTempFile("jm-tls-result",".properties");String java=Paths.get(System.getProperty("java.home"),"bin","java.exe").toString();
            String classes=System.getProperty("jm.test.classes");assertNotNull(classes);
            process=new ProcessBuilder(java,"-cp",classes,"app.jmbatch.android.TlsFixtureServer",fixtureStore.toString(),report.toString(),Integer.toString(requests),Integer.toString(bodyDelay)).redirectError(report.resolveSibling(report.getFileName()+".log").toFile()).start();
            String ready=new BufferedReader(new InputStreamReader(process.getInputStream(),StandardCharsets.US_ASCII)).readLine();assertNotNull("TLS server failed to start",ready);port=Integer.parseInt(ready);
        }
        void finish()throws Exception{assertTrue("TLS server did not exit",process.waitFor(8,TimeUnit.SECONDS));assertEquals(0,process.exitValue());try(InputStream in=Files.newInputStream(report)){result.load(in);}}
        public void close()throws Exception{if(process.isAlive())process.destroyForcibly();process.waitFor(5,TimeUnit.SECONDS);}
    }
    void exercise(String host,SSLSocketFactory trust,boolean success)throws Exception {
        try(Server server=new Server()){
            int port=server.port;URL origin=new URL("https://"+host+":"+port+"/metadata?x=a%20b");
            HttpsURLConnection connection=androidConnection(new URL("https://127.0.0.1:"+port+origin.getFile()),trust);
            OriginTls.configure(origin,connection,3000);connection.setConnectTimeout(3000);connection.setReadTimeout(3000);connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("Cookie","synthetic-session=test");
            try{
                if(success){assertEquals(200,connection.getResponseCode());try(InputStream in=connection.getInputStream()){assertEquals('O',in.read());assertEquals('K',in.read());}
                    server.finish();String headers=server.result.getProperty("headers","");assertTrue(headers.contains("Host: "+host+":"+port));assertTrue(headers.startsWith("GET /metadata?x=a%20b HTTP/1.1"));
                    assertEquals(host,server.result.getProperty("sni"));
                }else{
                    try{connection.getResponseCode();fail("invalid TLS identity was accepted");}catch(SSLException expected){for(Throwable cause=expected;cause!=null;cause=cause.getCause())assertFalse("test provider compatibility failure",cause instanceof UnsupportedOperationException);}
                    server.finish();assertEquals("",server.result.getProperty("headers",""));
                }
            }finally{connection.disconnect();}
        }
    }
    @Test public void originalHostSniCertificateAndHttpHostArePreserved()throws Exception{exercise("tls-fixture.test",clientContext.getSocketFactory(),true);}
    @Test public void trustedCertificateForWrongDomainIsRejectedBeforeCookies()throws Exception{exercise("wrong-fixture.test",clientContext.getSocketFactory(),false);}
    @Test public void untrustedCertificateIsRejectedBeforeCookies()throws Exception{exercise("tls-fixture.test",untrustedContext.getSocketFactory(),false);}
    static void readOk(HttpsURLConnection connection)throws Exception{
        assertEquals(200,connection.getResponseCode());try(InputStream input=connection.getInputStream()){assertEquals('O',input.read());assertEquals('K',input.read());assertEquals(-1,input.read());}
    }
    void reuse(boolean shared)throws Exception{
        try(Server server=new Server(8,0)){
            OriginTls.Session session=new OriginTls.Session();SSLSocketFactory base=clientContext.getSocketFactory();
            for(int page=0;page<8;page++){
                URL origin=new URL("https://tls-fixture.test:"+server.port+"/image-"+page);
                HttpsURLConnection connection=androidConnection(new URL("https://127.0.0.1:"+server.port+origin.getFile()),base);
                (shared?session:new OriginTls.Session()).configure(origin,connection,3000);
                connection.setConnectTimeout(3000);connection.setReadTimeout(3000);readOk(connection);
                // Successful production transfers close their stream, without disconnect().
            }
            server.finish();assertEquals("8",server.result.getProperty("requests"));
            assertEquals(shared?"1":"8",server.result.getProperty("connections"));
            assertEquals("0",server.result.getProperty("tlsFailures"));
        }
    }
    @Test public void repeatedSameOriginUsesOneTlsConnection()throws Exception{reuse(true);}
    @Test public void oldPerRequestPolicyRequiresEightTlsConnections()throws Exception{reuse(false);}
    @Test public void pooledSocketCannotBypassDifferentOriginCertificate()throws Exception{
        try(Server server=new Server(2,0)){
            OriginTls.Session session=new OriginTls.Session();SSLSocketFactory base=clientContext.getSocketFactory();
            URL target=new URL("https://127.0.0.1:"+server.port+"/image");
            HttpsURLConnection first=androidConnection(target,base);session.configure(new URL("https://tls-fixture.test:"+server.port+"/image"),first,3000);first.setReadTimeout(3000);readOk(first);
            HttpsURLConnection second=androidConnection(target,base);session.configure(new URL("https://wrong-fixture.test:"+server.port+"/image"),second,3000);second.setReadTimeout(3000);
            second.setRequestProperty("Cookie","must-not-be-sent=test");
            try{second.getResponseCode();fail("pooled connection crossed origin identity");}catch(SSLException expected){}finally{second.disconnect();}
            server.finish();assertEquals("1",server.result.getProperty("requests"));assertEquals("2",server.result.getProperty("connections"));assertEquals("1",server.result.getProperty("tlsFailures"));
            assertFalse(server.result.getProperty("headers","").contains("must-not-be-sent"));
        }
    }
    @Test public void bodyReadUsesConfiguredTimeoutAfterShortHandshakeBudget()throws Exception{
        try(Server server=new Server(1,1400)){
            URL origin=new URL("https://tls-fixture.test:"+server.port+"/slow-image");
            HttpsURLConnection connection=androidConnection(new URL("https://127.0.0.1:"+server.port+origin.getFile()),clientContext.getSocketFactory());
            new OriginTls.Session().configure(origin,connection,1000);connection.setConnectTimeout(1000);connection.setReadTimeout(4000);
            try{readOk(connection);server.finish();assertEquals("1",server.result.getProperty("requests"));}finally{connection.disconnect();}
        }
    }
}
