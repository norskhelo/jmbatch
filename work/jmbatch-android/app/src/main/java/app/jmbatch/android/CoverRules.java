package app.jmbatch.android;

import java.io.*;
import java.util.*;
import java.util.zip.*;

/** First-page selection and resource limits, shared by the reader and host tests. */
public final class CoverRules {
    public static final int MAX_IMAGE_BYTES=32*1024*1024;
    public static boolean imageEntry(String name){
        String normalized=name.replace('\\','/');
        for(String part:normalized.split("/",-1))if(part.isEmpty()||part.startsWith(".")||part.equals("__MACOSX"))return false;
        return normalized.toLowerCase(Locale.ROOT).matches(".*\\.(jpg|jpeg|png|webp|gif|bmp)");
    }
    public static int comparePages(String a,String b){
        a=a.replace('\\','/').toLowerCase(Locale.ROOT);b=b.replace('\\','/').toLowerCase(Locale.ROOT);
        int i=0,j=0;
        while(i<a.length()&&j<b.length()){
            char x=a.charAt(i),y=b.charAt(j);
            if(x>='0'&&x<='9'&&y>='0'&&y<='9'){
                int ai=i,bj=j;while(i<a.length()&&a.charAt(i)>='0'&&a.charAt(i)<='9')i++;while(j<b.length()&&b.charAt(j)>='0'&&b.charAt(j)<='9')j++;
                String left=a.substring(ai,i).replaceFirst("^0+(?!$)",""),right=b.substring(bj,j).replaceFirst("^0+(?!$)","");
                int cmp=Integer.compare(left.length(),right.length());if(cmp==0)cmp=left.compareTo(right);if(cmp!=0)return cmp;
            }else{if(x!=y)return Character.compare(x,y);i++;j++;}
        }
        return Integer.compare(a.length()-i,b.length()-j);
    }
    public static ZipEntry firstImage(ZipFile zip)throws IOException {
        ZipEntry first=null;Enumeration<? extends ZipEntry> entries=zip.entries();
        while(entries.hasMoreElements()){ZipEntry e=entries.nextElement();if(!e.isDirectory()&&imageEntry(e.getName())&&(first==null||comparePages(e.getName(),first.getName())<0))first=e;}
        if(first==null||first.getSize()>MAX_IMAGE_BYTES)throw new IOException("没有可读取的第一页");return first;
    }
    public static byte[] readImage(InputStream stream)throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[16384];int n;
        while((n=stream.read(buffer))!=-1){if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();if(out.size()+n>MAX_IMAGE_BYTES)throw new IOException("封面图片过大");out.write(buffer,0,n);}return out.toByteArray();
    }
    public static int sampleSize(int width,int height)throws IOException {
        if(width<=0||height<=0||(long)width*height>40000000)throw new IOException("封面尺寸无效或过大");
        int sample=1;while(width/(sample*2)>=192||height/(sample*2)>=256)sample*=2;return sample;
    }
}
