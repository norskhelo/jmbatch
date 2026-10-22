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
        private static final class Health {InetAddress preferred;final Map<InetAddress,Long> cooldown=new HashMap<>();}
        private Health health=new Health();
        Result(List<InetAddress> addresses,String provider,long expires){this.addresses=Collections.unmodifiableList(addresses);this.provider=provider;this.expires=expires;}
        List<InetAddress> routes(long now){synchronized(health){
            List<InetAddress> ready=new ArrayList<>();
            health.cooldown.values().removeIf(until->until<=now);
            for(InetAddress address:addresses)if(health.cooldown.getOrDefault(address,0L)<=now)ready.add(address);
            if(health.preferred!=null&&ready.remove(health.preferred))ready.add(0,health.preferred);return ready;
        }}
        void connected(InetAddress address){synchronized(health){health.preferred=address;health.cooldown.remove(address);}}
        void failed(InetAddress address,long now){synchronized(health){health.cooldown.put(address,now+15000);if(address.equals(health.preferred))health.preferred=null;}}
        // In-flight responses from the old TTL generation update the same health.
        void inherit(Result previous){if(previous!=null)health=previous.health;}
    }
    private static final class Entry {final ReentrantLock lock=new ReentrantLock();volatile Result result;volatile long failedUntil,zeroUntil;}
    private final Map<String,Entry> entries=new LinkedHashMap<>();
    final Lookup lookup;final LongSupplier clock;
    FallbackDns(){this(InetAddress::getAllByName,()->System.nanoTime()/1000000);}
    FallbackDns(Lookup lookup,LongSupplier clock){this.lookup=lookup;this.clock=clock;}
    private synchronized Entry entry(String host){
        Entry entry=entries.get(host);if(entry==null){if(entries.size()>=32)entries.remove(entries.keySet().iterator().next());entry=new Entry();entries.put(host,entry);}return entry;
    }
    synchronized Result cached(String host){Entry entry=entries.get(host.toLowerCase(Locale.ROOT));Result result=entry==null?null:entry.result;return result!=null&&clock.getAsLong()<result.expires?result:null;}
    synchronized void discard(String host,Result expected){Entry entry=entries.get(host.toLowerCase(Locale.ROOT));if(entry!=null&&entry.result==expected)entry.result=null;}
    synchronized boolean knownZero(String host){Entry entry=entries.get(host.toLowerCase(Locale.ROOT));return entry!=null&&clock.getAsLong()<entry.zeroUntil;}
    synchronized void systemRecovered(String host){Entry entry=entries.get(host.toLowerCase(Locale.ROOT));if(entry!=null){entry.zeroUntil=0;entry.result=null;entry.failedUntil=0;}}
    boolean confirmedZero(String host,Exception failure)throws IOException {
        if(!Arrays.asList("address","connect","refused","unreachable","dns").contains(NetworkRoutes.kind(failure)))return false;
        for(InetAddress address:lookup.get(host))if(address.isAnyLocalAddress()){entry(host.toLowerCase(Locale.ROOT)).zeroUntil=clock.getAsLong()+60000;return true;}
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
                    List<InetAddress> addresses=new ArrayList<>();for(int i=0;i<Math.max(v4.size(),v6.size());i++){if(i<v4.size())addresses.add(v4.get(i));if(i<v6.size())addresses.add(v6.get(i));}
                    Result result=new Result(addresses,new URL(provider).getHost(),expires);
                    result.inherit(entry.result);
                    entry.result=result;entry.failedUntil=0;notice.show("备用 DNS 已取得地址："+host+"（"+result.provider+"）");return result;
                }
                if(clock.getAsLong()>=deadline)break;
            }
            entry.failedUntil=clock.getAsLong()+15000;notice.show("备用 DNS 解析失败："+host);throw new Failure();
        }finally{entry.lock.unlock();}
    }
}
