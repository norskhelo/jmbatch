import app.jmbatch.android.*;
import java.net.*;
import java.io.*;
import java.util.*;

public class ImageRoutesTest {
    static int checks;
    static void check(boolean value) { checks++; if (!value) throw new AssertionError("route check " + checks); }
    public static void main(String[] args) throws Exception {
        long[] now={1000}; List<String> hosts=Arrays.asList("a.example","b.example","c.example");
        ImageRoutes routes=new ImageRoutes(hosts,()->now[0]);
        try(ImageRoutes.Plan p=routes.plan(0)){check(p.hosts.equals(hosts));}
        routes.failure("a.example",new ConnectException());routes.success("b.example",100000,100);
        for(int i=0;i<16;i++)try(ImageRoutes.Plan p=routes.plan(0)){check(!p.hosts.contains("a.example"));}
        now[0]+=16000;
        boolean includes=false;
        for(int i=0;i<8;i++)try(ImageRoutes.Plan p=routes.plan(0)){includes|=p.hosts.contains("a.example");}
        check(includes);
        routes.success("a.example",100000,1000);routes.success("b.example",100000,10);
        try(ImageRoutes.Plan p=routes.plan(0)){check(p.hosts.get(0).equals("b.example"));}
        for(int code:new int[]{401,403,404,429}) {
            ImageRoutes r=new ImageRoutes(hosts,()->now[0]);r.failure("a.example",new NetworkRoutes.HttpFailure(code));
            List<String> calls=new ArrayList<>();
            try(ImageRoutes.Plan p=r.plan(0)) {
                try {NetworkRoutes.run(p.hosts,2,"image",h->{calls.add(h);throw new NetworkRoutes.HttpFailure(code);},()->{},m->{});throw new AssertionError();}
                catch(NetworkRoutes.HttpFailure error){check(error.code==code&&calls.size()==1);}
            }
            try(ImageRoutes.Plan p=r.plan(0)){check(p.hosts.get(0).equals("a.example"));}
        }
        ImageRoutes r=new ImageRoutes(hosts,()->now[0]);r.failure("a.example",new FileNotFoundException("disk"));
        try(ImageRoutes.Plan p=r.plan(0)){check(p.hosts.get(0).equals("a.example"));}
        for(String h:hosts)r.failure(h,new SocketTimeoutException());
        try(ImageRoutes.Plan p=r.plan(0)){check(p.hosts.size()==1);}
        now[0]+=200000;
        try(ImageRoutes.Plan p=r.plan(0)){check(p.hosts.size()==3);}
        // Successful but slow first CDN is compared on a normal request. Only one probe in flight.
        ImageRoutes slow=new ImageRoutes(hosts,()->now[0]);slow.success("a.example",100000,1000);
        for(int i=0;i<7;i++)try(ImageRoutes.Plan p=slow.plan(0)){check(p.hosts.get(0).equals("a.example"));}
        try(ImageRoutes.Plan probe=slow.plan(0)) {
            check(probe.hosts.get(0).equals("b.example"));
            for(int i=0;i<16;i++)try(ImageRoutes.Plan p=slow.plan(0)){check(p.hosts.get(0).equals("a.example"));}
            slow.success("b.example",100000,10);
        }
        for(int i=0;i<16;i++)try(ImageRoutes.Plan p=slow.plan(0)){check(p.hosts.get(0).equals("b.example"));}
        try(ImageRoutes.Plan p=slow.plan(1)){check(!p.hosts.get(0).equals("b.example"));}
        System.out.println("ImageRoutesTest: "+checks+" checks passed");
    }
}
