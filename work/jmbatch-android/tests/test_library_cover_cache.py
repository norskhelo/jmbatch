"""Exercise production cover loading with host image codecs and storage doubles.

This verifies cache wiring and I/O reuse, not Android Bitmap/PDF/SAF performance.
"""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
jdk, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
stubs = {
    'android/net/Uri.java': '''package android.net;
public class Uri {final String value;private Uri(String v){value=v;}public static Uri parse(String s){return new Uri(s);}public String toString(){return value;}}''',
    'android/database/Cursor.java': '''package android.database;
public class Cursor implements AutoCloseable {final java.io.File file;public Cursor(java.io.File f){file=f;}
public boolean moveToFirst(){return file.exists();}public boolean isNull(int i){return false;}public long getLong(int i){return i==0?file.lastModified():file.length();}public void close(){}}''',
    'android/content/Context.java': '''package android.content;
public class Context {final java.io.File root;public Context(java.io.File f){root=f;root.mkdirs();}
public java.io.File getFilesDir(){return root;}public java.io.File getCacheDir(){return root;}
public ContentResolver getContentResolver(){return new ContentResolver();}}''',
    'android/content/ContentResolver.java': '''package android.content;
public class ContentResolver {
public android.database.Cursor query(android.net.Uri uri,String[] p,String s,String[] a,String o){return new android.database.Cursor(app.jmbatch.android.AlbumStorage.file(uri));}
public android.os.ParcelFileDescriptor openFileDescriptor(android.net.Uri uri,String mode){return new android.os.ParcelFileDescriptor();}}''',
    'android/provider/DocumentsContract.java': '''package android.provider;
public class DocumentsContract {public static class Document {public static final String COLUMN_LAST_MODIFIED="modified",COLUMN_SIZE="size";}}''',
    'android/os/ParcelFileDescriptor.java': '''package android.os;
public class ParcelFileDescriptor implements AutoCloseable {public void close(){}}''',
    'android/graphics/Color.java': '''package android.graphics;public class Color {public static final int WHITE=-1;}''',
    'android/graphics/Bitmap.java': '''package android.graphics;
public class Bitmap {public final java.awt.image.BufferedImage image;public Bitmap(java.awt.image.BufferedImage i){image=i;}
public enum CompressFormat {PNG,JPEG}public enum Config {ARGB_8888}
public int getWidth(){return image.getWidth();}public int getHeight(){return image.getHeight();}public void recycle(){}
public boolean compress(CompressFormat f,int q,java.io.OutputStream out){try{return javax.imageio.ImageIO.write(image,f==CompressFormat.PNG?"png":"jpg",out);}catch(java.io.IOException e){return false;}}
public static Bitmap createScaledBitmap(Bitmap src,int w,int h,boolean filter){java.awt.image.BufferedImage b=new java.awt.image.BufferedImage(w,h,java.awt.image.BufferedImage.TYPE_INT_RGB);java.awt.Graphics2D g=b.createGraphics();g.drawImage(src.image,0,0,w,h,null);g.dispose();return new Bitmap(b);}
public static Bitmap createBitmap(int w,int h,Config config){return new Bitmap(new java.awt.image.BufferedImage(w,h,java.awt.image.BufferedImage.TYPE_INT_RGB));}
public void eraseColor(int color){} }''',
    'android/graphics/BitmapFactory.java': '''package android.graphics;
public class BitmapFactory {public static class Options {public boolean inJustDecodeBounds;public int outWidth,outHeight,inSampleSize;}
public static Bitmap decodeByteArray(byte[] data,int offset,int size,Options options){try{java.awt.image.BufferedImage b=javax.imageio.ImageIO.read(new java.io.ByteArrayInputStream(data,offset,size));if(b==null)return null;options.outWidth=b.getWidth();options.outHeight=b.getHeight();return options.inJustDecodeBounds?null:new Bitmap(b);}catch(Exception e){return null;}}}''',
    'android/graphics/pdf/PdfRenderer.java': '''package android.graphics.pdf;
public class PdfRenderer implements AutoCloseable {public static int opens;
public PdfRenderer(android.os.ParcelFileDescriptor fd)throws java.io.IOException {opens++;throw new java.io.IOException("Host PDF renderer unavailable");}
public Page openPage(int n){return new Page();}public void close(){}
public static class Page implements AutoCloseable {public static final int RENDER_MODE_FOR_DISPLAY=1;public int getWidth(){return 600;}public int getHeight(){return 800;}public void render(android.graphics.Bitmap b,Object a,Object c,int mode){}public void close(){}}}''',
    'app/jmbatch/android/LibraryStore.java': '''package app.jmbatch.android;
public class LibraryStore {public static class Entry {public final String uri,format;public Entry(String i,String t,String u,String tr,String l,String f,boolean fav){uri=u;format=f;}}}''',
    'app/jmbatch/android/AlbumStorage.java': '''package app.jmbatch.android;
import java.io.*;import android.net.Uri;import android.content.Context;
public class AlbumStorage {public static int scans,opens;
public static File file(Uri u){String s=u.toString();return new File(s.startsWith("external:")?s.substring(9):s);}
public static File local(Context c,Uri u){return u.toString().startsWith("external:")?null:file(u);}
public static InputStream open(Context c,Uri u)throws IOException {opens++;return new FileInputStream(file(u));}
public static class Image {public final Uri uri;public final long size;Image(File f){uri=Uri.parse(f.toString());size=f.length();}}
public static class Album {public final java.util.List<Image> images=new java.util.ArrayList<>();}
public static Album load(Context c,Uri u){scans++;Album a=new Album();a.images.add(new Image(new File(file(u),"first.png")));return a;}}''',
}
sources = []
for name, source in stubs.items():
    file = out / 'stubs' / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(source, encoding='utf-8')
    sources.append(file)
program = out / 'LibraryCoverCacheTest.java'
program.write_text('''import app.jmbatch.android.*;
import android.content.Context;import android.net.Uri;import android.graphics.Bitmap;
import java.io.*;import java.nio.file.*;import java.util.zip.*;
public class LibraryCoverCacheTest {
static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("Cover integration "+checks);}
static LibraryStore.Entry entry(String uri,String format){return new LibraryStore.Entry("","",uri,"","",format,false);}
static void page(File file,int color)throws Exception {file.getParentFile().mkdirs();java.awt.image.BufferedImage b=new java.awt.image.BufferedImage(600,800,java.awt.image.BufferedImage.TYPE_INT_RGB);java.awt.Graphics2D g=b.createGraphics();g.setColor(new java.awt.Color(color));g.fillRect(0,0,600,800);g.dispose();javax.imageio.ImageIO.write(b,"png",file);}
public static void main(String[] args)throws Exception {
File root=new File(args[0]);root.mkdirs();File home=new File(root,"home"),first=new File(root,"first.png"),zip=new File(root,"comic.zip");page(first,0xff0000);
try(ZipOutputStream out=new ZipOutputStream(new FileOutputStream(zip))){out.putNextEntry(new ZipEntry("00001.png"));Files.copy(first.toPath(),out);out.closeEntry();}
Context context=new Context(home);String address="external:"+zip;
check(LibraryCover.load(context,entry(address,"zip"))!=null);check(AlbumStorage.opens==1);
for(int i=0;i<3;i++)check(LibraryCover.load(new Context(home),entry(address,"zip"))!=null);
check(AlbumStorage.opens==1);check(home.listFiles((d,n)->n.startsWith("library-cover-")).length==0);
File cached=new File(home,"covers").listFiles()[0];Files.write(cached.toPath(),new byte[]{0});
check(LibraryCover.load(context,entry(address,"zip"))!=null);check(AlbumStorage.opens==2);
long old=zip.lastModified();check(zip.setLastModified(old+2000));
check(LibraryCover.load(context,entry(address,"zip"))!=null);check(AlbumStorage.opens==3);
check(zip.delete());check(LibraryCover.load(context,entry(address,"zip"))==null);
// Prewarming PDF/ZIP uses the downloaded first page, never the finished archive.
for(String format:new String[]{"pdf","zip"}){
File finished=new File(root,"finished."+format);Files.write(finished.toPath(),new byte[]{0});
LibraryCover.remember(context,"external:"+finished,format,first,null);
check(LibraryCover.load(new Context(home),entry("external:"+finished,format))!=null);
}
check(android.graphics.pdf.PdfRenderer.opens==0);
File folder=new File(root,"album"),saved=new File(folder,"first.png");page(saved,0xff0000);
LibraryCover.remember(context,folder.toString(),"images",first,Uri.parse(saved.toString()));
check(LibraryCover.load(context,entry(folder.toString(),"images"))!=null);check(AlbumStorage.scans==0);
old=saved.lastModified();page(saved,0x0000ff);check(saved.setLastModified(old+2000));
Bitmap changed=LibraryCover.load(context,entry(folder.toString(),"images"));
check((changed.image.getRGB(0,0)&0xffffff)==0x0000ff);check(AlbumStorage.scans==1);
check(LibraryCover.load(new Context(home),entry(folder.toString(),"images"))!=null);check(AlbumStorage.scans==1);
LibraryCover.forget(context,entry(folder.toString(),"images"));
check(LibraryCover.load(context,entry(folder.toString(),"images"))!=null);check(AlbumStorage.scans==2);
System.out.println("Library cover integration: "+checks+" checks passed (host codecs/storage)");
}}''', encoding='utf-8')
production = root / 'app/src/main/java/app/jmbatch/android'
sources += [production / name for name in ('CoverRules.java', 'CoverDiskCache.java', 'LibraryCover.java')]
subprocess.run([str(jdk/'bin/javac.exe'), '-encoding', 'UTF-8', '-d', str(out), *map(str, sources), str(program)], check=True)
subprocess.run([str(jdk/'bin/java.exe'), '-Djava.awt.headless=true', '-cp', str(out), 'LibraryCoverCacheTest', str(out/'data')], check=True)
