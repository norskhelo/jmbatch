package app.jmbatch.android;

import android.content.*;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import org.json.*;

/** Rebuild in the original format, then journal the short same-name swap. */
final class ChapterMerge {
    private static final String PREFIX=".jmbatch-merge-";
    static String download(Store store,Store.Task task,List<AlbumStorage.Image> images,AlbumStorage.Check check)throws Exception {
        recover(store);
        if(!task.resultUri.isEmpty())return task.resultUri;
        LibraryStore.Entry base=LibraryStore.get(store.context).byUri(task.updateParent);
        if(!base.id.equals(task.id))throw new IOException("原漫画的 JM 编号已变化");
        Context context=store.context;
        File work=new File(context.getCacheDir(),"chapter-merge");
        Files.createDirectories(work.toPath());
        File temp=Files.createTempDirectory(work.toPath(),"prepare-").toFile();
        String token=PREFIX+UUID.randomUUID(),suffix=base.format.equals("images")?"":"."+base.format;
        String stagedName=token+".partial"+suffix;
        Uri staged=null;boolean journaled=false;
        try{
            LibraryStore library=LibraryStore.get(context);
            library.checkLocation(base);
            MergePages output=new MergePages(context,temp,check);
            String baseStamp=output.read(base);
            int originalCount=base.chapterCount>0?base.chapterCount:output.groups;
            output.append(images);
            int count=originalCount+task.selectedChapters.size();
            task.phase="正在保存更新后的 "+output.pages.size()+" 页";
            Downloader.writeTextAtomic(new File(temp,"output.json"),new JSONObject().put("tree",base.tree).put("name",stagedName).toString());
            staged=output.publish(base,stagedName);
            output.unchanged(base,baseStamp);
            synchronized(store){
                recover(store);
                if(journal(context).getBaseFile().exists())throw new IOException("上次合并的备份仍待清理，请检查原保存目录权限后重试");
                library.byUri(base.uri);
                String baseName=nameOf(context,base);
                JSONObject journal=new JSONObject().put("base",base.json()).put("name",baseName).put("staged",stagedName)
                    .put("baseStamp",baseStamp).put("backup",token+".original"+suffix).put("count",count).put("key",task.key)
                    .put("history",new JSONObject(context.getSharedPreferences("reader-history",Context.MODE_PRIVATE).getString(base.uri,"{}")));
                if(base.format.equals("images"))journal.put("album",output.metadata(base));
                check.run();
                if(task.discardRequested)throw new IOException("已取消追加章节");
                saveJournal(context,journal);journaled=true;
                return finish(store,journal,false);
            }
        }finally{
            try{if(staged!=null&&!journaled)AlbumStorage.remove(context,staged);}
            finally{
                try{Downloader.deleteOwned(temp,context.getCacheDir());}
                catch(IOException error){store.cleanupNotice="合并临时缓存待清理："+temp.getAbsolutePath();}
            }
        }
    }
    private static AtomicFile journal(Context c){return new AtomicFile(new File(c.getFilesDir(),"chapter-merge.json"));}
    private static void saveJournal(Context c,JSONObject data)throws IOException {
        AtomicFile journal=journal(c);FileOutputStream out=journal.startWrite();
        try{out.write(data.toString().getBytes(StandardCharsets.UTF_8));journal.finishWrite(out);}
        catch(Exception e){journal.failWrite(out);throw e;}
    }
    static void restoreOnStartup(Store store)throws Exception {
        recover(store);
        Context c=store.context;
        // A live journal owns the staged copy. The rest are interrupted preparations
        // from a previous process, where no rename of the original was attempted.
        if(journal(c).getBaseFile().exists())return;
        File work=new File(c.getCacheDir(),"chapter-merge");
        File[] abandoned=work.listFiles();if(abandoned==null)return;
        for(File directory:abandoned){
            if(!directory.getName().startsWith("prepare-")||Files.isSymbolicLink(directory.toPath())||!directory.isDirectory())continue;
            File marker=new File(directory,"output.json");
            if(marker.isFile()){
                JSONObject output=new JSONObject(Downloader.readText(marker));
                String tree=output.getString("tree"),name=output.getString("name");
                if(!name.matches("\\.jmbatch-merge-[a-f0-9-]{36}\\.partial(?:\\.pdf|\\.zip)?"))
                    throw new IOException("章节合并临时记录无效");
                String partial=java.util.regex.Pattern.quote(name)+"\\.[a-f0-9-]{36}\\.partial";
                if(tree.isEmpty()){
                    File[] files=AlbumStorage.root(c).listFiles();
                    if(files!=null)for(File file:files)if(file.getName().equals(name)||file.getName().matches(partial))
                        Downloader.deleteOwned(file,AlbumStorage.root(c));
                }else{
                    for(AlbumStorage.Node node:AlbumStorage.children(c,parent(tree)))if(node.name.equals(name)||node.name.matches(partial))
                        AlbumStorage.remove(c,node.uri);
                }
            }
            Downloader.deleteOwned(directory,work);
        }
    }
    static void recover(Store store)throws Exception {
        synchronized(store){
            AtomicFile file=journal(store.context);
            JSONObject data;
            try(InputStream in=file.openRead();ByteArrayOutputStream bytes=new ByteArrayOutputStream()){Core.copy(in,bytes);data=new JSONObject(bytes.toString("UTF-8"));}
            catch(FileNotFoundException missing){if(file.getBaseFile().exists())throw missing;return;}
            finish(store,data,true);
        }
    }
    private static String finish(Store store,JSONObject j,boolean recovering)throws Exception {
        Context c=store.context;LibraryStore.Entry base=new LibraryStore.Entry(j.getJSONObject("base"));
        // Only an interrupted operation from the previous local build can have an extra source.
        LibraryStore.Entry extra=j.has("extra")?new LibraryStore.Entry(j.getJSONObject("extra")):null;
        String name=j.getString("name"),backup=j.getString("backup"),staged=j.getString("staged");
        if(!j.has("result")){
            Uri old=find(c,base.tree,name),prepared=find(c,base.tree,staged),saved=find(c,base.tree,backup);
            if(saved==null){
                if(old==null||!old.toString().equals(base.uri)||prepared==null)throw new IOException("原漫画或临时副本已变化，请检查保存目录");
                if(recovering)new MergePages(c,c.getCacheDir(),()->{}).unchanged(base,j.getString("baseStamp"));
                rename(c,base.tree,old,backup);old=null;
            }
            if(prepared!=null){
                if(old!=null)throw new IOException("原漫画位置出现同名文件，已保留备份");
                try{old=rename(c,base.tree,prepared,name);}
                catch(Exception error){
                    // A provider can reject the second rename after accepting the first.
                    Uri originalBackup=find(c,base.tree,backup);
                    if(find(c,base.tree,name)==null&&originalBackup!=null){
                        try{rename(c,base.tree,originalBackup,name);}catch(Exception restore){error.addSuppressed(restore);}
                    }
                    throw error;
                }
            }
            if(old==null)throw new IOException("存储不可用，合并待恢复");
            j.put("result",old.toString());saveJournal(c,j);
        }
        String result=j.getString("result");
        if(!j.optBoolean("registered")){
            if(j.has("album"))AlbumStorage.remember(c,Uri.parse(result),j.getJSONObject("album"));
            if((extra!=null||!base.uri.equals(result))&&!c.getSharedPreferences("reader-history",Context.MODE_PRIVATE).edit().putString(result,j.getJSONObject("history").toString()).commit())
                throw new IOException("阅读记录保存失败，合并待恢复");
            LibraryStore library=LibraryStore.get(c);
            synchronized(library){
                library.finishMerge(base,extra,result,j.getInt("count"));
                for(Store.Task t:store.tasks){
                    if(t.resultUri.equals(base.uri)||(extra!=null&&t.resultUri.equals(extra.uri))){
                        t.resultUri=result;t.title=base.title;
                        t.settings.format=base.format;t.settings.outputUri=base.tree;t.settings.outputLabel=base.label;
                    }
                    if(t.updateParent.equals(base.uri)||(extra!=null&&t.updateParent.equals(extra.uri)))t.updateParent=result;
                    if(t.key.equals(j.getString("key"))){
                        t.title=base.title;t.status="done";t.resultUri=result;t.cleanupUri="";t.discardRequested=false;t.phase="新章节已并入原漫画";t.error="";
                    }
                }
                store.save();
            }
            j.put("registered",true);saveJournal(c,j);
        }
        try{
            if(extra!=null&&!j.optBoolean("extraMoved")){
                Uri original=find(c,extra.tree,j.getString("extraName")),saved=find(c,extra.tree,j.getString("extraBackup"));
                if(saved==null){
                    if(original==null||!original.toString().equals(extra.uri))throw new IOException("新增章节文件已移动，请检查保存目录");
                    new MergePages(c,c.getCacheDir(),()->{}).unchanged(extra,j.getString("extraStamp"));
                    rename(c,extra.tree,original,j.getString("extraBackup"));
                }
                j.put("extraMoved",true);saveJournal(c,j);
            }
            removeBackup(c,base.tree,backup);
            if(extra!=null)removeBackup(c,extra.tree,j.getString("extraBackup"));
            if(!base.uri.equals(result)&&base.format.equals("images"))AlbumStorage.forget(c,Uri.parse(base.uri));
            if(extra!=null&&extra.format.equals("images"))AlbumStorage.forget(c,Uri.parse(extra.uri));
            if(extra!=null){
                LibraryCover.forget(c,extra);
                c.getSharedPreferences("reader-history",Context.MODE_PRIVATE).edit().remove(extra.uri).apply();
            }
            journal(c).delete();
        }catch(Exception cleanup){
            store.cleanupNotice="章节已合并，原保存目录中的备份待清理："+cleanup.getMessage();
            for(Store.Task t:store.tasks)if(t.key.equals(j.getString("key")))t.cleanupNote=store.cleanupNotice;
        }
        return result;
    }
    private static void removeBackup(Context c,String tree,String name)throws Exception {
        if(!name.startsWith(PREFIX))throw new IOException("无效的合并临时文件名");
        Uri backup=find(c,tree,name);
        if(backup!=null)AlbumStorage.remove(c,backup);
    }
    static boolean temporaryName(String name){return name!=null&&name.startsWith(PREFIX);}
    private static String nameOf(Context c,LibraryStore.Entry book)throws Exception {
        Uri uri=Uri.parse(book.uri);File local=AlbumStorage.local(c,uri);
        if(local!=null)return local.getName();
        for(AlbumStorage.Node node:AlbumStorage.children(c,parent(book.tree)))if(node.uri.equals(uri))return node.name;
        throw new IOException("漫画已移出原保存目录");
    }
    private static Uri parent(String tree){
        Uri uri=Uri.parse(tree);return DocumentsContract.buildDocumentUriUsingTree(uri,DocumentsContract.getTreeDocumentId(uri));
    }
    private static Uri find(Context c,String tree,String name)throws Exception {
        if(name.isEmpty()||name.equals(".")||name.equals("..")||name.contains("/")||name.contains("\\"))throw new IOException("无效文件名");
        if(tree.isEmpty()){
            File file=new File(AlbumStorage.root(c),name);
            if(Files.isSymbolicLink(file.toPath()))throw new IOException("拒绝操作链接");
            return file.exists()?ExportProvider.uri(c,file):null;
        }
        try{return AlbumStorage.child(c,parent(tree),name).uri;}catch(FileNotFoundException missing){return null;}
    }
    private static Uri rename(Context c,String tree,Uri source,String name)throws Exception {
        if(find(c,tree,name)!=null)throw new IOException("保存目录中已有同名文件："+name);
        File local=AlbumStorage.local(c,source);
        if(local!=null){
            File target=new File(local.getParentFile(),name);
            Files.move(local.toPath(),target.toPath());return ExportProvider.uri(c,target);
        }
        Uri renamed=DocumentsContract.renameDocument(c.getContentResolver(),source,name);
        if(renamed==null||!renamed.equals(find(c,tree,name)))throw new IOException("所选目录不支持保留原文件名，请检查存储授权");
        return renamed;
    }
    private ChapterMerge(){}
}
