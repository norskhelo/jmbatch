package app.jmbatch.android;

import android.content.Context;
import android.graphics.*;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.*;
import java.util.*;
import java.util.zip.*;

/** One worker owns all open handles. ZIPs and PDFs are rendered page by page. */
public final class ReaderSource implements AutoCloseable {
    private final Context context;
    private AlbumStorage.Album album;
    private ZipFile zip;
    private List<ArchivePages.Page> archive;
    private PdfRenderer pdf;
    private ParcelFileDescriptor descriptor;
    private File temporary;
    public int[] chapters,pageNumbers;
    public ReaderSource(Context context,LibraryStore.Entry entry,AlbumStorage.Check cancelled)throws Exception {
        this.context=context;
        try{
            Uri uri=Uri.parse(entry.uri);cancelled.run();
            if(entry.format.equals("images")){
                album=AlbumStorage.load(context,uri);chapters=new int[album.images.size()];pageNumbers=new int[chapters.length];
                for(int i=0;i<chapters.length;i++){chapters[i]=album.images.get(i).chapter;pageNumbers[i]=album.images.get(i).page;}
            }else if(entry.format.equals("zip")){
                File input=AlbumStorage.local(context,uri);
                if(input==null)input=copy(uri,".zip",cancelled);
                zip=new ZipFile(input);archive=ArchivePages.read(zip);chapters=new int[archive.size()];pageNumbers=new int[chapters.length];
                for(int i=0;i<chapters.length;i++){chapters[i]=archive.get(i).chapter;pageNumbers[i]=archive.get(i).page;}
            }else if(entry.format.equals("pdf")){
                try{
                    descriptor=context.getContentResolver().openFileDescriptor(uri,"r");
                    if(descriptor==null)throw new IOException("PDF 无法读取");
                    pdf=new PdfRenderer(descriptor);
                }catch(Exception failure){
                    if(descriptor!=null){descriptor.close();descriptor=null;}
                    File input=copy(uri,".pdf",cancelled);descriptor=ParcelFileDescriptor.open(input,ParcelFileDescriptor.MODE_READ_ONLY);pdf=new PdfRenderer(descriptor);
                }
                int total=pdf.getPageCount();if(total<1||total>ArchivePages.MAX_PAGES)throw new IOException("PDF 页数超出支持范围");
                chapters=new int[total];pageNumbers=new int[total];Arrays.fill(chapters,1);for(int i=0;i<total;i++)pageNumbers[i]=i+1;
            }else throw new IOException("请选择图片文件夹、ZIP 或 PDF");
            if(chapters.length<1||chapters.length>ArchivePages.MAX_PAGES)throw new IOException("漫画为空或超过 20000 页");
            cancelled.run();
        }catch(Exception|OutOfMemoryError failure){close();throw failure;}
    }
    private File copy(Uri uri,String suffix,AlbumStorage.Check cancelled)throws Exception {
        temporary=File.createTempFile("reader-",suffix,context.getCacheDir());
        try(InputStream input=AlbumStorage.open(context,uri);OutputStream output=new FileOutputStream(temporary)){
            byte[] buffer=new byte[65536];long total=0;int count;
            while((count=input.read(buffer))!=-1){cancelled.run();total+=count;if(total>ArchivePages.MAX_TOTAL_BYTES)throw new IOException("阅读文件超过 8 GB");output.write(buffer,0,count);}
        }
        return temporary;
    }
    private InputStream image(int index)throws IOException {
        long size=zip!=null?archive.get(index).entry.getSize():album.images.get(index).size;
        if(size>ArchivePages.MAX_IMAGE_BYTES)throw new IOException("图片文件过大");
        InputStream stream=zip!=null?zip.getInputStream(archive.get(index).entry):AlbumStorage.open(context,album.images.get(index).uri);
        return new BufferedInputStream(stream);
    }
    public Bitmap render(int index,int width,int height)throws Exception {
        if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();
        if(pdf!=null){
            try(PdfRenderer.Page page=pdf.openPage(index)){
                int[] size=ReaderRules.size(page.getWidth(),page.getHeight(),width,height);
                Bitmap bitmap=Bitmap.createBitmap(size[0],size[1],Bitmap.Config.ARGB_8888);bitmap.eraseColor(Color.WHITE);
                try{page.render(bitmap,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);return bitmap;}catch(Exception e){bitmap.recycle();throw e;}
            }
        }
        BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;
        try(InputStream stream=image(index)){BitmapFactory.decodeStream(stream,null,options);}
        int[] size=ReaderRules.size(options.outWidth,options.outHeight,width,height);
        options.inSampleSize=ReaderRules.sample(options.outWidth,options.outHeight,size);options.inJustDecodeBounds=false;
        Bitmap source;try(InputStream stream=image(index)){source=BitmapFactory.decodeStream(stream,null,options);}
        if(source==null)throw new IOException("图片无法解码");
        try{Bitmap result=Bitmap.createScaledBitmap(source,size[0],size[1],true);if(result!=source)source.recycle();return result;}catch(Exception|OutOfMemoryError error){source.recycle();throw error;}
    }
    public void close(){
        if(zip!=null){try{zip.close();}catch(Exception ignored){}zip=null;}
        if(pdf!=null){try{pdf.close();}catch(Exception ignored){}pdf=null;}
        if(descriptor!=null){try{descriptor.close();}catch(Exception ignored){}descriptor=null;}
        if(temporary!=null){temporary.delete();temporary=null;}
    }
}
