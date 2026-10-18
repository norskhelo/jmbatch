package app.jmbatch.android;

import android.content.Context;
import android.database.Cursor;
import android.graphics.*;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import java.io.*;
import java.util.zip.*;

/** Local first-page previews only; never writes into a user's manga directory. */
public final class LibraryCover {
    private static CoverDiskCache cache(Context context){return new CoverDiskCache(new File(context.getFilesDir(),"covers"));}
    private static String key(LibraryStore.Entry entry){return entry.format+"\n"+entry.uri;}
    private static String stamp(Context context,String address)throws Exception {
        Uri uri=Uri.parse(address);File file=AlbumStorage.local(context,uri);
        if(file!=null){if(!file.exists())throw new FileNotFoundException();return file.lastModified()+"|"+file.length();}
        try(Cursor cursor=context.getContentResolver().query(uri,new String[]{DocumentsContract.Document.COLUMN_LAST_MODIFIED,DocumentsContract.Document.COLUMN_SIZE},null,null,null)){
            if(cursor==null||!cursor.moveToFirst())throw new FileNotFoundException();
            return (cursor.isNull(0)?-1:cursor.getLong(0))+"|"+(cursor.isNull(1)?-1:cursor.getLong(1));
        }
    }
    private static CoverDiskCache.Value encoded(Bitmap image,String dependency,String version)throws IOException {
        if(image==null)return null;
        try{ByteArrayOutputStream out=new ByteArrayOutputStream();
            if(!image.compress(Bitmap.CompressFormat.PNG,100,out))throw new IOException("封面无法保存");
            return new CoverDiskCache.Value(out.toByteArray(),dependency,version);
        }finally{image.recycle();}
    }
    /** The optional first page avoids reopening a large just-finished PDF/ZIP. */
    public static void remember(Context context,String uri,String format,File first,Uri savedFirst){
        LibraryStore.Entry entry=new LibraryStore.Entry("","",uri,"","",format,false);
        try{cache(context).get(key(entry),uri,address->stamp(context,address),()->{
            String dependency=savedFirst==null?"":savedFirst.toString();
            String version=dependency.isEmpty()?"":stamp(context,dependency);
            return encoded(loadImage(first),dependency,version);
        });}catch(Exception|OutOfMemoryError ignored){}
    }
    public static Bitmap load(Context context,LibraryStore.Entry entry){
        CoverDiskCache cache=cache(context);
        try{
            for(int attempt=0;attempt<2;attempt++){
                byte[] data=cache.get(key(entry),entry.uri,address->stamp(context,address),()->{
                    if(entry.format.equals("images")){
                        AlbumStorage.Image first=AlbumStorage.load(context,Uri.parse(entry.uri)).images.get(0);
                        String version=stamp(context,first.uri.toString());
                        if(first.size>CoverRules.MAX_IMAGE_BYTES)return null;
                        try(InputStream stream=AlbumStorage.open(context,first.uri)){return encoded(decode(stream),first.uri.toString(),version);}
                    }
                    return encoded(loadOriginal(context,entry),"","");
                });
                if(data==null)return null;
                try{return decode(new ByteArrayInputStream(data));}
                catch(Exception error){cache.forget(key(entry));}
            }
        }catch(Exception|OutOfMemoryError ignored){return loadOriginal(context,entry);}
        return null;
    }
    public static void forget(Context context,LibraryStore.Entry entry){cache(context).forget(key(entry));}
    public static Bitmap loadImage(File file){
        if(file.length()>CoverRules.MAX_IMAGE_BYTES)return null;
        try(InputStream stream=new FileInputStream(file)){return decode(stream);}
        catch(Exception|OutOfMemoryError ignored){return null;}
    }
    private static Bitmap decode(InputStream stream)throws IOException {
        byte[] data=CoverRules.readImage(stream);BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;
        BitmapFactory.decodeByteArray(data,0,data.length,options);options.inSampleSize=CoverRules.sampleSize(options.outWidth,options.outHeight);options.inJustDecodeBounds=false;
        Bitmap source=BitmapFactory.decodeByteArray(data,0,data.length,options);if(source==null)throw new IOException("封面无法解码");
        double scale=Math.min(1,Math.min(192.0/source.getWidth(),256.0/source.getHeight()));
        Bitmap result=Bitmap.createScaledBitmap(source,Math.max(1,(int)(source.getWidth()*scale)),Math.max(1,(int)(source.getHeight()*scale)),true);
        if(result!=source)source.recycle();return result;
    }
    private static Bitmap loadOriginal(Context context,LibraryStore.Entry entry){
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
