package app.jmbatch.android;

import static org.junit.Assert.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import javax.net.ssl.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk={29,35},manifest=Config.NONE,instrumentedPackages={"com.android.okhttp"})
public class DownloadRecoveryRuntimeTest {
    @BeforeClass public static void trust()throws Exception{FallbackTlsRuntimeTest.fixture();}
    Object response(JmApi api,URL origin,HttpsURLConnection connection,long budget)throws Exception {
        Method method=JmApi.class.getDeclaredMethod("response",URL.class,HttpURLConnection.class,Map.class,boolean.class,int.class,boolean.class,String.class,int.class,long.class);
        method.setAccessible(true);
        try{return method.invoke(api,origin,connection,Collections.emptyMap(),false,6,true,"GET",4,android.os.SystemClock.elapsedRealtime()+budget);}
        catch(InvocationTargetException error){throw (Exception)error.getCause();}
    }
    void finish(Object response,boolean success)throws Exception{
        Field field=response.getClass().getDeclaredField("request");field.setAccessible(true);Object request=field.get(response);
        Method finish=request.getClass().getDeclaredMethod("finish",boolean.class);finish.setAccessible(true);finish.invoke(request,success);
    }
    @Test public void headerDeadlineCancelsSocketBeforeBodyTimeout()throws Exception{
        try(DnsTransportAuditRuntimeTest.Server server=new DnsTransportAuditRuntimeTest.Server(1,-5000)){
            DnsTransportAuditRuntimeTest.Client client=new DnsTransportAuditRuntimeTest.Client();
            URL origin=new URL("https://tls-fixture.test:"+server.port+"/slow-headers");
            HttpsURLConnection connection=(HttpsURLConnection)client.factoryClass.getMethod("open",URL.class).invoke(client.factory,new URL("https://127.0.0.1:"+server.port+"/slow-headers"));
            client.session.configure(origin,connection,4000);
            JmApi api=new JmApi(new Store.Settings(),"",new JmApi.Control());long started=System.nanoTime();
            try{response(api,origin,connection,1500);fail("headers must time out");}catch(SocketTimeoutException expected){}
            assertTrue("header deadline did not close blocked socket",TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-started)<3500);
            assertEquals("header timer must not cancel the whole task","",api.control.stop);
        }
    }
    @Test public void headerDeadlineDoesNotShortenBodyReadsOrPooledRequests()throws Exception{
        try(DnsTransportAuditRuntimeTest.Server server=new DnsTransportAuditRuntimeTest.Server(2,1800)){
            DnsTransportAuditRuntimeTest.Client client=new DnsTransportAuditRuntimeTest.Client();JmApi api=new JmApi(new Store.Settings(),"",new JmApi.Control());
            for(int page=0;page<2;page++){
                URL origin=new URL("https://tls-fixture.test:"+server.port+"/page-"+page);
                HttpsURLConnection connection=(HttpsURLConnection)client.factoryClass.getMethod("open",URL.class).invoke(client.factory,new URL("https://127.0.0.1:"+server.port+origin.getFile()));
                client.session.configure(origin,connection,4000);Object reply=response(api,origin,connection,1500);
                int count=0;try(InputStream input=connection.getInputStream()){byte[] buffer=new byte[32768];int n;while((n=input.read(buffer))!=-1)count+=n;}
                assertEquals(65536,count);assertEquals(6000,connection.getReadTimeout());finish(reply,true);
            }
            server.finish();assertEquals("1",server.result.getProperty("connections"));
        }
    }
    @Test public void filledProcessingQueueDoesNotReconnectAndSpeedUsesOnlyCommittedBytes()throws Exception{
        Store.Task task=new Store.Task("123456",new Store.Settings());task.status="running";
        JmApi.Control control=new JmApi.Control();control.stage="download";
        Class<?> type=Class.forName("app.jmbatch.android.DownloadService$DownloadJob");
        Constructor<?> constructor=type.getDeclaredConstructor(DownloadService.class,Store.Task.class);constructor.setAccessible(true);
        Object job=constructor.newInstance(new DownloadService(),task);Field field=type.getDeclaredField("control");field.setAccessible(true);field.set(job,control);
        Method monitor=type.getDeclaredMethod("monitor",long.class);monitor.setAccessible(true);long start=1000;monitor.invoke(job,start);
        CountDownLatch filled=new CountDownLatch(12),release=new CountDownLatch(1);AtomicInteger processed=new AtomicInteger();AtomicReference<Throwable> failure=new AtomicReference<>();
        List<Integer> pages=new ArrayList<>();for(int i=0;i<24;i++)pages.add(i);
        Thread worker=new Thread(()->{try{ImagePipeline.run(pages,8,4,p->{control.received(1024*1024);filled.countDown();},p->{release.await();processed.incrementAndGet();control.saved(512*1024);},p->{},control::check,()->control.cancel("ABORT"),1);}catch(Throwable e){failure.set(e);}});
        worker.start();try{
            assertTrue(filled.await(3,TimeUnit.SECONDS));
            for(int second=1;second<=240;second++)monitor.invoke(job,start+second*1000);
            assertEquals("",control.stop);assertEquals(0,task.speed);assertEquals(0,processed.get());
        }finally{release.countDown();worker.join(5000);}
        assertFalse(worker.isAlive());assertNull(failure.get());assertEquals(24,processed.get());
        monitor.invoke(job,start+241000);assertEquals(12*1024*1024,task.speed);
        monitor.invoke(job,start+242000);assertEquals(0,task.speed);
        control.stage="page_retry";monitor.invoke(job,start+243000);control.saved(4096);monitor.invoke(job,start+244000);assertEquals(4096,task.speed);
        task.status="paused";monitor.invoke(job,start+245000);assertEquals(0,task.speed);
    }
}
