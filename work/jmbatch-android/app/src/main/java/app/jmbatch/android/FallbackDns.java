package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.TimeUnit;
import java.util.function.LongSupplier;

/** Task-local fallback, only activated after a confirmed system wildcard answer. */
final class FallbackDns {
    interface Lookup {InetAddress[] get(String host)throws IOException;}
    interface Fetch {byte[] get(URL url,long deadline)throws Exception;}
    static final String[] PROVIDERS={"https://dns.alidns.com/dns-query","https://doh.pub/dns-query"};
    static final class Failure extends UnknownHostException {Failure(){super("系统 DNS 返回全零地址，备用 DNS 也未取得可用地址");}}
    static final class Result {
        final List<InetAddress> addresses;final String provider;final long expires;
        private InetAddress preferred;private final Map<InetAddress,Long> cooldown=new HashMap<>();
        Result(List<InetAddress> addresses,String provider,long expires){this.addresses=Collections.unmodifiableList(addresses);this.provider=provider;this.expires=expires;}
        synchronized List<InetAddress> routes(long now){
            List<InetAddress> ready=new ArrayList<>();
            for(InetAddress address:addresses)if(cooldown.getOrDefault(address,0L)<=now)ready.add(address);
            if(preferred!=null&&ready.remove(preferred))ready.add(0,preferred);return ready;
        }
        synchronized void connected(InetAddress address){preferred=address;cooldown.remove(address);}
        synchronized void failed(InetAddress address,long now){cooldown.put(address,now+15000);if(address.equals(preferred))preferred=null;}
    }
    private static final class Entry {final ReentrantLock lock=new ReentrantLock();volatile Result result;volatile long failedUntil;}
    private final Map<String,Entry> entries=new LinkedHashMap<>();
    final Lookup lookup;final LongSupplier clock;
    FallbackDns(){this(InetAddress::getAllByName,()->System.nanoTime()/1000000);}
    FallbackDns(Lookup lookup,LongSupplier clock){this.lookup=lookup;this.clock=clock;}
    private synchronized Entry entry(String host){
        Entry entry=entries.get(host);if(entry==null){if(entries.size()>=32)entries.remove(entries.keySet().iterator().next());entry=new Entry();entries.put(host,entry);}return entry;
    }
    synchronized Result cached(String host){Entry entry=entries.get(host.toLowerCase(Locale.ROOT));Result result=entry==null?null:entry.result;return result!=null&&clock.getAsLong()<result.expires?result:null;}
    synchronized void discard(String host,Result expected){Entry entry=entries.get(host.toLowerCase(Locale.ROOT));if(entry!=null&&entry.result==expected)entry.result=null;}
    boolean confirmedZero(String host,Exception failure)throws IOException {
        if(!Arrays.asList("address","connect","refused","unreachable","dns").contains(NetworkRoutes.kind(failure)))return false;
        for(InetAddress address:lookup.get(host))if(address.isAnyLocalAddress())return true;
        return false;
    }
    static boolean permitsDirect(URL url){
        if(!url.getProtocol().equals("https")||url.getUserInfo()!=null)return false;
        try{DnsWire.host(url.getHost());ProxySelector selector=ProxySelector.getDefault();if(selector!=null){List<Proxy> proxies=selector.select(url.toURI());if(proxies!=null)for(Proxy proxy:proxies)if(proxy!=null&&proxy.type()!=Proxy.Type.DIRECT)return false;}return true;}catch(Exception e){return false;}
    }
    Result resolve(String host,Fetch fetch,NetworkRoutes.Check check,NetworkRoutes.Notice notice)throws Exception {
        host=DnsWire.host(host);Entry entry=entry(host);
        while(!entry.lock.tryLock(100,TimeUnit.MILLISECONDS))check.run();
        try{
            check.run();Result cached=cached(host);if(cached!=null)return cached;
            if(clock.getAsLong()<entry.failedUntil)throw new Failure();
            long deadline=clock.getAsLong()+14000;
            notice.show("系统 DNS 返回全零地址，尝试备用 DNS："+host);
            for(String provider:PROVIDERS){
                List<InetAddress> v4=new ArrayList<>(),v6=new ArrayList<>();long expires=Long.MAX_VALUE;
                for(int type:new int[]{1,28}){
                    check.run();if(clock.getAsLong()>=deadline)break;
                    try{
                        byte[] query=DnsWire.query(host,type);String encoded=Base64.getUrlEncoder().withoutPadding().encodeToString(query);
                        DnsWire.Answer answer=DnsWire.parse(query,fetch.get(new URL(provider+"?dns="+encoded),deadline));
                        if(!answer.addresses.isEmpty()){(type==1?v4:v6).addAll(answer.addresses);expires=Math.min(expires,clock.getAsLong()+answer.ttl*1000);}
                    }catch(Exception error){check.run();}
                }
                if(!v4.isEmpty()||!v6.isEmpty()){
                    List<InetAddress> addresses=new ArrayList<>();for(int i=0;i<2;i++){if(i<v4.size())addresses.add(v4.get(i));if(i<v6.size())addresses.add(v6.get(i));}
                    Result result=new Result(addresses,new URL(provider).getHost(),expires);
                    entry.result=result;entry.failedUntil=0;notice.show("备用 DNS 已取得地址："+host+"（"+result.provider+"）");return result;
                }
                if(clock.getAsLong()>=deadline)break;
            }
            entry.failedUntil=clock.getAsLong()+15000;notice.show("备用 DNS 解析失败："+host);throw new Failure();
        }finally{entry.lock.unlock();}
    }
}
