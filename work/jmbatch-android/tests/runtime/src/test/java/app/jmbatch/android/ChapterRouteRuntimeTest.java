package app.jmbatch.android;

import java.net.*;
import java.util.*;
import java.time.Duration;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowSystemClock;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},instrumentedPackages={"app.jmbatch.android"},shadows={ChapterRouteRuntimeTest.Transport.class})
public class ChapterRouteRuntimeTest {
    static int discovery;
    static boolean offline;
    static List<String> settingHosts;
    @Implements(value=JmApi.class,isInAndroidSdk=false)
    public static class Transport {
        @Implementation protected String text(String address,Map<String,String> headers,boolean api,int timeout)throws Exception {
            URL url=new URL(address);
            if(!api){discovery++;throw new SocketTimeoutException("discovery unavailable");}
            assertEquals("/setting",url.getPath());settingHosts.add(url.getHost());
            if(offline||url.getHost().equals(JmApi.DEFAULT_API[0]))throw new ConnectException("route unavailable");
            return "{}";
        }
    }
    private void open()throws Exception {
        Store.Settings settings=new Store.Settings();settings.retries=0;
        ChapterUpdates.open(settings,"",new JmApi.Control());
    }
    @Test public void successfulBuiltinRouteIsReusedUntilFailureOrExpiry()throws Exception {
        settingHosts=new ArrayList<>();discovery=0;offline=false;
        open();assertEquals(3,discovery);String working=settingHosts.get(settingHosts.size()-1);
        settingHosts.clear();open();assertEquals(Collections.singletonList(working),settingHosts);assertEquals(3,discovery);
        offline=true;try{open();fail();}catch(NetworkRoutes.Exhausted expected){}
        offline=false;open();assertEquals(6,discovery);
        ShadowSystemClock.advanceBy(Duration.ofMinutes(3));open();assertEquals(9,discovery);
    }
}
