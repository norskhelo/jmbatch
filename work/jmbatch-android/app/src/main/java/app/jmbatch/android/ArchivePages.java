package app.jmbatch.android;

import java.io.*;
import java.util.*;
import java.util.zip.*;

public final class ArchivePages {
    public static final int MAX_PAGES=20000;
    public static final long MAX_IMAGE_BYTES=128L*1024*1024,MAX_TOTAL_BYTES=8L*1024*1024*1024;
    public static final class Page {
        public final ZipEntry entry;public final int chapter,page;
        Page(ZipEntry value,int chapterNumber,int pageNumber){entry=value;chapter=chapterNumber;page=pageNumber;}
    }
    public static int natural(String first,String second){
        int left=0,right=0;
        while(left<first.length()&&right<second.length()){
            char leftCharacter=first.charAt(left),rightCharacter=second.charAt(right);
            if(leftCharacter>='0'&&leftCharacter<='9'&&rightCharacter>='0'&&rightCharacter<='9'){
                int endLeft=left,endRight=right;
                while(endLeft<first.length()&&first.charAt(endLeft)>='0'&&first.charAt(endLeft)<='9')endLeft++;
                while(endRight<second.length()&&second.charAt(endRight)>='0'&&second.charAt(endRight)<='9')endRight++;
                String numberLeft=first.substring(left,endLeft).replaceFirst("^0+(?!$)",""),numberRight=second.substring(right,endRight).replaceFirst("^0+(?!$)","");
                int order=Integer.compare(numberLeft.length(),numberRight.length());if(order==0)order=numberLeft.compareTo(numberRight);if(order!=0)return order;
                left=endLeft;right=endRight;
            }else{int order=Character.compare(Character.toLowerCase(leftCharacter),Character.toLowerCase(rightCharacter));if(order!=0)return order;left++;right++;}
        }
        return Integer.compare(first.length()-left,second.length()-right);
    }
    public static List<Page> read(ZipFile zip)throws IOException {
        List<ZipEntry> images=new ArrayList<>();Set<String> seen=new HashSet<>();long total=0;
        Enumeration<? extends ZipEntry> entries=zip.entries();
        while(entries.hasMoreElements()){
            ZipEntry entry=entries.nextElement();String name=entry.getName();
            if(name.startsWith("/")||name.contains("\\"))throw new IOException("ZIP 包含不安全路径");
            boolean hidden=false;for(String part:name.split("/")){
                if(part.equals("..")||part.equals(".")||part.contains(":"))throw new IOException("ZIP 包含不安全路径");
                if(part.startsWith(".")||part.startsWith("__MACOSX"))hidden=true;
            }
            if(entry.isDirectory()||hidden||!name.toLowerCase(Locale.ROOT).matches(".*\\.(jpg|jpeg|png|webp)"))continue;
            if(!seen.add(name.toLowerCase(Locale.ROOT))||entry.getSize()<=0||entry.getSize()>MAX_IMAGE_BYTES)throw new IOException("ZIP 图片重复、为空或过大");
            total+=entry.getSize();images.add(entry);
            if(images.size()>MAX_PAGES||total>MAX_TOTAL_BYTES)throw new IOException("ZIP 图片数量或总大小超出支持范围");
        }
        if(images.isEmpty())throw new IOException("ZIP 中没有可用图片");
        images.sort((first,second)->natural(first.getName(),second.getName()));
        Map<String,Integer> chapters=new LinkedHashMap<>();Map<Integer,Integer> counts=new HashMap<>();List<Page> result=new ArrayList<>();
        for(ZipEntry entry:images){String name=entry.getName();String parent=name.substring(0,name.lastIndexOf('/')+1);if(!chapters.containsKey(parent))chapters.put(parent,chapters.size()+1);
            int chapter=chapters.get(parent),page=counts.getOrDefault(chapter,0)+1;counts.put(chapter,page);result.add(new Page(entry,chapter,page));}
        return result;
    }
}
