package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

public final class NetworkProbeTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("probe check "+checks);}
    static class Fake implements NetworkProbe.Operations {
        int dns,https,direct;
        public InetAddress[] dns(String h)throws Exception{dns++;return new InetAddress[]{InetAddress.getByName("203.0.113.7"),InetAddress.getByName("2001:db8::7")};}
        public String https(String h)throws Exception{https++;return "HTTP 403";}
        public String direct(String h,InetAddress a)throws Exception{direct++;return "TCP + TLS";}
    }
    public static void main(String[] args)throws Exception {
        Fake f=new Fake();List<String> log=new ArrayList<>();
        new NetworkProbe(f,NetworkProbe.HOSTS,100,3000).run(false,log::add);
        check(f.dns==5&&f.https==5&&f.direct==0);check(log.toString().contains("HTTP 403"));check(log.toString().contains("JM Batch 自身身份"));
        f=new Fake();new NetworkProbe(f,NetworkProbe.HOSTS,100,3000).run(true,s->{});check(f.direct==10);
        InetAddress[] candidates=new InetAddress[8];String[] raw={"0.0.0.0","::","127.0.0.1","10.0.0.1","203.0.113.7","203.0.113.8","2001:db8::7","2001:db8::8"};
        for(int i=0;i<raw.length;i++)candidates[i]=InetAddress.getByName(raw[i]);
        List<InetAddress> sampled=NetworkProbe.sample(candidates);check(sampled.size()==2);check(sampled.get(0).getHostAddress().equals("203.0.113.7"));
        log.clear();new NetworkProbe(new Fake(){public InetAddress[] dns(String h)throws Exception{return new InetAddress[]{InetAddress.getByName("0.0.0.0")};}public String https(String h)throws Exception{throw new ConnectException("from /[::]:0 EACCES");}},new String[]{"test.example"},100,1000).run(true,log::add);
        check(log.toString().contains("DNS 实际返回全零地址"));check(log.toString().contains("观察到 EACCES/EPERM"));
        log.clear();new NetworkProbe(new Fake(){public String https(String h)throws Exception{throw new ConnectException("from /[::]:0 ECONNREFUSED");}},new String[]{"test.example"},100,1000).run(false,log::add);
        check(!log.toString().contains("DNS 实际返回全零地址"));check(!log.toString().contains("观察到 EACCES/EPERM"));
        f=new Fake();NetworkProbe stopped=new NetworkProbe(f,NetworkProbe.HOSTS,100,1000);stopped.cancel();log.clear();stopped.run(true,log::add);check(f.dns==0&&f.https==0&&f.direct==0);check(log.toString().contains("已停止"));
        AtomicInteger entered=new AtomicInteger();NetworkProbe slow=new NetworkProbe(new Fake(){public InetAddress[] dns(String h)throws Exception{entered.incrementAndGet();Thread.sleep(5000);return super.dns(h);}},NetworkProbe.HOSTS,30,70);
        long begin=System.nanoTime();slow.run(false,s->{});check((System.nanoTime()-begin)/1000000<1000);check(entered.get()<=3);
        NetworkProbe cancel=new NetworkProbe(new Fake(){public InetAddress[] dns(String h)throws Exception{Thread.sleep(5000);return super.dns(h);}},NetworkProbe.HOSTS,5000,90000);
        Thread worker=new Thread(()->cancel.run(false,s->{}));worker.start();Thread.sleep(50);cancel.cancel();worker.join(1000);check(!worker.isAlive());
        String detail=NetworkProbe.error(new IOException("outer",new ConnectException("ECONNREFUSED\nfrom /::")));check(detail.contains("IOException")&&detail.contains("ConnectException")&&!detail.contains("\n"));
        System.out.println("Probe engine: "+checks+" checks passed");
    }
}
