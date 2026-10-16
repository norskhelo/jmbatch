package app.jmbatch.android;

import android.content.Context;
import android.net.Uri;
import android.graphics.BitmapFactory;
import java.io.*;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;

/** Offline export; originals stay in place and only newly published files roll back. */
public final class AlbumExporter {
    public static List<LibraryStore.Entry> export(Context context,Uri source,String tree,String label,String format,boolean numeric,boolean flat,boolean split,AlbumStorage.Check check,java.util.function.Consumer<String> progress)throws Exception {
        return export(context,source,"images","","",tree,label,format,numeric,flat,split,check,progress);
    }
    public static List<LibraryStore.Entry> export(Context context,Uri source,String sourceFormat,String id,String title,String tree,String label,String format,boolean numeric,boolean flat,boolean split,AlbumStorage.Check check,java.util.function.Consumer<String> progress)throws Exception {
        File temporary=Files.createTempDirectory(context.getCacheDir().toPath(),"export-").toFile();List<Uri> committed=new ArrayList<>();
        try {
        AlbumStorage.Album album=ExportSource.load(context,source,sourceFormat,id,title,temporary,check,progress);check.run();
        Map<Integer,List<AlbumStorage.Image>> groups=new TreeMap<>();
        for(AlbumStorage.Image image:album.images)groups.computeIfAbsent(AlbumRules.group(format,split,image.chapter),k->new ArrayList<>()).add(image);
        String token=UUID.randomUUID().toString().substring(0,8);List<String> names=new ArrayList<>();
        for(int chapter:groups.keySet()){String name=AlbumRules.exportName(album.id,album.title,token,format,numeric,chapter);AlbumStorage.absent(context,tree,name);names.add(name);}
            List<File> outputs=new ArrayList<>();int index=0,completed=0;
            for(List<AlbumStorage.Image> images:groups.values()){
                List<Core.Page> pages=new ArrayList<>();List<File> files=new ArrayList<>();Set<Integer> chapters=new HashSet<>();
                for(AlbumStorage.Image image:images){
                    check.run();File file=new File(temporary,String.format(Locale.ROOT,"%04d-%05d.jpg",image.chapter,image.page));
                    try(InputStream in=AlbumStorage.open(context,image.uri);OutputStream out=new FileOutputStream(file)){AlbumStorage.copy(in,out,check);}
                    if(file.length()!=image.size)throw new IOException("源图片已变化，已停止导出");
                    BitmapFactory.Options bounds=Downloader.dimensions(file);if(bounds.outWidth<=0||bounds.outHeight<=0)throw new IOException("源图片损坏");
                    pages.add(new Core.Page(file,bounds.outWidth,bounds.outHeight));files.add(file);chapters.add(image.chapter);
                    progress.accept("准备图片 "+(++completed)+"/"+album.images.size());
                }
                File output=new File(temporary,names.get(index++));
                if(format.equals("pdf"))Core.writePdf(output,pages,(done,total)->{check.run();progress.accept("生成 PDF "+done+"/"+total);});
                else if(format.equals("images")){
                    if(!output.mkdir())throw new IOException("无法创建导出文件夹");
                    for(int imageIndex=0;imageIndex<images.size();imageIndex++){
                        check.run();AlbumStorage.Image image=images.get(imageIndex);File target=new File(output,AlbumRules.imageName(image.chapter,image.page,chapters.size()));
                        if(!target.getParentFile().isDirectory()&&!target.getParentFile().mkdirs())throw new IOException("无法创建章节目录");
                        Files.copy(files.get(imageIndex).toPath(),target.toPath());progress.accept("保存图片 "+(imageIndex+1)+"/"+images.size());
                    }
                }else{
                    try(ZipOutputStream zip=new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(output)))){
                        zip.setLevel(1);
                        for(int i=0;i<images.size();i++){
                            check.run();AlbumStorage.Image image=images.get(i);zip.putNextEntry(new ZipEntry(Core.zipImageName(flat,chapters.size(),i+1,image.chapter,image.page)));
                            try(InputStream in=new FileInputStream(files.get(i))){AlbumStorage.copy(in,zip,check);}zip.closeEntry();progress.accept("打包图片 "+(i+1)+"/"+images.size());
                        }
                    }
                    try(ZipFile zip=new ZipFile(output)){
                        if(zip.size()!=images.size())throw new IOException("ZIP 文件数量不一致");
                        Enumeration<? extends ZipEntry> entries=zip.entries();while(entries.hasMoreElements()){ZipEntry entry=entries.nextElement();CRC32 crc=new CRC32();try(InputStream in=zip.getInputStream(entry)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){check.run();crc.update(b,0,n);}}if(crc.getValue()!=entry.getCrc())throw new IOException("ZIP 校验失败");}
                    }
                }
                outputs.add(output);
            }
            List<LibraryStore.Entry> result=new ArrayList<>();
            for(File output:outputs){check.run();progress.accept("保存 "+output.getName());Uri uri=AlbumStorage.publish(context,output,tree,output.getName(),check);committed.add(uri);
                if(format.equals("images")){
                    org.json.JSONArray records=new org.json.JSONArray();int chapters=(int)album.images.stream().map(image->image.chapter).distinct().count();
                    for(AlbumStorage.Image image:album.images)records.put(new org.json.JSONObject().put("chapter",image.chapter).put("page",image.page).put("file",AlbumRules.imageName(image.chapter,image.page,chapters)).put("size",image.size));
                    AlbumStorage.remember(context,uri,new org.json.JSONObject().put("version",AlbumRules.LAYOUT_VERSION).put("id",album.id).put("title",album.title).put("entries",records));
                }
                result.add(new LibraryStore.Entry(album.id,output.getName(),uri.toString(),tree,label,format,false));}
            return result;
        }catch(Exception failure){
            for(Uri uri:committed)try{AlbumStorage.remove(context,uri);}catch(Exception cleanup){failure.addSuppressed(cleanup);}
            throw failure;
        }finally{Downloader.deleteOwned(temporary,context.getCacheDir());}
    }
}
