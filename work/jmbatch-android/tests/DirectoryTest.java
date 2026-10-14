import app.jmbatch.android.DirectoryTargets;
import app.jmbatch.android.DirectoryTargets.Target;
import java.util.*;

public class DirectoryTest {
    private static int checks;
    private static void check(boolean ok){checks++;if(!ok)throw new AssertionError("Directory check "+checks);}
    public static void main(String[] args) {
        Target documents=new Target("z.documents/Files",true,true,true,true,true);
        Target vendor=new Target("a.vendor/Folder",true,true,true,true,false);
        Target thirdParty=new Target("a.thirdparty/Folder",false,true,true,true,false);
        List<String> attempts=new ArrayList<>();
        check(DirectoryTargets.open(Arrays.asList(vendor,thirdParty,documents),attempts::add));
        check(attempts.equals(Arrays.asList(documents.component)));
        attempts.clear();
        check(DirectoryTargets.open(Arrays.asList(documents,vendor,documents),name->{attempts.add(name);if(name.equals(documents.component))throw new SecurityException();}));
        check(attempts.equals(Arrays.asList(documents.component,vendor.component)));
        attempts.clear();
        check(!DirectoryTargets.open(Arrays.asList(documents,vendor,thirdParty),name->{attempts.add(name);throw new IllegalStateException();}));
        check(attempts.equals(Arrays.asList(documents.component,vendor.component)));
        attempts.clear();
        check(!DirectoryTargets.open(Collections.emptyList(),attempts::add));
        check(!DirectoryTargets.open(Arrays.asList(thirdParty),attempts::add));
        check(!DirectoryTargets.open(Arrays.asList(
            new Target("disabled",true,false,true,true,true),
            new Target("private",true,true,false,true,true),
            new Target("wildcard",true,true,true,false,false)),attempts::add));
        check(attempts.isEmpty());
        check(DirectoryTargets.open(Arrays.asList(vendor),attempts::add));
        check(attempts.equals(Arrays.asList(vendor.component)));
        attempts.clear();
        check(!DirectoryTargets.open(Arrays.asList(documents,documents),name->{attempts.add(name);throw new SecurityException();}));
        check(attempts.size()==1);
        System.out.println("System directory selection and fallback: "+checks+" checks passed");
    }
}
