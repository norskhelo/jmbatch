import app.jmbatch.android.SinglePageRecovery;
import app.jmbatch.android.UpdateRules;
import java.util.*;
import java.io.*;
public class RecoveryTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
    public static void main(String[] args)throws Exception{
        List<SinglePageRecovery.Failure<Integer>> failed=new ArrayList<>();
        failed.add(new SinglePageRecovery.Failure<>(2,new IOException("timeout"),"第 1 章第 2 页"));
        List<Integer> requested=new ArrayList<>();
        SinglePageRecovery.recover(failed,(page,round)->requested.add(page),()->{},s->{},e->true);
        check(requested.equals(Arrays.asList(2)));
        requested.clear();
        try{SinglePageRecovery.recover(failed,(page,round)->{requested.add(page);throw new IOException("timeout");},()->{},s->{},e->true);throw new AssertionError();}
        catch(IOException e){check(e.getMessage().contains("第 1 章第 2 页"));}
        check(requested.equals(Arrays.asList(2,2)));
        requested.clear();
        failed.add(new SinglePageRecovery.Failure<>(3,new IOException("timeout"),"第 1 章第 3 页"));
        try{SinglePageRecovery.recover(failed,(page,round)->requested.add(page),()->{},s->{},e->true);throw new AssertionError();}
        catch(IOException e){check(e.getMessage().contains("2 页下载失败"));}
        check(requested.isEmpty());failed.remove(1);
        try{SinglePageRecovery.recover(failed,(page,round)->requested.add(page),()->{throw new IOException("PAUSE");},s->{},e->true);throw new AssertionError();}
        catch(IOException e){check(e.getMessage().equals("PAUSE"));}
        check(requested.isEmpty());
        try{SinglePageRecovery.recover(failed,(page,round)->requested.add(page),()->{},s->{},e->false);throw new AssertionError();}
        catch(IOException e){check(requested.isEmpty());}
        check(UpdateRules.announcement("owner/app","owner/app","0.2.6","0.2.6","full notes","local").contains("full notes"));
        check(UpdateRules.announcement("owner/app","other/app","0.2.6","0.2.6","full notes","local").equals("local"));
        check(UpdateRules.announcement("owner/app","owner/app","0.2.5","0.2.6","old notes","local").equals("local"));
        check(UpdateRules.announcement("","owner/app","","0.2.6","","local").equals("local"));
        System.out.println("Recovery and announcements: "+checks+" checks passed");
    }
}
