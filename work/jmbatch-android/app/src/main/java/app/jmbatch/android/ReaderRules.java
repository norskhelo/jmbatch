package app.jmbatch.android;

import java.util.*;

/** Pure navigation and bounded decode rules, shared by reader and host tests. */
public final class ReaderRules {
    public static int clamp(int page,int total){return Math.max(0,Math.min(total-1,page));}
    public static List<Integer> starts(int[] chapters){
        List<Integer> result=new ArrayList<>();
        for(int i=0;i<chapters.length;i++)if(i==0||chapters[i]!=chapters[i-1])result.add(i);
        return result;
    }
    public static int chapter(List<Integer> starts,int page){
        int found=Collections.binarySearch(starts,page);return found>=0?found:Math.max(0,-found-2);
    }
    public static int[] size(int width,int height,int targetWidth,int targetHeight){
        if(width<=0||height<=0||(long)width*height>100000000L)throw new IllegalArgumentException("图片尺寸超出支持范围");
        double scale=Math.min(1,Math.min(Math.min(1600,targetWidth)/(double)width,Math.min(8192.0/height,Math.sqrt(4000000.0/((double)width*height)))));
        if(targetHeight>0)scale=Math.min(scale,targetHeight/(double)height);
        return new int[]{Math.max(1,(int)(width*scale)),Math.max(1,(int)(height*scale))};
    }
    public static int sample(int width,int height,int[] target){
        int sample=1;while(width/(sample*2)>=target[0]&&height/(sample*2)>=target[1])sample*=2;return sample;
    }
    public static TreeSet<Integer> bookmarks(Collection<Integer> values,int total){
        TreeSet<Integer> result=new TreeSet<>();for(int value:values)if(value>=0&&value<total)result.add(value);return result;
    }
}
