import app.jmbatch.android.ChapterRules;
import java.util.*;

public class ChapterTest {
    static int checks;
    static void check(boolean ok){checks++;if(!ok)throw new AssertionError("Chapter check "+checks);}
    public static void main(String[] args)throws Exception{
        ChapterRules.Chapter one=new ChapterRules.Chapter("800001",1,"One"),two=new ChapterRules.Chapter("800002",2,"Two");
        List<ChapterRules.Chapter> catalog=Arrays.asList(one,two),empty=Collections.emptyList();
        try{ChapterRules.resolve(catalog,empty,false);throw new AssertionError();}
        catch(ChapterRules.ChoiceRequired choice){check(choice.chapters.equals(catalog));}
        check(ChapterRules.resolve(catalog,empty,true).equals(catalog));
        check(ChapterRules.resolve(Arrays.asList(one),empty,false).size()==1);
        List<ChapterRules.Chapter> chosen=ChapterRules.select(catalog,new HashSet<>(Arrays.asList("800002")));
        check(chosen.size()==1&&chosen.get(0).number==2);
        check(ChapterRules.resolve(Arrays.asList(two,one),chosen,true).equals(chosen));
        try{ChapterRules.resolve(Arrays.asList(one),chosen,true);throw new AssertionError();}catch(IllegalArgumentException expected){check(true);}
        for(Set<String> ids:Arrays.asList(Collections.<String>emptySet(),Collections.singleton("missing"))){
            try{ChapterRules.select(catalog,ids);throw new AssertionError();}catch(IllegalArgumentException expected){check(true);}
        }
        check(ChapterRules.select(catalog,new HashSet<>(Arrays.asList("800002","800001"))).get(0).id.equals("800001"));
        try{ChapterRules.resolve(Arrays.asList(one,one),empty,true);throw new AssertionError();}catch(IllegalArgumentException expected){check(true);}
        System.out.println("Chapter selection: "+checks+" checks passed");
    }
}
