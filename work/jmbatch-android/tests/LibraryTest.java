import app.jmbatch.android.LibraryRules;
import java.io.*;
import java.nio.file.*;

public class LibraryTest {
    private static int checks;
    private static void check(boolean ok){checks++;if(!ok)throw new AssertionError("Library check "+checks);}
    private static void denied(File root,String name)throws Exception {
        try{LibraryRules.ownedFile(root,name);throw new AssertionError("Unsafe target accepted: "+name);}catch(IOException expected){check(true);}
    }
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory(Paths.get(args[0]),"library-");
        Path pdf=root.resolve("123456.pdf"),zip=root.resolve("123456.zip");Files.write(pdf,new byte[]{1});Files.write(zip,new byte[]{2});
        try {
            check(LibraryRules.supported("123456.PDF"));check(LibraryRules.supported("123456.zip"));check(!LibraryRules.supported("123456.zip.partial"));
            check(LibraryRules.matches("123456","Test comic","/123456.zip",true,"COMIC",true));
            check(LibraryRules.matches("123456","标题","/123456.zip",false,"123456",false));
            check(!LibraryRules.matches("123456","标题","/123456.zip",false,"",true));
            check(!LibraryRules.matches("123456","标题","/123456.zip",true,"missing",false));
            check(LibraryRules.ownedFile(root.toFile(),"123456.pdf").equals(pdf.toFile().getCanonicalFile()));
            check(LibraryRules.ownedFile(root.toFile(),"123456.zip").equals(zip.toFile().getCanonicalFile()));
            denied(root.toFile(),"../123456.zip");denied(root.toFile(),"..\\123456.zip");denied(root.toFile(),"missing.pdf");denied(root.toFile(),"");denied(root.toFile(),"data.json");
            Path directory=root.resolve("folder.zip");Files.createDirectory(directory);denied(root.toFile(),"folder.zip");Files.delete(directory);
            check(Files.exists(pdf)&&Files.exists(zip));
            System.out.println("Library safety and search: "+checks+" checks passed");
        }finally{Files.deleteIfExists(pdf);Files.deleteIfExists(zip);Files.delete(root);}
    }
}
