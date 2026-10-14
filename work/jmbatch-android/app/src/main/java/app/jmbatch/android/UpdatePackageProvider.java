package app.jmbatch.android;
import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;

/** Grants the system installer read-only access to exactly one cached APK. */
public final class UpdatePackageProvider extends ContentProvider {
    public boolean onCreate(){return true;}
    private File file(Uri uri)throws FileNotFoundException{
        File file=UpdateInstaller.apk(getContext());
        if(!uri.getAuthority().equals(getContext().getPackageName()+".updates")||!uri.getPath().equals("/update.apk")||!file.isFile())throw new FileNotFoundException("更新包不存在");return file;
    }
    public String getType(Uri uri){return "application/vnd.android.package-archive";}
    public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
        if(!mode.equals("r"))throw new FileNotFoundException("仅允许读取");return ParcelFileDescriptor.open(file(uri),ParcelFileDescriptor.MODE_READ_ONLY);
    }
    public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){
        try{File f=file(uri);String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor c=new MatrixCursor(cols);Object[] values=new Object[cols.length];for(int i=0;i<cols.length;i++)values[i]=cols[i].equals(OpenableColumns.DISPLAY_NAME)?"JMBatch-update.apk":cols[i].equals(OpenableColumns.SIZE)?f.length():null;c.addRow(values);return c;}catch(Exception error){return null;}
    }
    public Uri insert(Uri uri,ContentValues v){throw new UnsupportedOperationException();}
    public int update(Uri uri,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
    public int delete(Uri uri,String s,String[] a){throw new UnsupportedOperationException();}
}
