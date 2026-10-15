package app.jmbatch.android;

import android.content.Context;
import android.graphics.*;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.*;
import java.util.zip.*;

/** Local first-page previews only; never writes into a user's manga directory. */
public final class LibraryCover {
    private static Bitmap decode(InputStream stream)throws IOException {
        byte[] data=CoverRules.readImage(stream);BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;
        BitmapFactory.decodeByteArray(data,0,data.length,options);options.inSampleSize=CoverRules.sampleSize(options.outWidth,options.outHeight);options.inJustDecodeBounds=false;
        Bitmap source=BitmapFactory.decodeByteArray(data,0,data.length,options);if(source==null)throw new IOException("封面无法解码");
        double scale=Math.min(1,Math.min(192.0/source.getWidth(),256.0/source.getHeight()));
        Bitmap result=Bitmap.createScaledBitmap(source,Math.max(1,(int)(source.getWidth()*scale)),Math.max(1,(int)(source.getHeight()*scale)),true);
        if(result!=source)source.recycle();return result;
    }
    public static Bitmap load(Context context,LibraryStore.Entry entry){
        try{
            if(Thread.currentThread().isInterrupted())return null;
            Uri uri=Uri.parse(entry.uri);
            if(entry.format.equals("images")){
                AlbumStorage.Image first=AlbumStorage.load(context,uri).images.get(0);
                if(first.size>CoverRules.MAX_IMAGE_BYTES)return null;
                try(InputStream stream=AlbumStorage.open(context,first.uri)){return decode(stream);}
            }
            if(entry.format.equals("pdf")){
                try(ParcelFileDescriptor fd=context.getContentResolver().openFileDescriptor(uri,"r")){
                    if(fd==null)return null;
                    try(PdfRenderer renderer=new PdfRenderer(fd);PdfRenderer.Page page=renderer.openPage(0)){
                        double scale=Math.min(192.0/page.getWidth(),256.0/page.getHeight());
                        Bitmap image=Bitmap.createBitmap(Math.max(1,(int)(page.getWidth()*scale)),Math.max(1,(int)(page.getHeight()*scale)),Bitmap.Config.ARGB_8888);
                        image.eraseColor(Color.WHITE);page.render(image,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);return image;
                    }
                }
            }
            if(entry.format.equals("zip")){
                File source=AlbumStorage.local(context,uri),temporary=null;
                try{
                    if(source==null){
                        temporary=File.createTempFile("library-cover-",".zip",context.getCacheDir());source=temporary;
                        try(InputStream in=AlbumStorage.open(context,uri);OutputStream out=new FileOutputStream(source)){
                            byte[] bytes=new byte[65536];long size=0;int n;
                            while((n=in.read(bytes))!=-1){if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();size+=n;if(size>512L*1024*1024)throw new IOException("预览文件过大");out.write(bytes,0,n);}
                        }
                    }
                    try(ZipFile zip=new ZipFile(source);InputStream in=zip.getInputStream(CoverRules.firstImage(zip))){return decode(in);}
                }finally{if(temporary!=null)temporary.delete();}
            }
        }catch(Exception|OutOfMemoryError ignored){ /* A broken preview never disables library actions. */ }
        return null;
    }
}
