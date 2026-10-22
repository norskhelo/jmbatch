package app.jmbatch.android;

import static org.junit.Assert.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import javax.net.ssl.*;

/** Uses Android's production HttpsHandler factory, not raw OkHttp defaults. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk={29,35},manifest=Config.NONE,instrumentedPackages={"com.android.okhttp"})
public class DnsTransportAuditRuntimeTest {
    @BeforeClass public static void trust()throws Exception{FallbackTlsRuntimeTest.fixture();}
    static final class Server implements AutoCloseable {
        final Process process;final int port;final Path report;final Properties result=new Properties();
        Server(int requests,int delay)throws Exception{
            report=Files.createTempFile("transport-audit-", ".properties");
            process=new ProcessBuilder(Paths.get(System.getProperty("java.home"),"bin","java.exe").toString(),
                "-cp",System.getProperty("jm.test.classes"),"app.jmbatch.android.TransportAuditServer",
                FallbackTlsRuntimeTest.fixtureStore.toString(),report.toString(),String.valueOf(requests),String.valueOf(delay))
                .redirectError(report.resolveSibling(report.getFileName()+".log").toFile()).start();
            String ready=new BufferedReader(new InputStreamReader(process.getInputStream(),StandardCharsets.US_ASCII)).readLine();
            assertNotNull("server startup failed",ready);port=Integer.parseInt(ready);
        }
        void finish()throws Exception{
            assertTrue(process.waitFor(8,TimeUnit.SECONDS));assertEquals(0,process.exitValue());
            try(InputStream input=Files.newInputStream(report)){result.load(input);}
        }
        public void close()throws Exception{if(process.isAlive())process.destroyForcibly();process.waitFor(5,TimeUnit.SECONDS);}
    }
    static final class Client {
        final Object factory;final Class<?> factoryClass;
        final OriginTls.Session session=new OriginTls.Session();
        Client()throws Exception{
            Class<?> handler=Class.forName("com.android.okhttp.HttpsHandler");
            factory=handler.getMethod("createHttpsOkUrlFactory",java.net.Proxy.class).invoke(null,java.net.Proxy.NO_PROXY);
            factoryClass=factory.getClass();Object client=factoryClass.getMethod("client").invoke(factory);Class<?> type=client.getClass();
            assertEquals("[http/1.1]",type.getMethod("getProtocols").invoke(client).toString());
            type.getMethod("setSslSocketFactory",SSLSocketFactory.class).invoke(client,FallbackTlsRuntimeTest.clientContext.getSocketFactory());
            Class<?> dns=Class.forName("com.android.okhttp.Dns");
            Object fixtureDns=java.lang.reflect.Proxy.newProxyInstance(dns.getClassLoader(),new Class[]{dns},(proxy,method,args)->{
                if(method.getName().equals("lookup"))return Collections.singletonList(InetAddress.getByName("127.0.0.1"));
                if(method.getName().equals("toString"))return "loopback fixture";
                if(method.getName().equals("hashCode"))return System.identityHashCode(proxy);
                return proxy==args[0];
            });
            type.getMethod("setDns",dns).invoke(client,fixtureDns);
        }
        void request(Server server,boolean fallback,int page,int readTimeout)throws Exception{
            URL origin=new URL("https://tls-fixture.test:"+server.port+"/image-"+page);
            URL address=fallback?new URL("https://127.0.0.1:"+server.port+origin.getFile()):origin;
            HttpsURLConnection connection=(HttpsURLConnection)factoryClass.getMethod("open",URL.class).invoke(factory,address);
            if(fallback)session.configure(origin,connection,1000);
            connection.setConnectTimeout(1000);connection.setReadTimeout(readTimeout);
            connection.setRequestProperty("Accept-Encoding","identity");
            assertEquals(200,connection.getResponseCode());int bytes=0;
            try(InputStream input=connection.getInputStream()){
                byte[] buffer=new byte[32768];int n;
                while((n=input.read(buffer))!=-1){bytes+=n;for(int i=0;i<n;i++)assertEquals(71,buffer[i]);}
            }
            assertEquals(65536,bytes);
        }
    }
    void run(boolean fallback,int parallel,int requests)throws Exception{
        try(Server server=new Server(requests,0)){
            Client client=new Client();ExecutorService pool=Executors.newFixedThreadPool(parallel);
            List<Long> windows=new ArrayList<>();
            try{
                // Separate batches expose pooling degradation and accumulation over repeated use.
                for(int first=0;first<requests;first+=8){
                    long start=System.nanoTime();List<Future<?>> tasks=new ArrayList<>();
                    for(int i=first;i<Math.min(first+8,requests);i++){final int page=i;tasks.add(pool.submit(()->{
                        try{client.request(server,fallback,page,6000);}catch(Exception error){throw new RuntimeException(error);}
                    }));}
                    for(Future<?> task:tasks)task.get(10,TimeUnit.SECONDS);
                    windows.add(TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-start));
                }
            }finally{pool.shutdownNow();}
            server.finish();Properties result=server.result;
            assertEquals(String.valueOf(requests),result.getProperty("completed"));
            int connections=Integer.parseInt(result.getProperty("connections"));
            assertTrue("connections="+connections,connections<=parallel+((requests/8)-1)*Math.max(0,parallel-5));
            if(parallel==1)assertEquals(1,connections);
            assertEquals("tls-fixture.test:"+server.port,result.getProperty("host"));
            assertTrue(result.getProperty("request-line").endsWith("HTTP/1.1"));
            for(int i=1;i<=connections;i++){
                assertEquals("tls-fixture.test",result.getProperty("sni."+i));
                assertFalse(result.getProperty("alpn-offered."+i,"").contains("h2"));
            }
            System.out.println("TRANSPORT AUDIT sdk="+android.os.Build.VERSION.SDK_INT+" fallback="+fallback+
                " parallel="+parallel+" requests="+requests+" connections="+connections+
                " batch8_ms="+windows+" protocol=HTTP/1.1 result="+result);
        }
    }
    @Test public void normalSequentialLongRun()throws Exception{run(false,1,80);}
    @Test public void fallbackSequentialLongRun()throws Exception{run(true,1,80);}
    @Test public void normalEightWorkersLongRun()throws Exception{run(false,8,80);}
    @Test public void fallbackEightWorkersLongRun()throws Exception{run(true,8,80);}
    @Test public void fallbackPooledBodyReadDoesNotUseHandshakeTimeout()throws Exception{
        try(Server server=new Server(2,1400)){
            Client client=new Client();
            client.request(server,true,1,6000);client.request(server,true,2,6000);
            server.finish();assertEquals("1",server.result.getProperty("connections"));
        }
    }
}
