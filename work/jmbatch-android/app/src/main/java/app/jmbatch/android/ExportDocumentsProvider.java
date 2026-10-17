package app.jmbatch.android;

import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.DocumentsContract;
import android.provider.DocumentsProvider;
import java.io.*;
import java.util.*;

/** Read-only system browser for ordered image folders and exported documents. */
public final class ExportDocumentsProvider extends DocumentsProvider {
    private static final String ROOT="exports";
    private static final String[] DOCS={"document_id","display_name","mime_type","flags","size","last_modified"};
    public static Uri folder(android.content.Context context){return folderUri(context,ROOT);}
    public static Uri folder(android.content.Context context,File directory)throws IOException {
        if(directory==null||!directory.isDirectory())throw new IOException("目录不存在");
        // Reuse the exports provider's containment and symlink checks before granting a subtree.
        File checked=AlbumStorage.local(context,ExportProvider.uri(context,directory));
        if(checked==null)throw new IOException("目录不可访问");
        String relative=AlbumStorage.root(context).toPath().toAbsolutePath().relativize(checked.toPath().toAbsolutePath()).toString().replace(File.separatorChar,'/');
        return folderUri(context,"file:"+relative);
    }
    private static Uri folderUri(android.content.Context context,String id){
        Uri tree=DocumentsContract.buildTreeDocumentUri(context.getPackageName()+".documents",id);
        return DocumentsContract.buildDocumentUriUsingTree(tree,id);
    }
    public boolean onCreate(){return true;}
    private File file(String id)throws FileNotFoundException {
        try{
            if(ROOT.equals(id))return AlbumStorage.root(getContext()).getCanonicalFile();
            if(!id.startsWith("file:"))throw new IOException("文件编号无效");
            Uri.Builder builder=new Uri.Builder().scheme("content").authority(getContext().getPackageName()+".exports");
            for(String part:id.substring(5).split("/")){if(part.startsWith(".")||part.contains(".partial"))throw new IOException("不可访问临时文件");builder.appendPath(part);}
            File result=AlbumStorage.local(getContext(),builder.build());
            if(result==null||!result.exists()||!(result.isDirectory()||LibraryRules.supported(result.getName())||result.getName().endsWith(".jpg")))throw new IOException("文件不存在");
            return result;
        }catch(IOException e){throw new FileNotFoundException(e.getMessage());}
    }
    private String id(File file){return "file:"+AlbumStorage.root(getContext()).toPath().toAbsolutePath().relativize(file.toPath().toAbsolutePath()).toString().replace(File.separatorChar,'/');}
    private static void row(MatrixCursor cursor,Map<String,Object> values){Object[] row=new Object[cursor.getColumnCount()];for(int i=0;i<row.length;i++)row[i]=values.get(cursor.getColumnName(i));cursor.addRow(row);}
    public Cursor queryRoots(String[] projection){
        MatrixCursor cursor=new MatrixCursor(projection==null?new String[]{"root_id","document_id","title","summary","flags","mime_types","icon"}:projection);
        Map<String,Object> values=new HashMap<>();values.put("root_id",ROOT);values.put("document_id",ROOT);values.put("title","JM Batch");values.put("summary","排序图片 / PDF / ZIP");values.put("flags",DocumentsContract.Root.FLAG_LOCAL_ONLY|DocumentsContract.Root.FLAG_SUPPORTS_IS_CHILD);values.put("mime_types","image/jpeg\napplication/pdf\napplication/zip");values.put("icon",R.drawable.ic_launcher);row(cursor,values);return cursor;
    }
    private void add(MatrixCursor cursor,String id)throws FileNotFoundException {
        File f=file(id);Map<String,Object> values=new HashMap<>();values.put("document_id",id);values.put("flags",0);values.put("display_name",ROOT.equals(id)?"JM Batch 保存的漫画":f.getName());
        values.put("mime_type",ROOT.equals(id)||f.isDirectory()?DocumentsContract.Document.MIME_TYPE_DIR:f.getName().endsWith(".jpg")?"image/jpeg":f.getName().endsWith(".pdf")?"application/pdf":"application/zip");values.put("size",f.isFile()?f.length():null);values.put("last_modified",f.lastModified());row(cursor,values);
    }
    public Cursor queryDocument(String id,String[] projection)throws FileNotFoundException {MatrixCursor c=new MatrixCursor(projection==null?DOCS:projection);add(c,id);return c;}
    public Cursor queryChildDocuments(String parent,String[] projection,String sort)throws FileNotFoundException {
        File folder=file(parent);MatrixCursor cursor=new MatrixCursor(projection==null?DOCS:projection);if(ROOT.equals(parent)&&!folder.exists())return cursor;
        File[] children=folder.listFiles();if(children==null)throw new FileNotFoundException("目录无法读取");Arrays.sort(children,Comparator.comparing(File::getName));
        for(File f:children)try{add(cursor,id(f));}catch(FileNotFoundException ignored){}return cursor;
    }
    public boolean isChildDocument(String parent,String child){try{return file(child).getCanonicalPath().startsWith(file(parent).getCanonicalPath()+File.separator);}catch(IOException e){return false;}}
    @Override public DocumentsContract.Path findDocumentPath(String parent,String child)throws FileNotFoundException {
        file(child);if(parent!=null&&!parent.equals(child)&&!isChildDocument(parent,child))throw new FileNotFoundException("目录不存在");
        List<String> path=new ArrayList<>();path.add(ROOT);
        if(!ROOT.equals(child)){String relative="";for(String part:child.substring(5).split("/")){relative+=relative.isEmpty()?part:"/"+part;path.add("file:"+relative);}}
        if(parent!=null)path=new ArrayList<>(path.subList(path.indexOf(parent),path.size()));
        return new DocumentsContract.Path(parent==null?ROOT:null,path);
    }
    public ParcelFileDescriptor openDocument(String id,String mode,CancellationSignal signal)throws FileNotFoundException {
        if(!"r".equals(mode))throw new FileNotFoundException("此入口只读");if(signal!=null)signal.throwIfCanceled();File f=file(id);if(!f.isFile())throw new FileNotFoundException("请选择图片或文件");return ParcelFileDescriptor.open(f,ParcelFileDescriptor.MODE_READ_ONLY);
    }
}
