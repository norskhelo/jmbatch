import app.jmbatch.android.DownloadCoverRules;
import java.io.*;
import java.nio.file.*;
import java.util.UUID;

public class DownloadCoverTest {
    private static int checks;
    private static void check(boolean value){checks++;if(!value)throw new AssertionError("Download cover check "+checks);}
    public static void main(String[] args)throws Exception {
        Path work=Files.createTempDirectory(Paths.get(args[0]),"live-covers-");
        String key=UUID.randomUUID().toString(),other=UUID.randomUUID().toString();
        Path first=work.resolve(key).resolve("images/0001/00001.jpg");Files.createDirectories(first.getParent());
        Files.write(first.resolveSibling("00002.jpg"),new byte[]{2});
        Files.write(first.resolveSibling("00001.partial.jpg"),new byte[]{3});
        Path later=work.resolve(key).resolve("images/0002/00001.jpg");Files.createDirectories(later.getParent());Files.write(later,new byte[]{4});
        check(DownloadCoverRules.resolve(work.toFile(),key,"running","","images")==null);
        check(DownloadCoverRules.resolve(work.toFile(),key,"running","","images",2).path.equals(later.toString()));
        Files.write(first,new byte[]{1});
        DownloadCoverRules.Source before=DownloadCoverRules.resolve(work.toFile(),key,"running","","pdf");
        check(before.path.equals(first.toString())&&before.format.equals("image"));
        for(String status:new String[]{"running","paused","queued","resetting","failed","cancelled","done"})
            check(DownloadCoverRules.resolve(work.toFile(),key,status,"file:///result.zip","zip").stamp.equals(before.stamp));
        check(DownloadCoverRules.resolve(work.toFile(),other,"running","","images")==null);
        Files.write(first,new byte[]{1,2});
        check(!DownloadCoverRules.resolve(work.toFile(),key,"running","","pdf").stamp.equals(before.stamp));
        Files.delete(first);
        for(String format:new String[]{"images","zip","pdf"}){
            DownloadCoverRules.Source completed=DownloadCoverRules.resolve(work.toFile(),key,"done","content://test/"+format,format);
            check(completed.format.equals(format)&&completed.path.equals("content://test/"+format));
            check(DownloadCoverRules.resolve(work.toFile(),key,"running","content://test/"+format,format)==null);
        }
        check(DownloadCoverRules.resolve(work.toFile(),key,"done","","images")==null);
        try{DownloadCoverRules.resolve(work.toFile(),"../escape","running","","pdf");throw new AssertionError();}catch(IOException expected){check(true);}
        System.out.println("Live download cover sources: "+checks+" checks passed");
    }
}
