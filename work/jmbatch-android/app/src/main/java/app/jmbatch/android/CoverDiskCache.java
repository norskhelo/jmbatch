package app.jmbatch.android;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Small disposable previews; atomic writes and per-comic coordination across screens. */
public final class CoverDiskCache {
    public static final int MAX_ENTRY=256*1024, MAX_ENTRIES=4096;
    public static final long MAX_BYTES=128L*1024*1024;
    private static final Object[] locks=new Object[32];
    static {for(int i=0;i<locks.length;i++)locks[i]=new Object();}
    public interface Stamps {String get(String uri)throws Exception;}
    public interface Loader {Value load()throws Exception;}
    public static final class Value {
        public final byte[] image;
        public final String dependency,stamp;
        public Value(byte[] image,String dependency,String stamp){this.image=image;this.dependency=dependency;this.stamp=stamp;}
    }
    private final File root;
    public CoverDiskCache(File root){this.root=root;}
    File file(String key)throws Exception {
        byte[] digest=MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8));
        StringBuilder name=new StringBuilder();for(byte b:digest)name.append(String.format(Locale.ROOT,"%02x",b&255));
        return new File(root,name+".cover");
    }
    public byte[] get(String key,String uri,Stamps stamps,Loader loader)throws Exception {
        File file=file(key);
        synchronized(locks[(key.hashCode()&0x7fffffff)%locks.length]){
            String source=stamps.get(uri);
            try{
                if(file.length()<=MAX_ENTRY)try(DataInputStream input=new DataInputStream(new FileInputStream(file))){
                    if(input.readInt()!=1||!input.readUTF().equals(source))throw new IOException("旧封面");
                    String dependency=input.readUTF(),version=input.readUTF();
                    if(!dependency.isEmpty()&&!stamps.get(dependency).equals(version))throw new IOException("首图已变化");
                    int size=input.readInt();if(size<=0||size>MAX_ENTRY)throw new IOException("封面无效");
                    byte[] bytes=new byte[size];input.readFully(bytes);if(input.read()!=-1)throw new IOException("封面无效");
                    file.setLastModified(System.currentTimeMillis());return bytes;
                }
            }catch(Exception ignored){ /* Missing, stale or truncated entries are rebuilt. */ }
            Value value=loader.load();
            if(value==null||value.image==null)return null;
            if(value.image.length>0&&value.image.length<=MAX_ENTRY&&source.equals(stamps.get(uri))&&
                (value.dependency.isEmpty()||value.stamp.equals(stamps.get(value.dependency))))write(file,source,value);
            return value.image;
        }
    }
    private void write(File file,String source,Value value){
        File temporary=null;
        try{
            if(!root.isDirectory()&&!root.mkdirs()&&!root.isDirectory())return;
            temporary=File.createTempFile("cover-",".tmp",root);
            try(DataOutputStream output=new DataOutputStream(new FileOutputStream(temporary))){
                output.writeInt(1);output.writeUTF(source);output.writeUTF(value.dependency);output.writeUTF(value.stamp);
                output.writeInt(value.image.length);output.write(value.image);
            }
            if(temporary.length()>MAX_ENTRY)return;
            Files.move(temporary.toPath(),file.toPath(),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
            trim();
        }catch(IOException ignored){ /* Disk cache failure cannot fail a download. */ }
        finally{if(temporary!=null)temporary.delete();}
    }
    private void trim(){
        File[] files=root.listFiles((dir,name)->name.matches("[0-9a-f]{64}\\.cover"));if(files==null)return;
        Arrays.sort(files,Comparator.comparingLong(File::lastModified));
        long size=0;for(File file:files)size+=file.length();int count=files.length;
        for(File file:files){if(count<=MAX_ENTRIES&&size<=MAX_BYTES)break;long bytes=file.length();if(file.delete()){size-=bytes;count--;}}
    }
    public void forget(String key){try{file(key).delete();}catch(Exception ignored){}}
}
