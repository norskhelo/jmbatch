package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;

/** Host-only synthetic URL transport; build.py supplies Store/SystemClock stubs. */
public class JmApiTransportTest {
    static int checks, disconnects;
    static String mode;
    static final List<String> calls=new ArrayList<>();
    static void check(boolean v){checks++;if(!v)throw new AssertionError("transport check "+checks);}
    static class Connection extends HttpURLConnection {
        Connection(URL url){super(url);}
        public void connect(){}
        public void disconnect(){disconnects++;}
        public boolean usingProxy(){return false;}
        public int getResponseCode()throws IOException {
            calls.add(url.getHost());
            if(mode.equals("denied"))return 429;
            if(url.getHost().equals(JmApi.IMAGE_HOSTS[0])) {
                if(mode.equals("failure"))throw new ConnectException("synthetic unavailable");
                if(mode.equals("slow"))try{Thread.sleep(40);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
            }
            return 200;
        }
        public Map<String,List<String>> getHeaderFields(){return Collections.emptyMap();}
        public long getContentLengthLong(){return mode.equals("trickle")?128:1024;}
        public String getContentEncoding(){return null;}
        public InputStream getInputStream() throws IOException {
            check(getRequestProperty("Accept-Encoding").equals("identity"));
            if(mode.equals("timeout")&&url.getHost().equals(JmApi.IMAGE_HOSTS[0]))
                throw new SocketTimeoutException("synthetic read timeout");
            if(mode.equals("trickle"))return new InputStream(){
                int count;
                public int read(){if(count==128)return -1;android.os.SystemClock.advance(1000);return count++;}
                public int read(byte[] buffer,int offset,int length){if(length==0)return 0;int n=read();if(n<0)return -1;buffer[offset]=(byte)n;return 1;}
            };
            return new ByteArrayInputStream(new byte[mode.equals("truncated")&&url.getHost().equals(JmApi.IMAGE_HOSTS[0])?512:1024]);
        }
    }
    static JmApi api(String scenario){mode=scenario;calls.clear();disconnects=0;return new JmApi(new Store.Settings(),"",new JmApi.Control(),new FallbackDns(h->new InetAddress[]{InetAddress.getByAddress(new byte[]{93,(byte)184,(byte)216,34})},()->System.nanoTime()/1000000));}
    public static void main(String[] args)throws Exception {
        URL.setURLStreamHandlerFactory(protocol->new URLStreamHandler(){protected URLConnection openConnection(URL url){return new Connection(url);}});
        Path root=Path.of(args[0]);Files.createDirectories(root);
        JmApi api=api("failure");
        for(int i=0;i<16;i++)api.image("123456",i+".jpg",root.resolve(i+".raw").toFile(),0);
        check(Collections.frequency(calls,JmApi.IMAGE_HOSTS[0])==1);check(api.control.bytes.get()==16384);check(disconnects==1);
        api=api("slow");
        for(int i=0;i<16;i++)api.image("123456",i+".jpg",root.resolve(i+".raw").toFile(),0);
        check(calls.subList(8,16).stream().noneMatch(h->h.equals(JmApi.IMAGE_HOSTS[0])));check(disconnects==0);
        // Legacy defaults enable slow detection (30 KB/s, 90 s). A 1 B/s body
        // must finish on its original connection beyond that observation window.
        api=api("trickle");api.image("123456","1.jpg",root.resolve("trickle.raw").toFile(),0);
        byte[] body=Files.readAllBytes(root.resolve("trickle.raw"));
        check(calls.size()==1);check(disconnects==0);check(body.length==128);check(api.control.bytes.get()==128);
        for(int i=0;i<body.length;i++)check(body[i]==(byte)i);
        check(api.control.stop.isEmpty());
        api=api("timeout");api.image("123456","1.jpg",root.resolve("timeout.raw").toFile(),0);
        check(calls.size()==2);check(disconnects==1);check(Files.size(root.resolve("timeout.raw"))==1024);
        api=api("truncated");api.image("123456","1.jpg",root.resolve("truncated.raw").toFile(),0);
        check(calls.size()==2);check(Files.size(root.resolve("truncated.raw"))==1024);check(api.control.bytes.get()==1536);check(disconnects==1);
        api=api("denied");
        try{api.image("123456","1.jpg",root.resolve("denied.raw").toFile(),0);throw new AssertionError();}
        catch(NetworkRoutes.HttpFailure e){check(e.code==429&&calls.size()==1);}
        api=api("healthy");api.control.cancel("PAUSE");
        try{api.image("123456","1.jpg",root.resolve("cancel.raw").toFile(),0);throw new AssertionError();}
        catch(IOException e){check(calls.isEmpty());}
        System.out.println("JmApiTransportTest: "+checks+" checks passed");
    }
}
