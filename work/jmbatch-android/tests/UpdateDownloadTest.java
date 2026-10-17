import app.jmbatch.android.*;
import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Exercises the production HTTP loop with synthetic connections and real signature checks. */
public class UpdateDownloadTest {
    static final String URL_BASE="https://github.com/owner/app/releases/download/v1/";
    static final String ADDRESS=URL_BASE+"JMBatch-0.5.7-Android.apk";
    static int checks,opens;static String mode;static byte[] payload;
    static AtomicBoolean cancel=new AtomicBoolean();
    static List<String> calls=new ArrayList<>(),routes=new ArrayList<>();
    static void check(boolean value){checks++;if(!value)throw new AssertionError("update transport check "+checks+" / "+mode);}
    static class Connection extends HttpURLConnection {
        Connection(URL url){super(url);}
        public void connect(){}
        public void disconnect(){}
        public boolean usingProxy(){return false;}
        boolean first(){return url.getHost().equals("github.com");}
        public int getResponseCode()throws IOException {
            calls.add(url.toString());
            check("identity".equals(getRequestProperty("Accept-Encoding")));
            if(mode.equals("all")||mode.equals("third")&&!url.getHost().equals("gh-proxy.com")||mode.equals("mirror")&&first())throw new SocketTimeoutException("unavailable");
            if(mode.equals("http")&&first())return 403;
            if(mode.equals("evil")||mode.equals("redirect")&&first())return 302;
            return 200;
        }
        public String getHeaderField(String key){return key.equals("Location")?(mode.equals("evil")?"https://evil.test/file":"https://release-assets.githubusercontent.com/file?token=signed"):null;}
        public String getContentType(){return mode.equals("html")&&first()?"text/html":"application/octet-stream";}
        public long getContentLengthLong(){return mode.equals("oversize")?999999:payload.length;}
        public InputStream getInputStream(){
            if(mode.equals("cancel")){cancel.set(true);return new ByteArrayInputStream(payload);}
            if(mode.equals("partial")&&first())return new InputStream(){int n;public int read(){return -1;}public int read(byte[] b)throws IOException{if(n++>0)throw new SocketTimeoutException();b[0]=88;return 1;}};
            return new ByteArrayInputStream(mode.equals("truncated")&&first()?new byte[]{88}:payload);
        }
    }
    static void setup(String scenario){mode=scenario;payload="hello".getBytes();cancel.set(false);calls.clear();routes.clear();opens=0;}
    static byte[] download()throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        UpdateDownload.transfer(ADDRESS,()->{opens++;bytes.reset();return bytes;},65536,cancel,(route,n)->{if(n==0)routes.add(route);});
        return bytes.toByteArray();
    }
    public static void main(String[] args)throws Exception {
        URL.setURLStreamHandlerFactory(protocol->new URLStreamHandler(){protected URLConnection openConnection(URL url){return new Connection(url);}});
        setup("healthy");check(Arrays.equals(download(),payload));check(calls.size()==1&&opens==1);
        setup("mirror");check(Arrays.equals(download(),payload));check(routes.equals(Arrays.asList("GitHub","GHFast")));
        setup("third");check(Arrays.equals(download(),payload));check(routes.equals(Arrays.asList("GitHub","GHFast","GH-Proxy")));
        for(String scenario:Arrays.asList("partial","truncated","html","http")) {
            setup(scenario);check(Arrays.equals(download(),payload));check(calls.size()==2&&opens==2);
        }
        setup("all");try{download();throw new AssertionError();}catch(IOException expected){check(calls.size()==3);}
        setup("healthy");cancel.set(true);try{download();throw new AssertionError();}catch(InterruptedIOException expected){check(calls.isEmpty()&&opens==0);}
        setup("cancel");try{download();throw new AssertionError();}catch(InterruptedIOException expected){check(calls.size()==1);}
        setup("oversize");try{download();throw new AssertionError();}catch(SecurityException expected){check(calls.size()==1);}
        setup("evil");try{download();throw new AssertionError();}catch(SecurityException expected){check(calls.size()==1);}
        setup("redirect");check(Arrays.equals(download(),payload));check(calls.size()==2&&routes.size()==1);
        for(String operation:Arrays.asList("open","write","close")) {
            setup(operation.equals("close")?"all":"healthy");
            try {
                UpdateDownload.transfer(ADDRESS,()->{
                    if(operation.equals("open"))throw new IOException("disk");
                    return new OutputStream(){public void write(int b)throws IOException{if(operation.equals("write"))throw new IOException("disk");}public void close()throws IOException{if(operation.equals("close"))throw new IOException("disk");}};
                },65536,cancel,(r,n)->{});throw new AssertionError();
            }catch(IOException expected){check(expected.getMessage().equals("disk"));check(calls.size()<2);}
        }
        for(String bad:Arrays.asList(ADDRESS.replace("https:","http:"),ADDRESS+"?token=private",ADDRESS+"#x",ADDRESS.replace("github.com","user@github.com"),ADDRESS.replace("github.com","github.com.evil.test"),ADDRESS.replace("/v1/","/%2e%2e/"),ADDRESS.replace("/v1/","/v1%2fother/"),"https://ghfast.top/"+ADDRESS)) {
            try{UpdateDownload.validate(bad);throw new AssertionError(bad);}catch(SecurityException expected){check(true);}
        }
        for(String bad:Arrays.asList("https://ghfast.top.evil.test/"+ADDRESS,"http://ghfast.top/"+ADDRESS,"https://ghfast.top/"+ADDRESS+"?x=1","https://ghfast.top/"+ADDRESS.replace("/owner/","/evil/"),"https://evil.test/a"))check(!UpdateDownload.allowed(new URL(bad),ADDRESS));
        check(UpdateDownload.allowed(new URL("https://ghfast.top/"+ADDRESS),ADDRESS));
        check(UpdateDownload.allowed(new URL("https://gh-proxy.com/"+ADDRESS),ADDRESS));
        // Signed bytes fetched through the mirror still pass the original public key.
        setup("mirror");payload=Files.readAllBytes(Paths.get(args[1],"manifest.bin"));byte[] manifest=download();
        setup("mirror");payload=Files.readAllBytes(Paths.get(args[1],"manifest.sig"));byte[] signature=download();
        UpdateCrypto.verify(manifest,signature);check(true);
        signature[0]^=1;try{UpdateCrypto.verify(manifest,signature);throw new AssertionError();}catch(SecurityException expected){check(true);}
        setup("mirror");Path file=Paths.get(args[0],"mirror.apk");Files.createDirectories(file.getParent());Files.write(file,download());
        UpdateCrypto.verifyFile(file.toFile(),5,"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");check(true);
        Files.write(file,"Hello".getBytes());try{UpdateCrypto.verifyFile(file.toFile(),5,"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");throw new AssertionError();}catch(Exception expected){check(true);}
        System.out.println("UpdateDownloadTest: "+checks+" checks passed");
    }
}
