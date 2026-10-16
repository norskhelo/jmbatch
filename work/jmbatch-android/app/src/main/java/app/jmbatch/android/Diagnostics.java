package app.jmbatch.android;

import android.content.Context;
import android.graphics.*;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import java.io.*;
import java.util.*;
import java.util.zip.*;

public final class Diagnostics {
    static final String VECTOR="HwoKLf5mI5eCAmt1zSQBMxSeVAtaes6+B1gnn+PxxGwW/BjFByGuhNemotgHMIeR";
    public static String run(Context context) throws Exception {
        File root=new File(context.getFilesDir(),"self-test");if(!root.exists()&&!root.mkdirs())throw new IOException("无法创建自检目录");
        require(Core.parseIds("JM123456,123456,123457-123460").size()==5,"编号解析");
        require(Core.decrypt(VECTOR,"1700566805",Core.API_SECRET).equals("{\"id\":123456,\"name\":\"offline-test\"}"),"API 解密对照");
        require(Core.segments(220980,1461466,"00001")==14,"图片分段算法");
        Store.Settings configured=new Store.Settings();configured.chapterWorkers=8;
        require(new Store.Settings(configured.json()).chapterWorkers==8,"章节并行设置保存");
        require(new Store.Settings(new org.json.JSONObject()).chapterWorkers==4,"旧配置默认章节并行数");
        Bitmap pattern=Bitmap.createBitmap(160,203,Bitmap.Config.ARGB_8888);
        for(int y=0;y<203;y++)for(int x=0;x<160;x++)pattern.setPixel(x,y,Color.rgb(y,80,160));
        File raw=new File(root,"test.png"),jpeg=new File(root,"test.jpg");
        try(FileOutputStream out=new FileOutputStream(raw)){pattern.compress(Bitmap.CompressFormat.PNG,100,out);}pattern.recycle();
        Downloader.decode(raw,jpeg,8);Bitmap decoded=BitmapFactory.decodeFile(jpeg.getAbsolutePath());require(decoded!=null,"原生图片解码");
        for(int i=0;i<8;i++){int[] strip=Core.strip(203,8,i);int source=strip[0]+strip[2]/2;int target=strip[1]+strip[2]/2;require(Math.abs(Color.red(decoded.getPixel(80,target))-source)<12,"图片条带重排 "+i);}decoded.recycle();
        File pdf=new File(root,"test.pdf");Core.writePdf(pdf,Arrays.asList(new Core.Page(jpeg,160,203),new Core.Page(jpeg,160,203)),(a,b)->{});Downloader.verifyPdf(pdf);
        try(ParcelFileDescriptor descriptor=ParcelFileDescriptor.open(pdf,ParcelFileDescriptor.MODE_READ_ONLY);PdfRenderer renderer=new PdfRenderer(descriptor)){
            require(renderer.getPageCount()==2,"PDF 页数");
            try(PdfRenderer.Page page=renderer.openPage(0)){Bitmap bitmap=Bitmap.createBitmap(160,203,Bitmap.Config.ARGB_8888);page.render(bitmap,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);require(Color.alpha(bitmap.getPixel(80,100))>0,"PDF 可渲染");bitmap.recycle();}
        }
        File zip=new File(root,"test.zip");try(ZipOutputStream out=new ZipOutputStream(new FileOutputStream(zip))){out.putNextEntry(new ZipEntry("0001/00001.jpg"));try(InputStream in=new FileInputStream(jpeg)){Core.copy(in,out);}out.closeEntry();}
        try(ZipFile archive=new ZipFile(zip)){require(archive.size()==1,"ZIP 导出");}
        // On-device coverage of clean publication, private indices and offline export.
        File albumStage=new File(root,"album-stage-"+UUID.randomUUID());albumStage.mkdirs();
        org.json.JSONArray images=new org.json.JSONArray();
        for(int chapter=1;chapter<=2;chapter++){
            String relative=AlbumRules.imageName(chapter,1);File image=new File(albumStage,relative);image.getParentFile().mkdirs();java.nio.file.Files.copy(jpeg.toPath(),image.toPath());
            images.put(new org.json.JSONObject().put("chapter",chapter).put("page",1).put("file",relative).put("size",image.length()));
        }
        android.net.Uri albumUri=null;List<LibraryStore.Entry> exported=new ArrayList<>();
        try{
            List<FolderSave.Entry> ordered=new ArrayList<>();
            for(int i=0;i<images.length();i++){org.json.JSONObject image=images.getJSONObject(i);ordered.add(new FolderSave.Entry(new File(albumStage,image.getString("file")),image.getString("file"),image.getLong("size")));}
            Set<String> savePhases=new HashSet<>();
            albumUri=AlbumStorage.publishImages(context,ordered,"","JM123456-self-test-"+UUID.randomUUID().toString().substring(0,8),()->{},(phase,done,total,bytes,totalBytes)->savePhases.add(phase));
            require(savePhases.contains("save")&&savePhases.contains("saved_verify"),"图片保存和读回校验进度");
            require(AlbumStorage.load(context,albumUri).images.size()==2,"无清单目录扫描");
            AlbumStorage.remember(context,albumUri,new org.json.JSONObject().put("version",AlbumRules.LAYOUT_VERSION).put("id","123456").put("title","offline-album-test").put("entries",images));
            require(AlbumStorage.children(context,albumUri).size()==2,"图片目录不含清单");
            require(AlbumStorage.load(context,albumUri).images.size()==2,"图片目录保存和读取");
            exported.addAll(AlbumExporter.export(context,albumUri,"","自检","pdf",false,false,true,()->{},message->{}));
            require(exported.size()==2,"分章节 PDF 文件数");
            for(LibraryStore.Entry entry:exported){File file=AlbumStorage.local(context,android.net.Uri.parse(entry.uri));try(ParcelFileDescriptor fd=ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);PdfRenderer renderer=new PdfRenderer(fd)){require(renderer.getPageCount()==1,"分章 PDF 页数");}}
            exported.addAll(AlbumExporter.export(context,albumUri,"","自检","zip",false,true,false,()->{},message->{}));
            File zipResult=AlbumStorage.local(context,android.net.Uri.parse(exported.get(exported.size()-1).uri));
            try(ZipFile archive=new ZipFile(zipResult)){require(archive.size()==2&&archive.getEntry("0002/00001.jpg")!=null,"多章节 ZIP 顺序");}
            require(AlbumStorage.load(context,albumUri).images.size()==2,"导出保留原始图片");
            List<LibraryStore.Entry> sources=new ArrayList<>();
            sources.add(exported.get(exported.size()-1));
            List<LibraryStore.Entry> merged=AlbumExporter.export(context,albumUri,"","自检","pdf",false,false,false,()->{},message->{});exported.addAll(merged);sources.add(merged.get(0));
            for(LibraryStore.Entry source:sources)for(String format:new String[]{"images",source.format.equals("zip")?"pdf":"zip"}){
                List<LibraryStore.Entry> converted=AlbumExporter.export(context,android.net.Uri.parse(source.uri),source.format,source.id,source.title,"","自检",format,false,false,false,()->{},message->{});exported.addAll(converted);
                require(converted.size()==1,"互转成品数 "+source.format+" -> "+format);
                android.net.Uri convertedUri=android.net.Uri.parse(converted.get(0).uri);
                if(format.equals("images")){require(AlbumStorage.load(context,convertedUri).images.size()==2,"互转文件夹页数");AlbumStorage.validateForDeletion(context,convertedUri);}
                else if(format.equals("pdf")){try(ParcelFileDescriptor fd=ParcelFileDescriptor.open(AlbumStorage.local(context,convertedUri),ParcelFileDescriptor.MODE_READ_ONLY);PdfRenderer renderer=new PdfRenderer(fd)){require(renderer.getPageCount()==2,"ZIP 转 PDF 页数");}}
                else try(ZipFile convertedZip=new ZipFile(AlbumStorage.local(context,convertedUri))){require(convertedZip.size()==2&&convertedZip.getEntry("00001.jpg")!=null,"PDF 转 ZIP 页数和布局");}
                require(AlbumStorage.local(context,android.net.Uri.parse(source.uri)).isFile(),"互转保留源文件");
            }
            AlbumStorage.validateForDeletion(context,albumUri);
        }finally{
            for(LibraryStore.Entry entry:exported)AlbumStorage.remove(context,android.net.Uri.parse(entry.uri));
            if(albumUri!=null)AlbumStorage.remove(context,albumUri);
            Downloader.deleteOwned(albumStage,root);
        }
        File singleStage=new File(root,"single-stage-"+UUID.randomUUID());singleStage.mkdirs();android.net.Uri singleUri=null;
        exported.clear();
        try{
            java.nio.file.Files.copy(jpeg.toPath(),new File(singleStage,"00001.jpg").toPath());
            singleUri=AlbumStorage.publish(context,singleStage,"","JM123457-single-test-"+UUID.randomUUID().toString().substring(0,8),()->{});
            require(AlbumStorage.children(context,singleUri).size()==1&&AlbumStorage.load(context,singleUri).images.size()==1,"单章节无清单图片平铺和扫描");
            for(boolean flat:new boolean[]{false,true}){
                List<LibraryStore.Entry> files=AlbumExporter.export(context,singleUri,"","自检","zip",false,flat,false,()->{},message->{});exported.addAll(files);
                try(ZipFile archive=new ZipFile(AlbumStorage.local(context,android.net.Uri.parse(files.get(0).uri)))){require(archive.size()==1&&archive.getEntry("00001.jpg")!=null,"单章节 ZIP 仅含平铺图片");}
            }
            AlbumStorage.validateForDeletion(context,singleUri);
        }finally{
            for(LibraryStore.Entry entry:exported)AlbumStorage.remove(context,android.net.Uri.parse(entry.uri));
            if(singleUri!=null)AlbumStorage.remove(context,singleUri);Downloader.deleteOwned(singleStage,root);
        }
        String report="离线自检通过\n\n编号与区间解析、API 解密对照、图片分段和重排、JPEG 保存、PDF 系统渲染、排序图片目录保存、分章节 PDF、PDF / ZIP / 文件夹六向互转和源文件保留均通过。\n\n没有请求漫画网站；不代表真实网络和账号访问已经验证。";
        Downloader.writeTextAtomic(new File(root,"report.txt"),report);return report;
    }
    private static void require(boolean condition,String name)throws IOException{if(!condition)throw new IOException("自检未通过："+name);}
}
