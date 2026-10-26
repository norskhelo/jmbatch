package app.jmbatch.android;

import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;

/** Read-only sharing of app-owned exports; does not expose arbitrary file paths. */
public final class ExportProvider extends ContentProvider {
    public static Uri uri(Context context, File file) {
        Uri.Builder builder=new Uri.Builder().scheme("content").authority(context.getPackageName()+".exports");
        for(java.nio.file.Path part:AlbumStorage.root(context).toPath().toAbsolutePath().relativize(file.toPath().toAbsolutePath()))builder.appendPath(part.toString());
        return builder.build();
    }
    public boolean onCreate(){return true;}
    private File file(Uri uri) throws FileNotFoundException {
        try {
            File file=AlbumStorage.local(getContext(),uri);
            if(file==null||!file.exists()||file.getName().contains(".partial")||file.getName().startsWith("."))throw new IOException();
            if(file.isFile()&&!LibraryRules.supported(file.getName())&&!file.getName().endsWith(".jpg"))throw new IOException();
            return file;
        }catch(Exception error){throw new FileNotFoundException("导出文件不存在");}
    }
    public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {if(!mode.equals("r"))throw new FileNotFoundException("仅允许读取");return ParcelFileDescriptor.open(file(uri),ParcelFileDescriptor.MODE_READ_ONLY);}
    public String getType(Uri uri){try{File f=file(uri);return f.isDirectory()?android.provider.DocumentsContract.Document.MIME_TYPE_DIR:LibraryRules.mimeType(f.getName());}catch(Exception e){return "application/octet-stream";}}
    public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){
        try{File file=file(uri);String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor cursor=new MatrixCursor(cols);Object[] values=new Object[cols.length];for(int i=0;i<cols.length;i++)values[i]=cols[i].equals(OpenableColumns.DISPLAY_NAME)?file.getName():cols[i].equals(OpenableColumns.SIZE)?file.length():null;cursor.addRow(values);return cursor;}catch(Exception error){return null;}
    }
    public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
    public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
    public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
}
