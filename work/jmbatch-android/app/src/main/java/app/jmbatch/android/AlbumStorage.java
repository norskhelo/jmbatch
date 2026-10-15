package app.jmbatch.android;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.CRC32;

/** Ordered album storage in the application folder or a user-selected SAF tree. */
public final class AlbumStorage {
    public interface Check { void run() throws Exception; }
    public static final class Node {
        public final String name; public final Uri uri; public final boolean directory; public final long size;
        Node(String n, Uri u, boolean d, long s) { name=n;uri=u;directory=d;size=s; }
    }
    public static final class Image {
        public final int chapter,page; public final Uri uri; public final long size;
        Image(int c,int p,Uri u,long s){chapter=c;page=p;uri=u;size=s;}
    }
    public static final class Album {
        public final String id,title; public final List<Image> images;
        Album(String i,String t,List<Image> p){id=i;title=t;images=p;}
    }
    public static File root(Context context) {
        File base=context.getExternalFilesDir(null);if(base==null)base=context.getFilesDir();return new File(base,"exports");
    }
    public static File local(Context context,Uri uri)throws IOException {
        if(!(context.getPackageName()+".exports").equals(uri.getAuthority()))return null;
        if(!"content".equals(uri.getScheme())||uri.getPathSegments().isEmpty())throw new IOException("文件地址无效");
        File root=root(context).getCanonicalFile(), target=root;
        for(String part:uri.getPathSegments()){
            if(part.isEmpty()||part.equals(".")||part.equals("..")||part.contains("/")||part.contains("\\"))throw new IOException("文件路径无效");
            target=new File(target,part);if(Files.isSymbolicLink(target.toPath()))throw new IOException("拒绝访问链接");
        }
        target=target.getCanonicalFile();
        if(!target.getPath().startsWith(root.getPath()+File.separator))throw new IOException("文件超出保存目录");
        return target;
    }
    public static InputStream open(Context context,Uri uri)throws IOException {
        File file=local(context,uri);InputStream stream=file==null?context.getContentResolver().openInputStream(uri):new FileInputStream(file);
        if(stream==null)throw new IOException("无法读取图片文件");return stream;
    }
    public static List<Node> children(Context context,Uri uri)throws IOException {
        List<Node> result=new ArrayList<>();File folder=local(context,uri);
        if(folder!=null){
            File[] files=folder.listFiles();if(files==null)throw new IOException("图片目录不可用");
            for(File file:files){if(Files.isSymbolicLink(file.toPath()))throw new IOException("图片目录含链接");result.add(new Node(file.getName(),ExportProvider.uri(context,file),file.isDirectory(),file.length()));}
        }else{
            Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(uri,DocumentsContract.getDocumentId(uri));
            try(Cursor cursor=context.getContentResolver().query(children,new String[]{"document_id","_display_name","mime_type","_size"},null,null,null)){
                if(cursor==null)throw new IOException("无法读取目录，请重新授权");
                while(cursor.moveToNext())result.add(new Node(cursor.getString(1),DocumentsContract.buildDocumentUriUsingTree(uri,cursor.getString(0)),DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(2)),cursor.isNull(3)?-1:cursor.getLong(3)));
            }
        }
        result.sort(Comparator.comparing(n->n.name));return result;
    }
    public static Node child(Context context,Uri parent,String name)throws IOException {
        Node found=null;for(Node node:children(context,parent))if(node.name.equals(name)){if(found!=null)throw new IOException("目录含同名文件");found=node;}
        if(found==null)throw new FileNotFoundException(name);return found;
    }
    public static Album load(Context context,Uri folder)throws Exception {
        Node marker=child(context,folder,AlbumRules.MANIFEST);
        if(marker.directory||marker.size>8*1024*1024)throw new IOException("图片清单无效");
        ByteArrayOutputStream buffer=new ByteArrayOutputStream();
        try(InputStream in=open(context,marker.uri)){byte[] bytes=new byte[8192];int n;while((n=in.read(bytes))!=-1){buffer.write(bytes,0,n);if(buffer.size()>8*1024*1024)throw new IOException("图片清单过大");}}
        JSONObject json=new JSONObject(buffer.toString("UTF-8"));
        String id=json.getString("id");if(json.getInt("version")!=1||!id.matches("[0-9]{1,10}"))throw new IOException("图片清单版本无效");
        JSONArray entries=json.getJSONArray("entries");List<Image> images=new ArrayList<>();Set<String> seen=new HashSet<>();Map<Integer,Map<String,Node>> chapters=new HashMap<>();
        if(entries.length()==0||entries.length()>20000)throw new IOException("图片数量无效");
        for(int i=0;i<entries.length();i++){
            JSONObject item=entries.getJSONObject(i);int c=item.getInt("chapter"),p=item.getInt("page");String name=AlbumRules.imageName(c,p);
            if(!name.equals(item.getString("file"))||!seen.add(name))throw new IOException("图片顺序或路径无效");
            if(!chapters.containsKey(c)){
                Node chapter=child(context,folder,name.split("/")[0]);if(!chapter.directory)throw new IOException("章节不是目录");
                Map<String,Node> nodes=new HashMap<>();for(Node n:children(context,chapter.uri))if(nodes.put(n.name,n)!=null)throw new IOException("章节有同名文件");chapters.put(c,nodes);
            }
            Node image=chapters.get(c).get(name.split("/")[1]);long size=item.getLong("size");
            if(image==null||image.directory||size<=0||image.size>=0&&image.size!=size)throw new IOException("图片缺失或大小变化："+name);
            images.add(new Image(c,p,image.uri,size));
        }
        images.sort(Comparator.comparingInt((Image i)->i.chapter).thenComparingInt(i->i.page));return new Album(id,json.getString("title"),images);
    }
    public static void copy(InputStream input,OutputStream output,Check check)throws Exception {
        byte[] buffer=new byte[65536];int n;while((n=input.read(buffer))!=-1){check.run();output.write(buffer,0,n);}output.flush();
    }
    private static long crc(InputStream input,Check check)throws Exception {
        CRC32 crc=new CRC32();byte[] buffer=new byte[65536];int n;while((n=input.read(buffer))!=-1){check.run();crc.update(buffer,0,n);}return crc.getValue();
    }
    private static String mime(File source){return source.isDirectory()?DocumentsContract.Document.MIME_TYPE_DIR:source.getName().endsWith(".jpg")?"image/jpeg":source.getName().endsWith(".pdf")?"application/pdf":source.getName().endsWith(".zip")?"application/zip":"application/json";}
    public static void absent(Context context,String tree,String name)throws IOException {
        if(tree.isEmpty()){if(new File(root(context),name).exists())throw new IOException("同名文件已存在，未覆盖："+name);return;}
        Uri uri=Uri.parse(tree);Uri parent=DocumentsContract.buildDocumentUriUsingTree(uri,DocumentsContract.getTreeDocumentId(uri));
        for(Node n:children(context,parent))if(n.name.equals(name))throw new IOException("同名文件已存在，未覆盖："+name);
    }
    private static void copyLocal(File source,File target,Check check)throws Exception {
        check.run();if(Files.isSymbolicLink(source.toPath()))throw new IOException("来源包含链接");
        if(source.isDirectory()){
            if(!target.mkdir())throw new IOException("无法创建图片目录");File[] files=source.listFiles();if(files==null)throw new IOException("来源不可读");
            for(File f:files)copyLocal(f,new File(target,f.getName()),check);
        }else{
            try(InputStream in=new FileInputStream(source);FileOutputStream out=new FileOutputStream(target)){copy(in,out,check);out.getFD().sync();}
            try(InputStream a=new FileInputStream(source);InputStream b=new FileInputStream(target)){if(source.length()!=target.length()||crc(a,check)!=crc(b,check))throw new IOException("图片保存校验失败");}
        }
    }
    private static void copySaf(Context context,File source,Uri target,Check check)throws Exception {
        check.run();if(source.isDirectory()){
            File[] files=source.listFiles();if(files==null)throw new IOException("来源不可读");
            for(File file:files){Uri child=DocumentsContract.createDocument(context.getContentResolver(),target,mime(file),file.getName());if(child==null)throw new IOException("无法创建图片文件");copySaf(context,file,child,check);}
        }else{
            try(InputStream in=new FileInputStream(source);OutputStream out=context.getContentResolver().openOutputStream(target,"w")){if(out==null)throw new IOException("保存目录不可写");copy(in,out,check);}
            try(InputStream a=new FileInputStream(source);InputStream b=open(context,target)){if(crc(a,check)!=crc(b,check))throw new IOException("图片保存校验失败");}
        }
    }
    public static Uri publish(Context context,File source,String tree,String name,Check check)throws Exception {
        absent(context,tree,name);String tempName=name+"."+UUID.randomUUID()+".partial";
        if(tree.isEmpty()){
            File root=root(context);if(!root.isDirectory()&&!root.mkdirs()&&!root.isDirectory())throw new IOException("无法创建保存目录");
            File temporary=new File(root,tempName), result=new File(root,name);
            try{copyLocal(source,temporary,check);check.run();absent(context,tree,name);Files.move(temporary.toPath(),result.toPath());return ExportProvider.uri(context,result);}
            finally{if(temporary.exists())Downloader.deleteOwned(temporary,root);}
        }
        Uri treeUri=Uri.parse(tree),parent=DocumentsContract.buildDocumentUriUsingTree(treeUri,DocumentsContract.getTreeDocumentId(treeUri));
        Uri temporary=DocumentsContract.createDocument(context.getContentResolver(),parent,mime(source),tempName);if(temporary==null)throw new IOException("无法创建临时输出");boolean committed=false;
        try{
            copySaf(context,source,temporary,check);check.run();absent(context,tree,name);
            Uri renamed=DocumentsContract.renameDocument(context.getContentResolver(),temporary,name);if(renamed==null)throw new IOException("所选目录不支持安全重命名");temporary=renamed;
            try(Cursor c=context.getContentResolver().query(renamed,new String[]{"_display_name"},null,null,null)){if(c==null||!c.moveToFirst()||!name.equals(c.getString(0)))throw new IOException("存储服务更改了输出名称");}
            committed=true;return renamed;
        }finally{if(!committed)try{DocumentsContract.deleteDocument(context.getContentResolver(),temporary);}catch(Exception ignored){}}
    }
    public static void remove(Context context,Uri uri)throws Exception {
        File file=local(context,uri);if(file!=null)Downloader.deleteOwned(file,root(context));else if(!DocumentsContract.deleteDocument(context.getContentResolver(),uri))throw new IOException("删除失败");
    }
    public static void validateForDeletion(Context context,Uri folder)throws Exception {
        Album album=load(context,folder);Map<String,Set<String>> allowed=new HashMap<>();
        for(Image image:album.images){String[] path=AlbumRules.imageName(image.chapter,image.page).split("/");allowed.computeIfAbsent(path[0],k->new HashSet<>()).add(path[1]);}
        for(Node node:children(context,folder)){
            if(node.name.equals(AlbumRules.MANIFEST)&&!node.directory)continue;
            if(!node.directory||!allowed.containsKey(node.name))throw new IOException("图片目录含额外文件，已停止删除");
            for(Node image:children(context,node.uri))if(image.directory||!allowed.get(node.name).contains(image.name))throw new IOException("章节内含额外文件，已停止删除");
        }
    }
}
