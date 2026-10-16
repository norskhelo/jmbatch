import app.jmbatch.android.ReaderRules;
import java.util.*;

public class ReaderTest {
    static int checks;
    static void check(boolean value,String label){if(!value)throw new AssertionError(label);checks++;}
    public static void main(String[] args){
        List<Integer> starts=ReaderRules.starts(new int[]{1,1,1,2,2,3});
        check(starts.equals(Arrays.asList(0,3,5)),"chapter boundaries");
        check(ReaderRules.chapter(starts,0)==0,"first chapter");
        check(ReaderRules.chapter(starts,2)==0,"last page of chapter");
        check(ReaderRules.chapter(starts,3)==1,"next chapter");
        check(ReaderRules.chapter(starts,5)==2,"last chapter");
        check(ReaderRules.clamp(-1,6)==0&&ReaderRules.clamp(6,6)==5,"page bounds");
        check(ReaderRules.bookmarks(Arrays.asList(0,3,3,9,-1),6).equals(new TreeSet<>(Arrays.asList(0,3))),"bookmarks filtered and unique");
        int[] size=ReaderRules.size(600,900,300,0);check(size[0]==300&&size[1]==450,"scroll fit width");
        size=ReaderRules.size(600,900,300,200);check(size[1]<=200&&size[0]<=300,"page fits viewport");
        size=ReaderRules.size(1000,90000,1600,0);check(size[1]<=8192&&(long)size[0]*size[1]<=4000000,"long page decode bound");
        check(ReaderRules.sample(8000,10000,new int[]{800,1000})==8,"sample before decoding");
        try{ReaderRules.size(0,100,300,0);throw new AssertionError("invalid dimensions accepted");}catch(IllegalArgumentException expected){checks++;}
        int[] longBook=new int[7227];for(int i=0;i<longBook.length;i++)longBook[i]=i/100+1;
        check(ReaderRules.starts(longBook).size()==73,"long manga chapters");
        check(ReaderRules.clamp(7227,7227)==7226,"long manga last page");
        System.out.println("ReaderTest: "+checks+" checks passed");
    }
}
