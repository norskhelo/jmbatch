package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/** Small, bounded RFC 1035 A/AAAA codec for authenticated RFC 8484 responses. */
final class DnsWire {
    static final class Answer {
        final List<InetAddress> addresses; final long ttl;
        Answer(List<InetAddress> addresses,long ttl){this.addresses=Collections.unmodifiableList(addresses);this.ttl=ttl;}
    }
    static String host(String host)throws IOException {
        String name=host.toLowerCase(Locale.ROOT);
        if(name.length()>253||!name.matches("[a-z0-9.-]+")||!name.contains("."))throw new IOException("无效 DNS 域名");
        for(String label:name.split("\\.",-1))if(label.isEmpty()||label.length()>63||label.startsWith("-")||label.endsWith("-"))throw new IOException("无效 DNS 域名");
        return name;
    }
    static byte[] query(String host,int type)throws IOException {
        if(type!=1&&type!=28)throw new IOException("无效 DNS 类型");
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeShort(ThreadLocalRandom.current().nextInt(65536));out.writeShort(0x100);out.writeShort(1);
        out.writeShort(0);out.writeShort(0);out.writeShort(0);
        for(String label:host(host).split("\\.")){byte[] value=label.getBytes(StandardCharsets.US_ASCII);out.writeByte(value.length);out.write(value);}
        out.writeByte(0);out.writeShort(type);out.writeShort(1);return bytes.toByteArray();
    }
    static final class Reader {
        final byte[] bytes; int pos;
        Reader(byte[] bytes){this.bytes=bytes;}
        int u16()throws IOException{if(pos+2>bytes.length)throw new IOException("DNS 响应截断");return ((bytes[pos++]&255)<<8)|(bytes[pos++]&255);}
        long u32()throws IOException{return ((long)u16()<<16)|u16();}
        String name()throws IOException {
            StringBuilder name=new StringBuilder();int p=pos,end=-1;Set<Integer> seen=new HashSet<>();
            for(int hops=0;hops<128;hops++){
                if(p>=bytes.length||!seen.add(p))throw new IOException("DNS 名称指针无效");
                int length=bytes[p++]&255;
                if(length==0){pos=end<0?p:end;return name.toString().toLowerCase(Locale.ROOT);}
                if((length&192)==192){if(p>=bytes.length)throw new IOException("DNS 响应截断");if(end<0)end=p+1;p=((length&63)<<8)|(bytes[p]&255);continue;}
                if(length>63||p+length>bytes.length||name.length()+length+1>254)throw new IOException("DNS 名称无效");
                if(name.length()>0)name.append('.');name.append(new String(bytes,p,length,StandardCharsets.US_ASCII));p+=length;
            }
            throw new IOException("DNS 名称过长");
        }
    }
    static final class Record {String name,alias;int type;long ttl;InetAddress address;}
    static Answer parse(byte[] query,byte[] response)throws IOException {
        if(response.length<12||response.length>65536)throw new IOException("DNS 响应长度无效");
        Reader q=new Reader(query);int id=q.u16();q.pos=12;String expected=q.name();int type=q.u16();
        Reader r=new Reader(response);if(r.u16()!=id)throw new IOException("DNS 响应不匹配");
        int flags=r.u16();if((flags&0x8000)==0||(flags&0x7800)!=0||(flags&0x200)!=0||(flags&15)!=0)throw new IOException("DNS 响应失败或不完整");
        int questions=r.u16(),answers=r.u16();r.u16();r.u16();
        if(questions!=1||answers>64||!r.name().equals(expected)||r.u16()!=type||r.u16()!=1)throw new IOException("DNS 问题不匹配");
        List<Record> records=new ArrayList<>();
        for(int i=0;i<answers;i++){
            Record rec=new Record();rec.name=r.name();rec.type=r.u16();int cls=r.u16();rec.ttl=r.u32();int size=r.u16(),end=r.pos+size;
            if(end>response.length)throw new IOException("DNS 响应截断");
            if(cls==1){
                if(rec.type==5){rec.alias=r.name();if(r.pos!=end)throw new IOException("DNS 别名无效");}
                else if((rec.type==1&&size==4)||(rec.type==28&&size==16))rec.address=InetAddress.getByAddress(Arrays.copyOfRange(response,r.pos,end));
                records.add(rec);
            }
            r.pos=end;
        }
        String current=expected;Set<String> seen=new HashSet<>();long ttl=300;
        for(int hop=0;hop<9&&seen.add(current);hop++){
            List<InetAddress> addresses=new ArrayList<>();Record alias=null;
            for(Record rec:records)if(rec.name.equals(current)){
                if(rec.type==5){if(alias!=null&&!alias.alias.equals(rec.alias))throw new IOException("DNS 别名冲突");alias=rec;}
                if(rec.type==type&&rec.address!=null&&publicAddress(rec.address)){if(!addresses.contains(rec.address))addresses.add(rec.address);ttl=Math.min(ttl,rec.ttl);}
            }
            if(alias!=null&&!addresses.isEmpty())throw new IOException("DNS 地址与别名冲突");
            if(!addresses.isEmpty())return new Answer(new ArrayList<>(addresses.subList(0,Math.min(4,addresses.size()))),ttl);
            if(alias==null)return new Answer(new ArrayList<>(),0);
            ttl=Math.min(ttl,alias.ttl);current=alias.alias;
        }
        throw new IOException("DNS 别名循环或过长");
    }
    static boolean publicAddress(InetAddress address){
        if(address.isAnyLocalAddress()||address.isLoopbackAddress()||address.isLinkLocalAddress()||address.isSiteLocalAddress()||address.isMulticastAddress())return false;
        byte[] b=address.getAddress();int a=b[0]&255;
        if(b.length==16)return (a&0xfe)!=0xfc;
        int second=b[1]&255;
        return a!=0&&a<224&&!(a==100&&second>=64&&second<=127)&&!(a==192&&second==0)&&!(a==198&&(second==18||second==19));
    }
    private DnsWire(){}
}
