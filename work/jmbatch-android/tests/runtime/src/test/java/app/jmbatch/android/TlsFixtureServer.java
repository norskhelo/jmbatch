package app.jmbatch.android;

import javax.net.ssl.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;

/** Separate JVM keeps server crypto independent of Robolectric's Android providers. */
public final class TlsFixtureServer {
    public static void main(String[] args)throws Exception{
        KeyStore keys=KeyStore.getInstance("PKCS12");try(InputStream in=Files.newInputStream(Paths.get(args[0]))){keys.load(in,"test-fixture-only".toCharArray());}
        KeyManagerFactory km=KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());km.init(keys,"test-fixture-only".toCharArray());
        SSLContext context=SSLContext.getInstance("TLS");context.init(km.getKeyManagers(),null,null);Properties result=new Properties();
        try(SSLServerSocket listener=(SSLServerSocket)context.getServerSocketFactory().createServerSocket(0,5,InetAddress.getByName("127.0.0.1"))){
            listener.setSoTimeout(10000);System.out.println(listener.getLocalPort());System.out.flush();
            try(SSLSocket socket=(SSLSocket)listener.accept()){
                socket.setSoTimeout(5000);socket.startHandshake();List<SNIServerName> names=((ExtendedSSLSession)socket.getSession()).getRequestedServerNames();
                result.setProperty("sni",names.isEmpty()?"":((SNIHostName)names.get(0)).getAsciiName());
                BufferedReader reader=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.US_ASCII));StringBuilder request=new StringBuilder();String line;
                while((line=reader.readLine())!=null&&!line.isEmpty())request.append(line).append('\n');result.setProperty("headers",request.toString());
                socket.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK".getBytes(StandardCharsets.US_ASCII));socket.getOutputStream().flush();
            }catch(Exception error){result.setProperty("error",error.toString());}
        }finally{try(OutputStream out=Files.newOutputStream(Paths.get(args[1]))){result.store(out,"Synthetic TLS fixture");}}
    }
}
