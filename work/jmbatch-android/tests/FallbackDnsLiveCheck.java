package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Opt-in public DNS smoke check; never included in the offline build test run. */
public final class FallbackDnsLiveCheck {
    public static void main(String[] args)throws Exception{
        if(args.length!=1)throw new IllegalArgumentException("Pass the local report file explicitly");
        StringBuilder log=new StringBuilder("Public DoH check from Windows, not the affected phone. "+java.time.Instant.now()+"\n");int passed=0;
        for(String provider:FallbackDns.PROVIDERS)for(String host:new String[]{"www.mi.com","www.cdnhjk.net"})for(int type:new int[]{1,28}){
            byte[] query=DnsWire.query(host,type);URL url=new URL(provider+"?dns="+Base64.getUrlEncoder().withoutPadding().encodeToString(query));
            HttpURLConnection connection=(HttpURLConnection)url.openConnection();connection.setConnectTimeout(5000);connection.setReadTimeout(5000);connection.setInstanceFollowRedirects(false);connection.setRequestProperty("Accept","application/dns-message");
            try{
                if(connection.getResponseCode()!=200)throw new IOException("HTTP "+connection.getResponseCode());
                ByteArrayOutputStream data=new ByteArrayOutputStream();try(InputStream in=connection.getInputStream()){byte[] buffer=new byte[2048];int n;while((n=in.read(buffer))!=-1){if(data.size()+n>65536)throw new IOException("too large");data.write(buffer,0,n);}}
                DnsWire.Answer answer=DnsWire.parse(query,data.toByteArray());if(answer.addresses.isEmpty())throw new IOException("no public answers");
                log.append("PASS ").append(provider).append(' ').append(host).append(' ').append(type).append(" ttl=").append(answer.ttl).append(' ').append(answer.addresses).append('\n');passed++;
            }catch(Exception error){log.append("FAIL ").append(provider).append(' ').append(host).append(' ').append(type).append(' ').append(error).append('\n');}
            finally{connection.disconnect();}
        }
        Path target=Paths.get(args[0]);Files.createDirectories(target.toAbsolutePath().getParent());Files.write(target,log.toString().getBytes(StandardCharsets.UTF_8));System.out.print(log);System.out.println("Passed "+passed+"/8");if(passed!=8)System.exit(1);
    }
}
