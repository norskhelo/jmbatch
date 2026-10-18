package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.util.*;
import javax.net.ssl.SSLHandshakeException;

public final class NetworkCauseTest {
    static int checks;
    static void check(boolean ok){checks++;if(!ok)throw new AssertionError("cause check "+checks);}
    static void kind(String expected,Exception error){check(expected.equals(NetworkRoutes.kind(error)));}
    public static void main(String[] args)throws Exception {
        for(String local:new String[]{"[::]","0:0:0:0:0:0:0:0","0.0.0.0","::"}) {
            String prefix="failed to connect to example.org/203.0.113.1 (port 443) from /"+local+" (port 0)";
            kind("connect",new ConnectException(prefix));
            kind("permission",new ConnectException(prefix+": connect failed: EACCES (Permission denied)"));
            kind("refused",new ConnectException(prefix+": connect failed: ECONNREFUSED (Connection refused)"));
            kind("unreachable",new ConnectException(prefix+": ENETUNREACH"));
            kind("timeout",new SocketTimeoutException(prefix+" after 8000ms"));
        }
        for(String remote:new String[]{"[::]:443","0:0:0:0:0:0:0:0 (port 443)","0.0.0.0:443",":: (port 443)"})
            kind("address",new ConnectException("Failed to connect to example.org/"+remote));
        kind("connect",new ConnectException("Failed to connect to example.org/[::1]:443"));
        kind("connect",new ConnectException("Failed to connect to example.org/10.0.0.0:443"));
        kind("permission",new ConnectException("wrapper"){ {initCause(new IOException("EPERM (Operation not permitted)"));} });
        kind("permission",new UnknownHostException("getaddrinfo failed: EACCES"));
        kind("tls",new SSLHandshakeException("failed from /[::]: Permission denied"));
        kind("dns",new UnknownHostException("not found"));
        kind("other",new IOException("disk"));
        IOException wrapped=new IOException("cookie=SECRET",new NetworkRoutes.HttpFailure(403));
        check(!NetworkRoutes.reason(wrapped).contains("SECRET"));
        try {NetworkRoutes.run(Arrays.asList("a.example","b.example"),5,"API",h->{throw wrapped;},()->{},m->{});throw new AssertionError();}
        catch(NetworkRoutes.HttpFailure e){check(e.code==403);check(!e.getMessage().contains("SECRET"));}
        List<String> calls=new ArrayList<>();
        try {
            NetworkRoutes.run(Arrays.asList("a.example","b.example"),5,"API",h->{calls.add(h);throw new ConnectException("from /[::]:0 EACCES cookie=SECRET");},()->{},m->{});
            throw new AssertionError();
        } catch(NetworkRoutes.Exhausted e) {
            check(calls.size()==2);check(e.getMessage().contains("系统拒绝联网"));
            check(!e.getMessage().contains("未指定地址"));check(!e.getMessage().contains("SECRET"));
        }
        System.out.println("Network cause classification: "+checks+" checks passed");
    }
}
