package app.jmbatch.android;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.CancellationSignal;
import android.provider.DocumentsContract;
import java.io.*;
import java.util.*;

/** Read-only, non-recursive scan of one selected folder. No file contents are opened. */
public final class LibraryScanner {
    public static final class Result {
        public final List<LibraryStore.Entry> entries=new ArrayList<>();
        public int skipped;
    }
    private static LibraryStore.Entry entry(String name,Uri uri,String tree,String label){
        return new LibraryStore.Entry(LibraryRules.idFromName(name),name.substring(0,name.length()-4),uri.toString(),tree,label,name.toLowerCase(Locale.ROOT).endsWith(".pdf")?"pdf":"zip",false);
    }
    public static Result scan(Context context,String tree,String label,CancellationSignal signal)throws IOException {
        Result result=new Result();
        if(tree.isEmpty()){
            File root=context.getExternalFilesDir(null);if(root==null)root=context.getFilesDir();
            File folder=new File(root,"exports");
            LibraryRules.Scan found=LibraryRules.scanOwned(folder,signal::isCanceled);result.skipped=found.skipped;
            for(File file:found.files){signal.throwIfCanceled();result.entries.add(entry(file.getName(),ExportProvider.uri(context,file),tree,label));}
            File[] children=folder.listFiles();if(children!=null)for(File child:children)if(child.isDirectory()&&!child.getName().startsWith(".")&&!child.getName().contains(".partial")){
                signal.throwIfCanceled();try{Uri uri=ExportProvider.uri(context,child);AlbumStorage.Album album=AlbumStorage.load(context,uri);result.entries.add(new LibraryStore.Entry(album.id,album.title,uri.toString(),tree,label,"images",false));}catch(Exception invalid){result.skipped++;}
            }
        }else{
            Uri root=Uri.parse(tree);
            Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(root,DocumentsContract.getTreeDocumentId(root));
            String[] columns={DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE,DocumentsContract.Document.COLUMN_SIZE};
            try(Cursor cursor=context.getContentResolver().query(children,columns,null,null,null,signal)){
                if(cursor==null)throw new IOException("存储服务未返回目录内容，请重新授权原保存目录");
                while(cursor.moveToNext()){
                    signal.throwIfCanceled();String id=cursor.getString(0),name=cursor.getString(1),mime=cursor.getString(2);
                    if(id!=null&&name!=null&&!name.startsWith(".")&&!name.contains(".partial")&&DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)){
                        try{Uri uri=DocumentsContract.buildDocumentUriUsingTree(root,id);AlbumStorage.Album album=AlbumStorage.load(context,uri);result.entries.add(new LibraryStore.Entry(album.id,album.title,uri.toString(),tree,label,"images",false));}catch(Exception invalid){result.skipped++;}continue;
                    }
                    if(name==null||!LibraryRules.supported(name))continue;
                    if(id==null||DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)||(!cursor.isNull(3)&&cursor.getLong(3)==0)){result.skipped++;continue;}
                    result.entries.add(entry(name,DocumentsContract.buildDocumentUriUsingTree(root,id),tree,label));
                }
            }
        }
        signal.throwIfCanceled();return result;
    }
}
