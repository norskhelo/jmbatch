package app.jmbatch.android;

import android.content.ClipData;
import android.content.Context;
import android.content.Intent;
import android.content.res.AssetFileDescriptor;
import android.net.Uri;
import android.os.CancellationSignal;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/** Prepare a read-only share off the UI thread; never select a recipient. */
final class FileSharing {
    private FileSharing() {}

    static Intent prepare(Context context, List<LibraryStore.Entry> items,
                          CancellationSignal cancellation) throws IOException {
        if(items.isEmpty())throw new IOException("请先选择要分享的文件");
        ArrayList<Uri> uris=new ArrayList<>();
        String mime=null;
        LibraryStore library=LibraryStore.get(context);
        for(LibraryStore.Entry item:items){
            cancellation.throwIfCanceled();
            if(!item.format.equals("pdf")&&!item.format.equals("zip"))
                throw new IOException("图片文件夹请先导出为 PDF 或 ZIP 后分享");
            Uri uri=Uri.parse(item.uri);
            try {
                library.check(item);
                cancellation.throwIfCanceled();
                // Open through the same provider the recipient will use, including
                // the app's own provider. Merely finding the local file is not enough.
                try(AssetFileDescriptor file=context.getContentResolver().openAssetFileDescriptor(uri,"r",cancellation)){
                    if(file==null)throw new IOException("存储服务未返回可读文件");
                }
            } catch(SecurityException error){
                throw new IOException("无法分享“"+item.title+"”：读取权限已失效，请重新选择原保存目录授权后重试。",error);
            } catch(FileNotFoundException error){
                throw new IOException("无法分享“"+item.title+"”：文件不存在、已移动或保存目录不可用，请检查文件和目录授权。",error);
            } catch(IOException error){
                throw new IOException("无法分享“"+item.title+"”："+error.getMessage(),error);
            }
            cancellation.throwIfCanceled();
            String type=LibraryRules.mimeType("file."+item.format);
            mime=mime==null?type:mime.equals(type)?mime:"*/*";
            uris.add(uri);
        }
        boolean single=uris.size()==1;
        Intent intent=new Intent(single?Intent.ACTION_SEND:Intent.ACTION_SEND_MULTIPLE)
                .setType(mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        if(single)intent.putExtra(Intent.EXTRA_STREAM,uris.get(0));
        else intent.putParcelableArrayListExtra(Intent.EXTRA_STREAM,uris);
        ClipData clip=ClipData.newRawUri("漫画",uris.get(0));
        for(int i=1;i<uris.size();i++)clip.addItem(new ClipData.Item(uris.get(i)));
        intent.setClipData(clip);
        return intent;
    }
}
