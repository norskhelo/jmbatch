import app.jmbatch.android.NetworkRoutes;
import java.net.*;
import java.io.*;
import java.util.*;
import javax.net.ssl.SSLHandshakeException;

public class NetworkTest {
    private static int checks;
    private static void check(boolean ok){checks++;if(!ok)throw new AssertionError("Network check "+checks);}
    public static void main(String[] args)throws Exception {
        List<String> hosts=Arrays.asList("a.example","b.example"),calls=new ArrayList<>(),notices=new ArrayList<>();
        String value=NetworkRoutes.run(hosts,5,"接口",host->{calls.add(host);if(host.equals("a.example"))throw new ConnectException("Failed to connect to a.example/[::]:443");return "ok";},()->{},notices::add);
        check(value.equals("ok"));check(calls.equals(hosts));check(notices.get(0).contains("b.example"));
        calls.clear();
        try {NetworkRoutes.run(hosts,5,"接口",host->{calls.add(host);if(host.equals("a.example"))throw new ConnectException("a.example/[::]:443 cookie=SECRET");throw new UnknownHostException("https://b.example?token=PRIVATE");},()->{},m->{});throw new AssertionError();}
        catch(NetworkRoutes.Exhausted error){String text=error.getMessage();check(text.contains("a.example")&&text.contains("b.example"));check(text.contains("未指定地址")&&text.contains("DNS 解析失败"));check(!text.contains("SECRET")&&!text.contains("PRIVATE")&&!text.contains("https://"));check(text.contains("2 次请求"));}
        check(calls.equals(hosts));calls.clear();
        try{NetworkRoutes.run(hosts,2,"接口",host->{calls.add(host);throw new SocketTimeoutException();},()->{},m->{});throw new AssertionError();}
        catch(NetworkRoutes.Exhausted error){check(calls.equals(Arrays.asList("a.example","b.example","a.example","b.example")));}
        calls.clear();
        try{NetworkRoutes.run(hosts,0,"接口",host->{calls.add(host);throw new ConnectException();},()->{},m->{});throw new AssertionError();}
        catch(NetworkRoutes.Exhausted error){check(calls.equals(hosts));}
        for(int code:new int[]{401,403,404,429}){
            calls.clear();try{NetworkRoutes.run(hosts,5,"接口",host->{calls.add(host);throw new NetworkRoutes.HttpFailure(code);},()->{},m->{});throw new AssertionError();}
            catch(NetworkRoutes.HttpFailure error){check(error.code==code);check(calls.size()==1);}
        }
        check(NetworkRoutes.run(hosts,0,"接口",host->{if(host.equals("a.example"))throw new NetworkRoutes.HttpFailure(503);return 7;},()->{},m->{}).equals(7));
        check(NetworkRoutes.run(hosts,0,"接口",host->{if(host.equals("a.example"))throw new NetworkRoutes.BadResponse();return 7;},()->{},m->{}).equals(7));
        calls.clear();try{NetworkRoutes.run(hosts,5,"接口",host->{calls.add(host);throw new SSLHandshakeException("PRIVATE");},()->{},m->{});throw new AssertionError();}
        catch(NetworkRoutes.Exhausted error){check(calls.size()==2);check(error.getMessage().contains("证书校验失败"));check(!error.getMessage().contains("PRIVATE"));}
        calls.clear();try{NetworkRoutes.run(hosts,5,"图片",host->{calls.add(host);throw new FileNotFoundException("disk");},()->{},m->{});throw new AssertionError();}
        catch(FileNotFoundException error){check(calls.size()==1);}
        calls.clear();try{NetworkRoutes.run(hosts,5,"接口",host->{calls.add(host);return 1;},()->{throw new InterruptedException("cancel");},m->{});throw new AssertionError();}
        catch(InterruptedException error){check(calls.isEmpty());}
        check(NetworkRoutes.merge(Arrays.asList("A.EXAMPLE","https://bad.example/","a.example","bad..example"),Arrays.asList("b.example")).equals(hosts));
        List<String> longList=new ArrayList<>();for(int i=0;i<100;i++)longList.add("a"+i+".example");check(NetworkRoutes.merge(longList,Arrays.asList("backup.example")).contains("backup.example"));
        System.out.println("Network failover and diagnostics: "+checks+" checks passed");
    }
}
