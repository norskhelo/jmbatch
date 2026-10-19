package app.jmbatch.android;

import javax.net.ssl.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Separate JVM keeps server crypto independent of Robolectric's Android providers. */
public final class TlsFixtureServer {
    public static void main(String[] args)throws Exception{
        KeyStore keys=KeyStore.getInstance("PKCS12");try(InputStream in=Files.newInputStream(Paths.get(args[0]))){keys.load(in,"test-fixture-only".toCharArray());}
        KeyManagerFactory km=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());km.init(keys,"test-fixture-only".toCharArray());
        SSLContext context=SSLContext.getInstance("TLS");context.init(km.getKeyManagers(),null,null);Properties result=new Properties();
        int expected=args.length>2?Integer.parseInt(args[2]):1,delay=args.length>3?Integer.parseInt(args[3]):0;
        AtomicInteger requests=new AtomicInteger(),exchanges=new AtomicInteger(),failures=new AtomicInteger();
        List<SSLSocket> sockets=new ArrayList<>();List<Thread> workers=new ArrayList<>();
        try(SSLServerSocket listener=(SSLServerSocket)context.getServerSocketFactory().createServerSocket(0,5,InetAddress.getByName("127.0.0.1"))){
            listener.setSoTimeout(100);System.out.println(listener.getLocalPort());System.out.flush();long deadline=System.nanoTime()+15000000000L;
            while(exchanges.get()<expected&&System.nanoTime()<deadline){
                SSLSocket socket;try{socket=(SSLSocket)listener.accept();}catch(SocketTimeoutException wait){continue;}sockets.add(socket);
                Thread worker=new Thread(()->{boolean trusted=false;
                    try{
                        socket.setSoTimeout(5000);socket.setTcpNoDelay(true);socket.startHandshake();trusted=true;
                        List<SNIServerName> names=((ExtendedSSLSession)socket.getSession()).getRequestedServerNames();
                        result.setProperty("sni",names.isEmpty()?"":((SNIHostName)names.get(0)).getAsciiName());
                        BufferedReader reader=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.US_ASCII));
                        while(exchanges.get()<expected){
                            String line=reader.readLine();if(line==null)return;StringBuilder request=new StringBuilder(line).append('\n');
                            while((line=reader.readLine())!=null&&!line.isEmpty())request.append(line).append('\n');
                            int number=requests.incrementAndGet();result.setProperty("headers",request.toString());result.setProperty("headers."+number,request.toString());
                            String keep=number<expected?"keep-alive":"close";
                            socket.getOutputStream().write(("HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: "+keep+"\r\n\r\n").getBytes(StandardCharsets.US_ASCII));socket.getOutputStream().flush();
                            if(delay>0)Thread.sleep(delay);
                            socket.getOutputStream().write(new byte[]{79,75});socket.getOutputStream().flush();exchanges.incrementAndGet();
                            if(number>=expected)return;
                        }
                    }catch(Exception error){if(!trusted){failures.incrementAndGet();exchanges.incrementAndGet();}result.setProperty("error",error.toString());}
                    finally{try{socket.close();}catch(IOException ignored){}}
                },"fixture-http");worker.setDaemon(true);worker.start();workers.add(worker);
            }
            for(SSLSocket socket:sockets)try{socket.close();}catch(IOException ignored){}
            for(Thread worker:workers)worker.join(1000);
            result.setProperty("connections",Integer.toString(sockets.size()));result.setProperty("requests",Integer.toString(requests.get()));result.setProperty("tlsFailures",Integer.toString(failures.get()));
        }finally{try(OutputStream out=Files.newOutputStream(Paths.get(args[1]))){result.store(out,"Synthetic TLS fixture");}}
    }
}
