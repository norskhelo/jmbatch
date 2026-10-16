import app.jmbatch.android.ArchivePages;
import app.jmbatch.android.AlbumRules;
import java.io.*;
import java.util.*;
import java.util.zip.*;

public class ArchivePagesTest {
    static int checks;
    static void check(boolean value,String name){if(!value)throw new AssertionError(name);checks++;}
    static void archive(File file,String...names)throws Exception {
        try(ZipOutputStream output=new ZipOutputStream(new FileOutputStream(file))){for(String name:names){output.putNextEntry(new ZipEntry(name));output.write(new byte[]{1,2,3});output.closeEntry();}}
    }
    public static void main(String[] args)throws Exception {
        File root=new File(args[0]);root.mkdirs();File archive=new File(root,"pages.zip");
        archive(archive,"chapter10/10.jpg","chapter2/10.jpg","chapter2/2.jpg","info.json","__MACOSX/._1.jpg");
        try(ZipFile zip=new ZipFile(archive)){
            List<ArchivePages.Page> pages=ArchivePages.read(zip);check(pages.size()==3,"metadata excluded");
            check(pages.get(0).entry.getName().equals("chapter2/2.jpg"),"natural chapter and page order");
            check(pages.get(1).chapter==1&&pages.get(1).page==2,"normalized page numbering");
            check(pages.get(2).chapter==2&&pages.get(2).page==1,"normalized chapter numbering");
        }
        archive(archive,"10.jpg","2.jpg");
        try(ZipFile zip=new ZipFile(archive)){List<ArchivePages.Page> pages=ArchivePages.read(zip);check(pages.get(0).entry.getName().equals("2.jpg")&&pages.get(1).chapter==1,"single chapter flat ZIP");}
        for(String bad:new String[]{"../bad.jpg","/bad.jpg","C:/bad.jpg","dir\\bad.jpg"}){
            archive(archive,bad);try(ZipFile zip=new ZipFile(archive)){try{ArchivePages.read(zip);throw new AssertionError("unsafe path accepted");}catch(IOException expected){checks++;}}
        }
        archive(archive,"0001.jpg","0001.JPG");try(ZipFile zip=new ZipFile(archive)){try{ArchivePages.read(zip);throw new AssertionError("duplicate accepted");}catch(IOException expected){checks++;}}
        archive(archive,"info.json");try(ZipFile zip=new ZipFile(archive)){try{ArchivePages.read(zip);throw new AssertionError("empty accepted");}catch(IOException expected){checks++;}}
        check(ArchivePages.natural("99999999999999999999","100000000000000000000")<0,"large numeric names");
        check(AlbumRules.exportName("123456","title","deadbeef","images",false,0).equals("JM123456-title-deadbeef"),"folder export name");
        check(AlbumRules.group("images",true,2)==0,"folder preserves chapters in one output");
        System.out.println("ArchivePagesTest: "+checks+" checks passed");
    }
}
