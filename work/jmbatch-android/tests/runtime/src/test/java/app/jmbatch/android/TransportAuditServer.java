package app.jmbatch.android;

import javax.net.ssl.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Loopback-only synthetic transport audit server, with fixed bytes and no user data. */
public final class TransportAuditServer {
    public static void main(String[] args)throws Exception {
        KeyStore keys=KeyStore.getInstance("PKCS12");
        try(InputStream input=Files.newInputStream(Paths.get(args[0]))){keys.load(input,"test-fixture-only".toCharArray());}
        KeyManagerFactory km=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
        km.init(keys,"test-fixture-only".toCharArray());
        SSLContext context=SSLContext.getInstance("TLS");context.init(km.getKeyManagers(),null,null);
        int expected=Integer.parseInt(args[2]),bodyDelay=Integer.parseInt(args[3]);
        Properties result=new Properties();
        AtomicInteger accepted=new AtomicInteger(),requests=new AtomicInteger(),complete=new AtomicInteger(),failures=new AtomicInteger();
        List<SSLSocket> sockets=new CopyOnWriteArrayList<>();
        List<Thread> workers=new CopyOnWriteArrayList<>();
        byte[] body=new byte[65536];Arrays.fill(body,(byte)71);
        try(SSLServerSocket listener=(SSLServerSocket)context.getServerSocketFactory().createServerSocket(0,32,InetAddress.getByName("127.0.0.1"))){
            listener.setSoTimeout(100);System.out.println(listener.getLocalPort());System.out.flush();
            long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(45);
            while(complete.get()<expected&&System.nanoTime()<deadline){
                SSLSocket socket;try{socket=(SSLSocket)listener.accept();}catch(SocketTimeoutException waiting){continue;}
                sockets.add(socket);int connection=accepted.incrementAndGet();
                Thread worker=new Thread(()->{
                    try{
                        socket.setSoTimeout(15000);socket.setTcpNoDelay(true);
                        socket.setHandshakeApplicationProtocolSelector((s,offers)->{
                            result.setProperty("alpn-offered."+connection,String.join(",",offers));
                            return offers.contains("http/1.1")?"http/1.1":"";
                        });
                        socket.startHandshake();
                        List<SNIServerName> names=((ExtendedSSLSession)socket.getSession()).getRequestedServerNames();
                        result.setProperty("sni."+connection,names.isEmpty()?"":((SNIHostName)names.get(0)).getAsciiName());
                        result.setProperty("tls."+connection,socket.getSession().getProtocol());
                        BufferedReader reader=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.US_ASCII));
                        while(complete.get()<expected){
                            String line=reader.readLine();if(line==null)return;
                            result.setProperty("request-line",line);String host="";
                            while((line=reader.readLine())!=null&&!line.isEmpty())if(line.toLowerCase(Locale.ROOT).startsWith("host:"))host=line.substring(5).trim();
                            result.setProperty("host",host);requests.incrementAndGet();
                            OutputStream out=socket.getOutputStream();
                            if(bodyDelay<0)Thread.sleep(-bodyDelay); // Header stall fixture.
                            out.write(("HTTP/1.1 200 OK\r\nContent-Length: "+body.length+"\r\nConnection: keep-alive\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.flush();
                            if(bodyDelay>0)Thread.sleep(bodyDelay);
                            out.write(body);out.flush();complete.incrementAndGet();
                        }
                    }catch(Exception error){if(complete.get()<expected){failures.incrementAndGet();result.setProperty("error",error.toString());}}
                    finally{try{socket.close();}catch(IOException ignored){}}
                },"transport-audit");worker.setDaemon(true);worker.start();workers.add(worker);
            }
            for(SSLSocket socket:sockets)try{socket.close();}catch(IOException ignored){}
            for(Thread worker:workers)worker.join(1000);
            result.setProperty("connections",String.valueOf(accepted.get()));result.setProperty("requests",String.valueOf(requests.get()));
            result.setProperty("completed",String.valueOf(complete.get()));result.setProperty("failures",String.valueOf(failures.get()));
        }finally{try(OutputStream output=Files.newOutputStream(Paths.get(args[1]))){result.store(output,"Loopback diagnostic");}}
    }
}
