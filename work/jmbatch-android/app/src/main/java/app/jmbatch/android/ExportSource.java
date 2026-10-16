package app.jmbatch.android;

import android.content.Context;
import android.graphics.*;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.*;
import java.util.*;
import java.util.zip.*;

public final class ExportSource {
    public static AlbumStorage.Album load(Context context,Uri source,String format,String id,String title,File temporary,AlbumStorage.Check check,java.util.function.Consumer<String> progress)throws Exception {
        check.run();if(format.equals("images"))return AlbumStorage.load(context,source);
        if(!format.equals("pdf")&&!format.equals("zip"))throw new IOException("请选择 PDF、ZIP 或图片文件夹");
        File input=new File(temporary,"source."+format);
        try(InputStream stream=AlbumStorage.open(context,source);OutputStream output=new FileOutputStream(input)){copyLimited(stream,output,ArchivePages.MAX_TOTAL_BYTES,check);}
        List<AlbumStorage.Image> images=new ArrayList<>();
        if(format.equals("zip")){
            try(ZipFile zip=new ZipFile(input)){
                List<ArchivePages.Page> pages=ArchivePages.read(zip);int index=0;
                for(ArchivePages.Page page:pages){
                    check.run();progress.accept("读取 ZIP 图片 "+(++index)+"/"+pages.size());File raw=new File(temporary,"source-image"),target=new File(temporary,"page-"+index+".jpg");
                    CRC32 crc=new CRC32();try(InputStream stream=new CheckedInputStream(zip.getInputStream(page.entry),crc);OutputStream output=new FileOutputStream(raw)){copyLimited(stream,output,ArchivePages.MAX_IMAGE_BYTES,check);}
                    if(crc.getValue()!=page.entry.getCrc()||raw.length()!=page.entry.getSize())throw new IOException("ZIP 图片校验失败");
                    BitmapFactory.Options bounds=Downloader.dimensions(raw);
                    if(bounds.outWidth<=0||bounds.outHeight<=0)throw new IOException("ZIP 图片损坏");
                    if("image/jpeg".equals(bounds.outMimeType))java.nio.file.Files.move(raw.toPath(),target.toPath());
                    else{
                        if((long)bounds.outWidth*bounds.outHeight>16000000L)throw new IOException("非 JPEG 图片尺寸过大，请先转换为 JPEG");
                        Bitmap bitmap=BitmapFactory.decodeFile(raw.getAbsolutePath());if(bitmap==null)throw new IOException("ZIP 图片损坏");
                        try{save(bitmap,target);}finally{bitmap.recycle();}
                    }
                    images.add(new AlbumStorage.Image(page.chapter,page.page,Uri.fromFile(target),target.length(),target.getName()));
                }
            }
        }else{
            try(ParcelFileDescriptor descriptor=ParcelFileDescriptor.open(input,ParcelFileDescriptor.MODE_READ_ONLY);PdfRenderer renderer=new PdfRenderer(descriptor)){
                int count=renderer.getPageCount();if(count<1||count>ArchivePages.MAX_PAGES)throw new IOException("PDF 页数超出支持范围");long total=0;
                for(int index=0;index<count;index++){
                    check.run();progress.accept("渲染 PDF 页面 "+(index+1)+"/"+count);File target=new File(temporary,"page-"+(index+1)+".jpg");
                    try(PdfRenderer.Page page=renderer.openPage(index)){
                        double width=page.getWidth(),height=page.getHeight();if(width<=0||height<=0)throw new IOException("PDF 页面尺寸无效");
                        double scale=Math.min(2.0,Math.min(8192.0/Math.max(width,height),Math.sqrt(16000000.0/(width*height))));
                        Bitmap bitmap=Bitmap.createBitmap(Math.max(1,(int)(width*scale)),Math.max(1,(int)(height*scale)),Bitmap.Config.ARGB_8888);
                        try{bitmap.eraseColor(Color.WHITE);page.render(bitmap,null,null,PdfRenderer.Page.RENDER_MODE_FOR_PRINT);check.run();save(bitmap,target);}finally{bitmap.recycle();}
                    }
                    total+=target.length();if(total>ArchivePages.MAX_TOTAL_BYTES)throw new IOException("PDF 转换后的图片总大小超出限制");
                    images.add(new AlbumStorage.Image(1,index+1,Uri.fromFile(target),target.length(),target.getName()));
                }
            }
        }
        check.run();return new AlbumStorage.Album(id.matches("[0-9]{1,10}")?id:"0",title,images);
    }
    private static void save(Bitmap bitmap,File target)throws IOException {
        try(FileOutputStream output=new FileOutputStream(target)){if(!bitmap.compress(Bitmap.CompressFormat.JPEG,95,output))throw new IOException("无法保存图片");output.getFD().sync();}
    }
    private static void copyLimited(InputStream input,OutputStream output,long limit,AlbumStorage.Check check)throws Exception {
        byte[] buffer=new byte[65536];int count;long total=0;while((count=input.read(buffer))!=-1){check.run();total+=count;if(total>limit)throw new IOException("源文件或图片大小超出限制");output.write(buffer,0,count);}
    }
}
