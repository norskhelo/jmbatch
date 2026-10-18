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
    static class Backup extends Fake {
        volatile int fallback,cancelled;boolean zero=true,fail=true;
        public InetAddress[] dns(String h)throws Exception{return zero?new InetAddress[]{InetAddress.getByName("0.0.0.0"),InetAddress.getByName("::")}:super.dns(h);}
        public String https(String h)throws Exception{if(fail)throw new ConnectException("all addresses failed");return super.https(h);}
        public boolean hasFallback(){return true;}
        public String fallback(String h)throws Exception{fallback++;return "HTTP 200（仅连接测试）";}
        public void cancel(){cancelled++;}
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
        Backup backup=new Backup();log.clear();new NetworkProbe(backup,new String[]{"test.example"},100,1000).run(false,log::add);
        check(backup.fallback==1);check(backup.cancelled==1);check(log.toString().contains("备用路径：HTTP 200"));
        backup=new Backup();backup.zero=false;new NetworkProbe(backup,new String[]{"test.example"},100,1000).run(false,s->{});check(backup.fallback==0);
        backup=new Backup();backup.fail=false;new NetworkProbe(backup,new String[]{"test.example"},100,1000).run(false,s->{});check(backup.fallback==0);
        backup=new Backup(){public String fallback(String h)throws Exception{throw new IOException("backup offline");}};log.clear();new NetworkProbe(backup,new String[]{"test.example"},100,1000).run(false,log::add);
        check(log.toString().contains("备用路径失败：IOException: backup offline"));check(backup.cancelled==1);
        backup=new Backup(){public String fallback(String h)throws Exception{fallback++;Thread.sleep(5000);return "unexpected";}};
        Backup slowBackup=backup;NetworkProbe pending=new NetworkProbe(backup,new String[]{"test.example"},100,90000);Thread waiting=new Thread(()->pending.run(false,s->{}));waiting.start();
        for(int i=0;i<100&&slowBackup.fallback==0;i++)Thread.sleep(10);pending.cancel();waiting.join(1000);check(!waiting.isAlive()&&slowBackup.cancelled>=1);
        System.out.println("Probe engine: "+checks+" checks passed");
    }
}
