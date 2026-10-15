import app.jmbatch.android.Core;
import app.jmbatch.android.UpdateRules;
import java.io.*;
import java.util.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

public class CoreTest {
    static int checks;
    static void check(boolean value,String label){if(!value)throw new AssertionError(label);checks++;}
    public static void main(String[] args)throws Exception{
        check(UpdateRules.initialRepository("",false).equals("norskhelo/jmbatch"),"new/legacy blank default repository");
        check(UpdateRules.initialRepository("owner/app",false).equals("owner/app"),"preserve custom repository");
        check(UpdateRules.initialRepository("",true).isEmpty(),"preserve explicitly cleared repository");
        check(UpdateRules.repository("https://github.com/owner/app.git/").equals("owner/app"),"repository URL");
        check(UpdateRules.repository("").isEmpty(),"empty disables checks");
        for(String invalid:new String[]{"http://github.com/owner/app","https://evil.example/owner/app","owner/app/releases","owner/.."}){
            boolean rejected=false;try{UpdateRules.repository(invalid);}catch(IllegalArgumentException expected){rejected=true;}check(rejected,"invalid update repo");
        }
        check(UpdateRules.compare("0.2.10","0.2.9")>0,"numeric update version");
        check(UpdateRules.compare("0.2.2","0.2.2")==0,"same version");
        check(UpdateRules.assetVersion("JMBatch-0.2.3-Android.apk").equals("0.2.3"),"Android update asset");
        check(UpdateRules.assetVersion("JMBatch-9.0.0-Windows-x64.zip")==null,"other platform ignored");
        String updateName="JMBatch-0.2.3-Android.apk",updateUrl="https://github.com/owner/app/releases/download/v3/"+updateName;
        check(UpdateRules.validUrl(updateUrl,"owner/app",updateName),"trusted download");
        check(!UpdateRules.validUrl(updateUrl.replace("github.com","github.com.evil.example"),"owner/app",updateName),"foreign host rejected");
        check(!UpdateRules.validUrl(updateUrl,"other/repo",updateName),"foreign repository rejected");
        check(!UpdateRules.validUrl(updateUrl.replace("/v3/","/../../"),"owner/app",updateName),"path traversal rejected");
        check(Core.outputName("123456","title","pdf",true).equals("123456.pdf"),"numeric PDF");
        check(Core.outputName("123456","title","zip",true).equals("123456.zip"),"numeric ZIP");
        check(Core.outputName("123456","title","zip",false).matches("JM123456-title-[0-9a-f]{8}\\.zip"),"legacy filename");
        check(Core.zipImageName(true,2,4,2,1).equals("0002/00001.jpg"),"multi-chapter overrides flat setting");
        check(Core.zipImageName(false,2,4,2,1).equals("0002/00001.jpg"),"chapter ZIP hierarchy");
        check(Core.zipImageName(true,1,20000,1,20000).equals("20000.jpg"),"single-chapter flat sequence");
        check(Core.zipImageName(false,1,1,1,1).equals("00001.jpg"),"single-chapter ignores legacy setting");
        check(Core.parseIds("JM123456，123457\n123456;123458 至 JM123460").equals(Arrays.asList("123456","123457","123458","123459","123460")),"parse and deduplicate");
        for(String invalid:new String[]{"","000","123456-123400","123456-9000000000","12","123456/path"}){
            boolean rejected=false;try{Core.parseIds(invalid);}catch(IllegalArgumentException expected){rejected=true;}check(rejected,"reject "+invalid);
        }
        check(Core.decrypt("HwoKLf5mI5eCAmt1zSQBMxSeVAtaes6+B1gnn+PxxGwW/BjFByGuhNemotgHMIeR","1700566805",Core.API_SECRET).equals("{\"id\":123456,\"name\":\"offline-test\"}"),"AES matches Python jmcomic");
        long[] ids={219979,220980,268849,268850,421925,421926,1461466};int[] expected={0,10,10,6,18,14,14};
        for(int i=0;i<ids.length;i++)check(Core.segments(220980,ids[i],"00001")==expected[i],"segment vector "+ids[i]);
        for(int height:new int[]{103,1000,2001})for(int count:new int[]{2,8,10,18}){
            int[] seen=new int[height],result=new int[height];
            for(int i=0;i<count;i++){int[] strip=Core.strip(height,count,i);for(int j=0;j<strip[2];j++){seen[strip[1]+j]++;result[strip[1]+j]=strip[0]+j;}}
            for(int n:seen)if(n!=1)throw new AssertionError("missing/overlapping decoded rows");
            boolean[] used=new boolean[height];for(int n:result){if(used[n])throw new AssertionError("duplicate source row");used[n]=true;}checks++;
        }
        check(!Core.error(new IOException("secret-cookie https://invalid.example/?token=hidden"),"AVS=secret-cookie").contains("secret-cookie"),"cookie redaction");
        File directory=new File(args[0]);directory.mkdirs();java.util.List<Core.Page> pages=new ArrayList<>();
        for(int i=1;i<=3;i++){
            BufferedImage bitmap=new BufferedImage(300,400,BufferedImage.TYPE_INT_RGB);Graphics2D g=bitmap.createGraphics();g.setColor(Color.WHITE);g.fillRect(0,0,300,400);g.setColor(new Color(8,127,140));g.fillRect(20,20,260,60);g.setColor(Color.BLACK);g.drawString("Offline Android PDF test - page "+i,25,150);g.dispose();File image=new File(directory,"page"+i+".jpg");ImageIO.write(bitmap,"jpg",image);pages.add(new Core.Page(image,300,400));
        }
        Core.writePdf(new File(directory,"test.pdf"),pages,(n,total)->check(n>=1&&n<=3&&total==3,"PDF progress"));
        check(new File(directory,"test.pdf").length()>1000,"PDF generated");
        for(boolean flat:new boolean[]{false,true}){
            File zipped=new File(directory,"chapters-"+flat+".zip");
            try(java.util.zip.ZipOutputStream out=new java.util.zip.ZipOutputStream(new FileOutputStream(zipped))){
                for(int n=0;n<3;n++){
                    out.putNextEntry(new java.util.zip.ZipEntry(Core.zipImageName(flat,2,n+1,n<2?1:2,n<2?n+1:1)));
                    try(InputStream in=new FileInputStream(new File(directory,"page"+(n+1)+".jpg"))){Core.copy(in,out);}out.closeEntry();
                }
            }
            try(java.util.zip.ZipFile zip=new java.util.zip.ZipFile(zipped)){
                check(zip.size()==3,"multi-chapter archive size");
                for(String name:new String[]{"0001/00001.jpg","0001/00002.jpg","0002/00001.jpg"}){
                    check(zip.getEntry(name)!=null,"chapter path "+name);
                    try(InputStream in=zip.getInputStream(zip.getEntry(name))){check(ImageIO.read(in)!=null,"archive image readable");}
                }
            }
        }
        System.out.println("PASS: "+checks+" checks; protocol vectors, row mapping, input validation, privacy, streaming PDF");
    }
}
