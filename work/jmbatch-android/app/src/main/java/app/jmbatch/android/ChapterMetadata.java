package app.jmbatch.android;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

/** Task-local, versioned metadata records and a bounded, cancellable prefetch. */
public final class ChapterMetadata {
    public static final int MAX_WORKERS=4, MAX_BYTES=2*1024*1024;
    public static final long TTL=24*60*60*1000L;
    private static final int MAGIC=0x4a4d4301;
    public interface Check { void run() throws Exception; }
    public interface Fetch { Detail get(String id) throws Exception; }
    public interface Progress { void update(int done,int total,int cached) throws Exception; }
    public static final class UnstoppedWorkers extends IOException {
        UnstoppedWorkers(){super("旧章节线程未能退出，请重启应用后重试");}
    }
    public static final class Detail {
        public final List<String> images;
        public final long scramble;
        public Detail(List<String> images,long scramble) throws IOException {
            if(images==null||images.isEmpty()||images.size()>20000||scramble<0)throw new IOException("章节图片列表或解码参数无效");
            for(String image:images)if(image==null||!image.matches("[A-Za-z0-9_.-]{1,255}")||image.equals(".")||image.equals(".."))throw new IOException("章节图片名称无效");
            this.images=Collections.unmodifiableList(new ArrayList<>(images));this.scramble=scramble;
        }
    }
    public static String scope(String album,String cookie,String catalog) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        for(String part:new String[]{album,cookie.trim(),catalog}){
            byte[] bytes=part.getBytes(StandardCharsets.UTF_8);
            digest.update(Integer.toString(bytes.length).getBytes(StandardCharsets.US_ASCII));digest.update((byte)':');digest.update(bytes);
        }
        StringBuilder text=new StringBuilder();for(byte value:digest.digest())text.append(String.format(Locale.ROOT,"%02x",value&255));return text.toString();
    }
    public static final class Cache {
        private final File root;private final String scope;
        public Cache(File root,String scope){this.root=root;this.scope=scope;}
        public File path(String id)throws IOException{
            if(!id.matches("[0-9]{1,10}"))throw new IOException("章节编号无效");return new File(root,id+".bin");
        }
        public Detail read(String id,long now)throws IOException{
            File path=path(id);if(!path.isFile()||path.length()>MAX_BYTES)return null;
            try(DataInputStream in=new DataInputStream(new BufferedInputStream(new FileInputStream(path)))){
                if(in.readInt()!=MAGIC)return null;
                long saved=in.readLong();if(saved>now||now-saved>=TTL||!scope.equals(in.readUTF())||!id.equals(in.readUTF()))return null;
                long scramble=in.readLong();int count=in.readInt();if(count<1||count>20000)return null;
                List<String> images=new ArrayList<>();for(int i=0;i<count;i++)images.add(in.readUTF());
                if(in.read()!=-1)return null;
                return new Detail(images,scramble);
            }catch(IOException|RuntimeException invalid){return null;}
        }
        public void write(String id,Detail detail,long now)throws IOException{
            File path=path(id);if(!root.isDirectory()&&!root.mkdirs())throw new IOException("无法保存章节缓存");
            File partial=new File(root,id+".part");
            try{
                try(DataOutputStream out=new DataOutputStream(new BufferedOutputStream(new FileOutputStream(partial)))){
                    out.writeInt(MAGIC);out.writeLong(now);out.writeUTF(scope);out.writeUTF(id);out.writeLong(detail.scramble);out.writeInt(detail.images.size());
                    for(String image:detail.images)out.writeUTF(image);
                }
                if(partial.length()>MAX_BYTES)throw new IOException("章节信息过大");
                try{Files.move(partial.toPath(),path.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
                catch(AtomicMoveNotSupportedException ignored){Files.move(partial.toPath(),path.toPath(),StandardCopyOption.REPLACE_EXISTING);}
            }finally{Files.deleteIfExists(partial.toPath());}
        }
        public void invalidate(String id)throws IOException{Files.deleteIfExists(path(id).toPath());}
    }
    private static final class Result {
        final String id;final Detail detail;
        Result(String id,Detail detail){this.id=id;this.detail=detail;}
    }
    public static List<Detail> load(List<String> ids,Cache cache,Fetch fetch,Check check,
                                    Runnable abort,Progress progress,int timeout)throws Exception{
        Map<String,Detail> values=new HashMap<>();List<String> missing=new ArrayList<>();int cached=0,pages=0;
        progress.update(0,ids.size(),0);
        for(String id:ids){
            check.run();if(values.containsKey(id)||missing.contains(id))throw new IOException("章节编号重复");
            Detail detail=cache.read(id,System.currentTimeMillis());
            if(detail==null)missing.add(id);else{
                pages+=detail.images.size();if(pages>20000)throw new IOException("单本超过 20000 张图片，请拆分任务");
                values.put(id,detail);cached++;progress.update(values.size(),ids.size(),cached);
            }
        }
        if(!missing.isEmpty()){
            ExecutorService pool=Executors.newFixedThreadPool(Math.min(MAX_WORKERS,missing.size()));
            CompletionService<Result> completion=new ExecutorCompletionService<>(pool);
            List<Future<Result>> active=new ArrayList<>();int next=0,received=0;boolean success=false;
            try{
                while(received<missing.size()){
                    check.run();
                    while(next<missing.size()&&active.size()<MAX_WORKERS){
                        String id=missing.get(next++);
                        active.add(completion.submit(()->{check.run();Detail value=fetch.get(id);check.run();return new Result(id,value);}));
                    }
                    Future<Result> future=completion.poll(200,TimeUnit.MILLISECONDS);
                    if(future==null)continue;
                    active.remove(future);Result result;
                    try{result=future.get();}catch(ExecutionException error){Throwable cause=error.getCause();if(cause instanceof Exception)throw (Exception)cause;throw new IOException("章节读取异常",cause);}
                    check.run();pages+=result.detail.images.size();if(pages>20000)throw new IOException("单本超过 20000 张图片，请拆分任务");
                    cache.write(result.id,result.detail,System.currentTimeMillis());values.put(result.id,result.detail);received++;
                    progress.update(values.size(),ids.size(),cached);
                }
                check.run();success=true;
            }finally{
                if(!success)abort.run();
                for(Future<Result> future:active)future.cancel(true);
                pool.shutdownNow();
                try{if(!pool.awaitTermination(timeout+10L,TimeUnit.SECONDS))throw new UnstoppedWorkers();}
                catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new UnstoppedWorkers();}
            }
        }
        check.run();List<Detail> ordered=new ArrayList<>();for(String id:ids)ordered.add(values.get(id));return ordered;
    }
}
