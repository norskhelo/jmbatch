package app.jmbatch.android;

import android.content.Context;
import android.graphics.BitmapFactory;
import android.net.Uri;
import java.io.*;
import java.nio.file.Files;
import java.security.*;
import java.util.*;
import java.util.regex.*;
import java.util.zip.*;
import org.json.*;

/** Reads the original JPEG bytes when rebuilding a downloaded album. */
final class MergePages {
    private final Context context;
    private final File temporary;
    private final AlbumStorage.Check check;
    final List<AlbumStorage.Image> pages=new ArrayList<>();
    private long size;
    int groups;

    MergePages(Context context,File temporary,AlbumStorage.Check check){
        this.context=context;this.temporary=temporary;this.check=check;
    }
    void append(List<AlbumStorage.Image> images)throws Exception {
        int previous=-1,page=0;
        for(AlbumStorage.Image image:images){
            check.run();
            if(image.chapter!=previous){groups++;page=0;previous=image.chapter;}
            size=Math.addExact(size,image.size);
            if(image.size<=0||image.size>ArchivePages.MAX_IMAGE_BYTES||size>ArchivePages.MAX_TOTAL_BYTES||pages.size()>=ArchivePages.MAX_PAGES)
                throw new IOException("合并后超过漫画大小或页数上限");
            pages.add(new AlbumStorage.Image(groups,++page,image.uri,image.size,image.file));
        }
    }
    String read(LibraryStore.Entry book)throws Exception {
        Uri uri=Uri.parse(book.uri);
        if(book.format.equals("images")){
            AlbumStorage.Album album=inspect(book);
            append(album.images);
            return stamp(album);
        }
        File directory=Files.createTempDirectory(temporary.toPath(),"source-").toFile();
        File source=new File(directory,"source."+book.format);
        String digest;
        try(OutputStream output=new BufferedOutputStream(new FileOutputStream(source))){digest=digest(uri,output);}
        if(book.format.equals("pdf"))append(pdfImages(source,directory,digest));
        else append(zipImages(source,directory));
        return digest;
    }
    private AlbumStorage.Album inspect(LibraryStore.Entry book)throws Exception {
        return AlbumStorage.inspectForDeletion(context,Uri.parse(book.uri),check::run,(phase,done,total,bytes,totalBytes)->{});
    }
    private static String stamp(AlbumStorage.Album album)throws NoSuchAlgorithmException {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        for(AlbumStorage.Image p:album.images){
            String row=p.chapter+"/"+p.page+":"+p.uri+":"+p.size+":"+p.modified+"\n";
            digest.update(row.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        return android.util.Base64.encodeToString(digest.digest(),android.util.Base64.NO_WRAP);
    }
    void unchanged(LibraryStore.Entry book,String expected)throws Exception {
        check.run();
        String actual=book.format.equals("images")?stamp(inspect(book)):digest(Uri.parse(book.uri),null);
        if(!expected.equals(actual))throw new IOException("源漫画在合并期间发生变化，请重试");
    }
    private InputStream open(Uri uri)throws IOException {
        if("file".equals(uri.getScheme()))return new FileInputStream(new File(uri.getPath()));
        return AlbumStorage.open(context,uri);
    }
    private String digest(Uri uri,OutputStream output)throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream in=open(uri)){
            byte[] buffer=new byte[65536];int n;long total=0;
            while((n=in.read(buffer))!=-1){check.run();total+=n;if(total>ArchivePages.MAX_TOTAL_BYTES)throw new IOException("源文件超过 8 GB");
                digest.update(buffer,0,n);if(output!=null)output.write(buffer,0,n);}
        }
        return android.util.Base64.encodeToString(digest.digest(),android.util.Base64.NO_WRAP);
    }
    private List<AlbumStorage.Image> zipImages(File source,File directory)throws Exception {
        List<AlbumStorage.Image> result=new ArrayList<>();
        try(ZipFile zip=new ZipFile(source)){
            List<ArchivePages.Page> images=ArchivePages.read(zip);
            int regular=0;
            for(Enumeration<? extends ZipEntry> all=zip.entries();all.hasMoreElements();)if(!all.nextElement().isDirectory())regular++;
            if(regular!=images.size())throw new IOException("ZIP 包含图片以外的文件，已保留原件");
            for(ArchivePages.Page page:images){
                File target=new File(directory,"page-"+result.size()+".jpg");CRC32 crc=new CRC32();
                try(InputStream in=new CheckedInputStream(zip.getInputStream(page.entry),crc);OutputStream out=new FileOutputStream(target)){
                    copyExactly(in,out,page.entry.getSize());
                    if(in.read()!=-1||crc.getValue()!=page.entry.getCrc())throw new IOException("ZIP 图片校验失败");
                }
                if(!"image/jpeg".equals(Downloader.dimensions(target).outMimeType))throw new IOException("ZIP 内含非 JPEG 图片，无法无损追加到下载漫画");
                result.add(new AlbumStorage.Image(page.chapter,page.page,Uri.fromFile(target),target.length(),target.getName()));
            }
        }
        return result;
    }
    private void copyExactly(InputStream in,OutputStream out,long count)throws Exception {
        if(count<=0||count>ArchivePages.MAX_IMAGE_BYTES)throw new IOException("单页大小超出限制");
        byte[] buffer=new byte[65536];
        while(count>0){check.run();int n=in.read(buffer,0,(int)Math.min(buffer.length,count));if(n<0)throw new EOFException("图片数据不完整");out.write(buffer,0,n);count-=n;}
    }
    // Only accept the PDF layout emitted by Core.writePdf. A byte-exact round trip
    // also protects annotations, forms and other data in externally modified PDFs.
    private List<AlbumStorage.Image> pdfImages(File source,File directory,String originalDigest)throws Exception {
        List<AlbumStorage.Image> images=new ArrayList<>();
        List<Core.Page> originals=new ArrayList<>();
        Pattern header=Pattern.compile("<< /Type /XObject /Subtype /Image /Width (\\d+) /Height (\\d+) /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length (\\d+) >>");
        try(BufferedInputStream in=new BufferedInputStream(new FileInputStream(source))){
            if(!"%PDF-1.4".equals(line(in)))throw externalPdf();
            for(String value;(value=line(in))!=null;){
                check.run();
                if(value.equals("xref"))break;
                Matcher jpeg=header.matcher(value);
                if(!jpeg.matches())continue;
                if(!"stream".equals(line(in))||images.size()>=ArchivePages.MAX_PAGES)throw externalPdf();
                File target=new File(directory,"page-"+images.size()+".jpg");
                try(OutputStream out=new BufferedOutputStream(new FileOutputStream(target))){copyExactly(in,out,Long.parseLong(jpeg.group(3)));}
                originals.add(new Core.Page(target,Integer.parseInt(jpeg.group(1)),Integer.parseInt(jpeg.group(2))));
                images.add(new AlbumStorage.Image(1,images.size()+1,Uri.fromFile(target),target.length(),target.getName()));
            }
        }
        if(images.isEmpty())throw externalPdf();
        File verification=new File(directory,"verified.pdf");
        Core.writePdf(verification,originals,(done,total)->check.run());
        if(!digest(Uri.fromFile(verification),null).equals(originalDigest))throw externalPdf();
        Files.delete(verification.toPath());
        return images;
    }
    private static IOException externalPdf(){return new IOException("此 PDF 含有非本应用生成的内容，无法无损合并，原文件已保留");}
    private static String line(InputStream in)throws IOException {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();int c;
        while((c=in.read())!=-1&&c!='\n'){if(bytes.size()>400000)throw externalPdf();bytes.write(c);}
        return c==-1&&bytes.size()==0?null:bytes.toString("ISO-8859-1");
    }
    JSONObject metadata(LibraryStore.Entry base)throws Exception {
        JSONArray entries=new JSONArray();
        for(AlbumStorage.Image p:pages)entries.put(new JSONObject().put("chapter",p.chapter).put("page",p.page)
            .put("file",AlbumRules.imageName(p.chapter,p.page,groups)).put("size",p.size));
        return new JSONObject().put("version",AlbumRules.LAYOUT_VERSION).put("id",base.id).put("title",base.title).put("entries",entries);
    }
    Uri publish(LibraryStore.Entry base,String name)throws Exception {
        if(base.format.equals("images")){
            List<FolderSave.Entry> sources=new ArrayList<>();
            for(AlbumStorage.Image p:pages)sources.add(new FolderSave.Entry(()->open(p.uri),AlbumRules.imageName(p.chapter,p.page,groups),p.size));
            return AlbumStorage.publishImages(context,sources,base.tree,name,check::run,(phase,done,total,bytes,totalBytes)->{});
        }
        File output=new File(temporary,"merged."+base.format);
        if(base.format.equals("pdf")){
            List<Core.Page> pdf=new ArrayList<>();
            for(AlbumStorage.Image p:pages){
                File jpeg=AlbumStorage.local(context,p.uri);
                if(jpeg==null&&"file".equals(p.uri.getScheme()))jpeg=new File(p.uri.getPath());
                if(jpeg==null){
                    jpeg=new File(temporary,"pdf-"+pdf.size()+".jpg");
                    try(InputStream in=open(p.uri);OutputStream out=new FileOutputStream(jpeg)){copyExactly(in,out,p.size);}
                }
                BitmapFactory.Options bounds=Downloader.dimensions(jpeg);
                if(!"image/jpeg".equals(bounds.outMimeType))throw new IOException("PDF 需要 JPEG 图片");
                pdf.add(new Core.Page(jpeg,bounds.outWidth,bounds.outHeight));
            }
            Core.writePdf(output,pdf,(done,total)->check.run());Downloader.verifyPdf(output);
        }else{
            try(ZipOutputStream zip=new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(output)))){
                zip.setLevel(1);
                for(AlbumStorage.Image p:pages){
                    zip.putNextEntry(new ZipEntry(AlbumRules.imageName(p.chapter,p.page,groups)));
                    try(InputStream in=open(p.uri)){copyExactly(in,zip,p.size);if(in.read()!=-1)throw new IOException("源图片大小已变化");}
                    zip.closeEntry();
                }
            }
        }
        return AlbumStorage.publish(context,output,base.tree,name,check);
    }
}
