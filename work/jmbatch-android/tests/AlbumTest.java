import app.jmbatch.android.AlbumRules;
import app.jmbatch.android.Core;
import java.io.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

public class AlbumTest {
    static int checks;
    static void check(boolean value,String label){if(!value)throw new AssertionError(label);checks++;}
    public static void main(String[] args)throws Exception {
        check(AlbumRules.imageName(1,2).equals("0001/00002.jpg"),"ordered image name");
        check(AlbumRules.imageName(2,1).compareTo(AlbumRules.imageName(10,1))<0,"chapter numeric order");
        check(AlbumRules.imageName(1,2).compareTo(AlbumRules.imageName(1,10))<0,"page numeric order");
        try{AlbumRules.imageName(-1,2);throw new AssertionError("invalid chapter");}catch(IOException expected){checks++;}
        check(AlbumRules.exportName("123456","title","token","pdf",true,1).equals("123456-0001.pdf"),"chapter filename");
        check(AlbumRules.exportName("123456","title","token","pdf",true,0).equals("123456.pdf"),"merged filename");
        check(AlbumRules.group("zip",true,2)==0,"ZIP keeps chapters together");
        check(AlbumRules.group("pdf",false,2)==0,"merged PDF");
        check(AlbumRules.group("pdf",true,2)==2,"split PDF");
        File root=new File(args[0]);root.mkdirs();Map<Integer,List<Core.Page>> groups=new TreeMap<>();List<Core.Page> all=new ArrayList<>();
        for(int c=1;c<=2;c++)for(int p=1;p<=(c==1?3:2);p++){
            File image=new File(root,AlbumRules.imageName(c,p));image.getParentFile().mkdirs();ImageIO.write(new BufferedImage(12,16,BufferedImage.TYPE_INT_RGB),"jpg",image);
            Core.Page page=new Core.Page(image,12,16);groups.computeIfAbsent(AlbumRules.group("pdf",true,c),k->new ArrayList<>()).add(page);all.add(page);
        }
        File merged=new File(root,"merged.pdf");Core.writePdf(merged,all,(a,b)->{});
        check(new String(Files.readAllBytes(merged.toPath()),StandardCharsets.ISO_8859_1).contains("/Count 5"),"merged five pages");
        for(Map.Entry<Integer,List<Core.Page>> group:groups.entrySet()){
            File pdf=new File(root,AlbumRules.exportName("123456","title","token","pdf",true,group.getKey()));Core.writePdf(pdf,group.getValue(),(a,b)->{});
            check(new String(Files.readAllBytes(pdf.toPath()),StandardCharsets.ISO_8859_1).contains("/Count "+group.getValue().size()),"split chapter page count");
        }
        check(all.stream().allMatch(page->page.jpeg.isFile()),"original images remain");
        System.out.println("AlbumTest: "+checks+" checks passed");
    }
}
