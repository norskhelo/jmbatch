import app.jmbatch.android.BatchOperations;
import app.jmbatch.android.LibraryRules;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

public class BatchTest {
    private static int checks;
    private static void check(boolean ok){checks++;if(!ok)throw new AssertionError("Batch check "+checks);}
    public static void main(String[] args)throws Exception{
        check(LibraryRules.idFromName("JM123456_title.ZIP").equals("123456"));
        check(LibraryRules.idFromName("123456.pdf").equals("123456"));
        check(LibraryRules.idFromName("unknown title.zip").isEmpty());
        check(LibraryRules.idFromName("123456789012_title.pdf").isEmpty());
        check(LibraryRules.idFromName("123456abc.zip").isEmpty());
        List<Integer> completed=new ArrayList<>();List<Integer> progress=new ArrayList<>();
        BatchOperations.Result partial=BatchOperations.run(Arrays.asList(1,2,3),item->{if(item==2)throw new IOException("denied");completed.add(item);},()->false,Object::toString,(done,total)->progress.add(done));
        check(partial.succeeded==2&&partial.failed==1&&partial.unprocessed==0);
        check(completed.equals(Arrays.asList(1,3)));check(partial.errors.get(0).contains("2：denied"));check(progress.equals(Arrays.asList(1,2,3)));
        AtomicBoolean cancelled=new AtomicBoolean();
        BatchOperations.Result stopped=BatchOperations.run(Arrays.asList(1,2,3),item->cancelled.set(true),cancelled::get,Object::toString,(done,total)->{});
        check(stopped.succeeded==1&&stopped.unprocessed==2&&stopped.failed==0);
        BatchOperations.Result untouched=BatchOperations.run(Arrays.asList(1,2),item->{throw new AssertionError();},()->true,Object::toString,(done,total)->{});
        check(untouched.unprocessed==2&&untouched.succeeded==0);
        Path root=Files.createTempDirectory(Paths.get(args[0]),"scan-");
        List<Path> files=new ArrayList<>();
        try{
            for(String name:Arrays.asList("123456.pdf","JM999999_Title.ZIP","unknown.zip","temp.zip.partial")){Path file=root.resolve(name);Files.write(file,new byte[]{1});files.add(file);}
            Path empty=root.resolve("empty.pdf");Files.createFile(empty);files.add(empty);
            Path sub=root.resolve("sub.zip");Files.createDirectory(sub);Path hidden=sub.resolve("444444.zip");Files.write(hidden,new byte[]{1});
            LibraryRules.Scan scan=LibraryRules.scanOwned(root.toFile(),()->false);check(scan.files.size()==3&&scan.skipped==2);check(Files.exists(hidden));
            try{LibraryRules.scanOwned(root.toFile(),()->true);throw new AssertionError();}catch(java.util.concurrent.CancellationException expected){check(true);}
            Files.delete(hidden);Files.delete(sub);
            check(LibraryRules.scanOwned(root.resolve("absent").toFile(),()->false).files.isEmpty());
        }finally{for(Path path:files)Files.deleteIfExists(path);Files.delete(root);}
        System.out.println("Batch actions and directory scanning: "+checks+" checks passed");
    }
}
