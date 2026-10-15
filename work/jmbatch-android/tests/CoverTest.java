import app.jmbatch.android.CoverRules;
import java.io.*;
import java.nio.file.*;
import java.util.zip.*;

public class CoverTest {
    private static int checks;
    private static void check(boolean value){checks++;if(!value)throw new AssertionError("Cover check "+checks);}
    public static void main(String[] args)throws Exception {
        check(CoverRules.comparePages("2/2.jpg","2/10.jpg")<0);
        check(CoverRules.comparePages("2/10.jpg","10/1.jpg")<0);
        check(CoverRules.comparePages("0001/00001.JPG","1/1.jpg")==0);
        check(CoverRules.comparePages("2.jpg","100000000000000000000000.jpg")<0);
        for(String name:new String[]{"../1.jpg","/1.jpg",".hidden/1.jpg","__MACOSX/1.jpg","notes.json"})check(!CoverRules.imageEntry(name));
        check(CoverRules.imageEntry("0001/00001.JPG"));check(CoverRules.sampleSize(600,800)==2);
        for(int[] size:new int[][]{{0,1},{50000,50000},{-1,800}}){try{CoverRules.sampleSize(size[0],size[1]);throw new AssertionError();}catch(IOException expected){check(true);}}
        Path file=Files.createTempFile(Paths.get(args[0]),"cover-",".zip");
        try{
            try(ZipOutputStream out=new ZipOutputStream(Files.newOutputStream(file))){for(String name:new String[]{"10/1.jpg","2/10.jpg","2/2.jpg","../1.jpg","__MACOSX/0.jpg"}){out.putNextEntry(new ZipEntry(name));out.write(new byte[]{1,2,3});out.closeEntry();}}
            try(ZipFile zip=new ZipFile(file.toFile())){ZipEntry first=CoverRules.firstImage(zip);check(first.getName().equals("2/2.jpg"));try(InputStream in=zip.getInputStream(first)){check(CoverRules.readImage(in).length==3);}}
        }finally{Files.delete(file);}
        InputStream huge=new InputStream(){int left=CoverRules.MAX_IMAGE_BYTES+1;public int read(){return left-->0?0:-1;}public int read(byte[] b,int off,int len){if(left<=0)return -1;int n=Math.min(left,len);left-=n;return n;}};
        try{CoverRules.readImage(huge);throw new AssertionError();}catch(IOException expected){check(true);}
        System.out.println("Library first-page covers: "+checks+" checks passed");
    }
}
