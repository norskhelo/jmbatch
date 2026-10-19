package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class FallbackDnsTest {
    static int checks;
    static void check(boolean condition){checks++;if(!condition)throw new AssertionError("DNS check "+checks);}
    interface Action {void run()throws Exception;}
    static void fails(Action action)throws Exception{try{action.run();throw new AssertionError("expected rejection "+checks);}catch(IOException expected){checks++;}}
    static byte[] answer(byte[] query,String ip,long ttl)throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.write(query);byte[] prefix=bytes.toByteArray();prefix[2]=(byte)0x81;prefix[3]=(byte)0x80;prefix[7]=(byte)(ip==null?0:1);
        bytes.reset();out.write(prefix);
        if(ip!=null){byte[] address=InetAddress.getByName(ip).getAddress();out.writeShort(0xc00c);out.writeShort(address.length==4?1:28);out.writeShort(1);out.writeInt((int)ttl);out.writeShort(address.length);out.write(address);}
        return bytes.toByteArray();
    }
    static byte[] query(URL url){return Base64.getUrlDecoder().decode(url.getQuery().substring(4));}
    static int type(byte[] query){return query[query.length-3]&255;}
    static byte[] reply(URL url,long ttl)throws Exception{byte[] q=query(url);return answer(q,type(q)==1?"93.184.216.34":"2606:4700::1111",ttl);}
    static byte[] alias(byte[] query,long ttl)throws Exception {
        byte[] prefix=answer(query,null,0);prefix[7]=2;
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);out.write(prefix);
        out.writeShort(0xc00c);out.writeShort(5);out.writeShort(1);out.writeInt((int)ttl);out.writeShort(14);out.writeByte(6);out.writeBytes("target");out.writeByte(4);out.writeBytes("test");out.writeByte(0);
        // alias RDATA above is 13 bytes: target(7) + test(5) + root(1).
        byte[] partial=bytes.toByteArray();partial[prefix.length+10]=0;partial[prefix.length+11]=13;
        bytes.reset();out.write(partial);out.writeByte(6);out.writeBytes("target");out.writeByte(4);out.writeBytes("test");out.writeByte(0);
        out.writeShort(1);out.writeShort(1);out.writeInt(100);out.writeShort(4);out.write(new byte[]{93,(byte)184,(byte)216,34});return bytes.toByteArray();
    }
    public static void main(String[] args)throws Exception {
        byte[] q=DnsWire.query("API.Test",1),r=answer(q,"93.184.216.34",600);
        check(DnsWire.parse(q,r).addresses.size()==1);check(DnsWire.parse(q,r).ttl==300);
        for(String ip:new String[]{"0.0.0.0","127.0.0.1","10.0.0.1","169.254.2.1","192.168.1.1","100.64.0.1","224.0.0.1","255.255.255.255"})check(DnsWire.parse(q,answer(q,ip,30)).addresses.isEmpty());
        byte[] q6=DnsWire.query("api.test",28);
        for(String ip:new String[]{"::","::1","fe80::1","fd00::1","ff02::1"})check(DnsWire.parse(q6,answer(q6,ip,30)).addresses.isEmpty());
        check(DnsWire.parse(q6,answer(q6,"2606:4700::1111",30)).addresses.size()==1);
        check(DnsWire.parse(q,r).ttl==300);check(DnsWire.parse(q,answer(q,"93.184.216.34",0)).ttl==0);
        byte[] wrong=r.clone();wrong[0]^=1;fails(()->DnsWire.parse(q,wrong));
        byte[] truncated=Arrays.copyOf(r,r.length-1);fails(()->DnsWire.parse(q,truncated));
        byte[] tc=r.clone();tc[2]|=2;fails(()->DnsWire.parse(q,tc));
        byte[] denied=r.clone();denied[3]|=5;fails(()->DnsWire.parse(q,denied));
        byte[] loop=r.clone();loop[12]=(byte)0xc0;loop[13]=12;fails(()->DnsWire.parse(q,loop));
        byte[] mismatch=r.clone();mismatch[13]='x';fails(()->DnsWire.parse(q,mismatch));
        fails(()->DnsWire.query("api.test/path?token=x",1));fails(()->DnsWire.query("a..test",1));
        check(DnsWire.parse(q,alias(q,7)).ttl==7);
        AtomicLong time=new AtomicLong(1000);AtomicInteger lookups=new AtomicInteger(),fetches=new AtomicInteger();
        FallbackDns dns=new FallbackDns(h->{lookups.incrementAndGet();return new InetAddress[]{InetAddress.getByAddress(new byte[4])};},time::get);
        check(!dns.confirmedZero("api.test",new SocketTimeoutException()));check(lookups.get()==0);
        FallbackDns healthy=new FallbackDns(h->new InetAddress[]{InetAddress.getByAddress(new byte[]{93,(byte)184,(byte)216,34})},time::get);
        check(!healthy.confirmedZero("api.test",new ConnectException("Failed to connect to api.test/93.184.216.34 from /:: (port 0)")));
        check(dns.confirmedZero("api.test",new ConnectException("generic connection failure")));
        check(dns.confirmedZero("api.test",new ConnectException("Failed to connect to api.test/[::]:443")));
        FallbackDns.Fetch fetch=(url,deadline)->{fetches.incrementAndGet();return reply(url,2);};
        FallbackDns.Result first=dns.resolve("api.test",fetch,()->{},s->{});check(first.addresses.size()==2);check(fetches.get()==2);
        check(dns.resolve("api.test",fetch,()->{},s->{})==first);check(fetches.get()==2);
        first.connected(first.addresses.get(1));check(first.routes(time.get()).get(0).equals(first.addresses.get(1)));
        first.failed(first.addresses.get(1),time.get());check(first.routes(time.get()).size()==1);
        first.failed(first.addresses.get(0),time.get());check(first.routes(time.get()).isEmpty());
        check(first.routes(time.get()+15000).size()==2);
        time.addAndGet(2001);check(dns.cached("api.test")==null);dns.resolve("api.test",fetch,()->{},s->{});check(fetches.get()==4);
        dns.discard("api.test",first);check(dns.cached("api.test")!=null);
        dns.discard("api.test",dns.cached("api.test"));check(dns.cached("api.test")==null);
        AtomicInteger second=new AtomicInteger();
        FallbackDns.Result switched=dns.resolve("other.test",(url,deadline)->{second.incrementAndGet();if(url.getHost().equals("dns.alidns.com"))return answer(query(url),null,0);return reply(url,20);},()->{},s->{});
        check(second.get()==4&&switched.provider.equals("doh.pub"));
        AtomicInteger bad=new AtomicInteger();FallbackDns.Fetch invalid=(url,deadline)->{bad.incrementAndGet();return new byte[2];};
        fails(()->dns.resolve("bad.test",invalid,()->{},s->{}));check(bad.get()==4);
        fails(()->dns.resolve("bad.test",invalid,()->{},s->{}));check(bad.get()==4);
        time.addAndGet(15001);fails(()->dns.resolve("bad.test",invalid,()->{},s->{}));check(bad.get()==8);
        fails(()->dns.resolve("cancel.test",fetch,()->{throw new IOException("CANCEL");},s->{}));check(dns.cached("cancel.test")==null);
        AtomicInteger parallelCalls=new AtomicInteger();FallbackDns parallel=new FallbackDns(h->new InetAddress[0],time::get);
        ExecutorService pool=Executors.newFixedThreadPool(16);List<Future<?>> futures=new ArrayList<>();
        try{for(int i=0;i<16;i++)futures.add(pool.submit(()->{try{parallel.resolve("parallel.test",(url,deadline)->{parallelCalls.incrementAndGet();Thread.sleep(30);return reply(url,30);},()->{},s->{});}catch(Exception e){throw new RuntimeException(e);}}));for(Future<?> future:futures)future.get(5,TimeUnit.SECONDS);}finally{pool.shutdownNow();}
        check(parallelCalls.get()==2);
        ProxySelector previous=ProxySelector.getDefault();
        try{ProxySelector.setDefault(new ProxySelector(){public List<Proxy> select(URI uri){return Collections.singletonList(new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",8080)));}public void connectFailed(URI u,SocketAddress a,IOException e){}});check(!FallbackDns.permitsDirect(new URL("https://api.test")));}
        finally{ProxySelector.setDefault(previous);}
        check(!FallbackDns.permitsDirect(new URL("http://api.test")));check(!FallbackDns.permitsDirect(new URL("https://name:password@api.test")));
        System.out.println("FallbackDnsTest: "+checks+" checks passed");
    }
}
