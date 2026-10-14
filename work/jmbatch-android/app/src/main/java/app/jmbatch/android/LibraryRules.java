package app.jmbatch.android;

import java.io.*;
import java.nio.file.Files;
import java.util.Locale;
import java.util.regex.*;
import java.util.*;
import java.util.function.BooleanSupplier;

/** File safety and search rules shared by the library and host tests. */
public final class LibraryRules {
    public static final class Scan {
        public final List<File> files=new ArrayList<>();
        public int skipped;
    }
    public static Scan scanOwned(File folder,BooleanSupplier cancelled)throws IOException {
        Scan result=new Scan();if(!folder.exists())return result;
        File[] files=folder.listFiles();if(files==null)throw new IOException("保存目录无法读取，请确认存储可用");
        for(File file:files){
            if(cancelled.getAsBoolean())throw new java.util.concurrent.CancellationException("扫描已取消");
            if(!supported(file.getName()))continue;
            try{File checked=ownedFile(folder,file.getName());if(checked.length()==0){result.skipped++;continue;}result.files.add(checked);}
            catch(IOException invalid){result.skipped++;}
        }
        return result;
    }
    public static String idFromName(String name) {
        String stem=name.replaceFirst("(?i)\\.(pdf|zip)$", "");
        Matcher match=Pattern.compile("^(?:JM)?([0-9]{3,10})(?=$|[\\s_.-])",Pattern.CASE_INSENSITIVE).matcher(stem);
        return match.find()?match.group(1):"";
    }
    public static boolean supported(String name) {
        String lower=name.toLowerCase(Locale.ROOT);
        return lower.endsWith(".pdf") || lower.endsWith(".zip");
    }
    public static boolean matches(String id,String title,String uri,boolean favorite,String query,boolean favoritesOnly) {
        return (!favoritesOnly||favorite) && (id+" "+title+" "+uri).toLowerCase(Locale.ROOT).contains(query.trim().toLowerCase(Locale.ROOT));
    }
    public static File ownedFile(File directory,String name) throws IOException {
        if(name==null||name.isEmpty()||name.contains("/")||name.contains("\\")||!supported(name))
            throw new IOException("只允许管理记录中的 PDF / ZIP 文件");
        File base=directory.getCanonicalFile(), file=new File(base,name);
        if(Files.isSymbolicLink(file.toPath())||!base.equals(file.getCanonicalFile().getParentFile()))
            throw new IOException("文件已离开应用保存目录");
        if(!file.isFile())throw new FileNotFoundException("文件不存在、已移动，或存储暂时不可用");
        return file;
    }
}
