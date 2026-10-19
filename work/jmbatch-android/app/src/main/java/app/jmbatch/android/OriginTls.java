package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.util.*;
import javax.net.ssl.*;

/** Per-connection IP routing with the original HTTPS identity and system trust. */
final class OriginTls extends SSLSocketFactory {
    private final SSLSocketFactory delegate;private final String host;private final int timeout;
    OriginTls(SSLSocketFactory delegate,String host,int timeout){this.delegate=delegate;this.host=host;this.timeout=timeout;}
    static void configure(URL original,HttpsURLConnection connection,int timeout){
        new Session().configure(original,connection,timeout);
    }
    /** Stable identities let Android pool connections, isolated by origin and trust. */
    static final class Session {
        private final Map<String,Policy> policies=new LinkedHashMap<>();
        HttpsURLConnection open(URL original,InetAddress address,int timeout)throws IOException{
            String ip=address.getHostAddress();if(ip.contains(":"))ip="["+ip+"]";
            HttpsURLConnection connection=(HttpsURLConnection)new URL("https",ip,original.getPort(),original.getFile()).openConnection();
            configure(original,connection,timeout);return connection;
        }
        synchronized void configure(URL original,HttpsURLConnection connection,int timeout){
            String host=original.getHost(),key=host.toLowerCase(Locale.ROOT)+":"+(original.getPort()==-1?original.getDefaultPort():original.getPort())+":"+timeout;
            SSLSocketFactory base=connection.getSSLSocketFactory();HostnameVerifier verifier=connection.getHostnameVerifier();
            Policy policy=policies.get(key);
            if(policy==null||policy.base!=base||policy.baseVerifier!=verifier){
                if(policies.size()>=32)policies.remove(policies.keySet().iterator().next());
                policy=new Policy(base,verifier,host,timeout);policies.put(key,policy);
            }
            connection.setSSLSocketFactory(policy.sockets);connection.setHostnameVerifier(policy.verifier);
            connection.setRequestProperty("Host",host+(original.getPort()!=-1&&original.getPort()!=443?":"+original.getPort():""));
        }
    }
    private static final class Policy {
        final SSLSocketFactory base,sockets;final HostnameVerifier baseVerifier,verifier;
        Policy(SSLSocketFactory base,HostnameVerifier verifier,String host,int timeout){
            this.base=base;baseVerifier=verifier;sockets=new OriginTls(base,host,timeout);
            this.verifier=(ignored,session)->verifier.verify(host,session);
        }
    }
    @Override public Socket createSocket(Socket plain,String ignored,int port,boolean close)throws IOException {
        SSLSocket socket=(SSLSocket)delegate.createSocket(plain,host,port,close);
        try{
            socket.setSoTimeout(timeout);SSLParameters parameters=socket.getSSLParameters();
            parameters.setServerNames(Collections.singletonList(new SNIHostName(host)));
            parameters.setEndpointIdentificationAlgorithm("HTTPS");socket.setSSLParameters(parameters);
            // Complete authentication before the platform configures extensions for
            // the IP URL. The request's Host and cookie scope remain the origin.
            socket.startHandshake();return socket;
        }catch(IOException|RuntimeException error){try{socket.close();}catch(IOException ignoredClose){}throw error;}
    }
    @Override public String[] getDefaultCipherSuites(){return delegate.getDefaultCipherSuites();}
    @Override public String[] getSupportedCipherSuites(){return delegate.getSupportedCipherSuites();}
    // HttpsURLConnection uses the layered overload; fail closed on unexpected paths.
    @Override public Socket createSocket(String h,int p)throws IOException{throw new IOException("需要已连接的 TLS 套接字");}
    @Override public Socket createSocket(String h,int p,InetAddress l,int lp)throws IOException{throw new IOException("需要已连接的 TLS 套接字");}
    @Override public Socket createSocket(InetAddress a,int p)throws IOException{throw new IOException("需要已连接的 TLS 套接字");}
    @Override public Socket createSocket(InetAddress a,int p,InetAddress l,int lp)throws IOException{throw new IOException("需要已连接的 TLS 套接字");}
}
