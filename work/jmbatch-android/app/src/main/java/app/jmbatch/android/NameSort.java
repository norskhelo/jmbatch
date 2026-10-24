package app.jmbatch.android;

import java.util.*;

/** Left-to-right character keys, using the same offline pinyin table as Windows. */
final class NameSort {
    private static final Map<Integer,String> READINGS = new HashMap<>();
    static {
        for(String row:NamePinyinData.GROUPS) {
            int split=row.indexOf('\t');
            String reading=row.substring(0,split);
            for(int i=split+1;i<row.length();) {
                int cp=row.codePointAt(i);i+=Character.charCount(cp);
                READINGS.put(cp,reading);
            }
        }
    }
    static String[] key(String title) {
        String lower=title.toLowerCase(Locale.ROOT);
        String[] result=new String[lower.codePointCount(0,lower.length())];
        for(int i=0,index=0;i<lower.length();index++) {
            int cp=lower.codePointAt(i);i+=Character.charCount(cp);
            result[index]=READINGS.getOrDefault(cp,new String(Character.toChars(cp)));
        }
        return result;
    }
    static int compare(String[] left,String[] right) {
        for(int i=0;i<Math.min(left.length,right.length);i++) {
            int result=compareCodePoints(left[i],right[i]);
            if(result!=0)return result;
        }
        return Integer.compare(left.length,right.length);
    }
    private static int compareCodePoints(String left,String right) {
        int a=0,b=0;
        while(a<left.length()&&b<right.length()) {
            int x=left.codePointAt(a),y=right.codePointAt(b);
            if(x!=y)return Integer.compare(x,y);
            a+=Character.charCount(x);b+=Character.charCount(y);
        }
        return Integer.compare(left.length()-a,right.length()-b);
    }
    private NameSort() {}
}
