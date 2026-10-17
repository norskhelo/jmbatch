package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.provider.DocumentsContract;
import android.widget.*;
import java.io.*;
import java.util.*;

/** Read-only browser for the selected SAF folder or the application's exports. */
public final class SavedDirectory {
    private final Activity activity;
    private final Uri tree;
    private final String label;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ArrayList<Item> items = new ArrayList<>();
    private final ArrayList<String> labels = new ArrayList<>();
    private final ArrayList<Item> parents = new ArrayList<>();
    private AlertDialog dialog;
    private TextView status;
    private ArrayAdapter<String> adapter;
    private Button up;
    private CancellationSignal cancellation;
    private int generation;

    private static final class Item {
        final String name, id, mime;
        final Uri uri;
        final boolean directory;
        Item(String name, String id, String mime, Uri uri) {
            this.name=name; this.id=id; this.mime=mime; this.uri=uri;
            directory=DocumentsContract.Document.MIME_TYPE_DIR.equals(mime);
        }
    }

    public SavedDirectory(Activity activity, String outputUri, String label) {
        this.activity=activity; this.tree=outputUri.isEmpty()?null:Uri.parse(outputUri); this.label=label;
    }

    public void openExternal() {
        final Uri document;
        try { document=tree==null?ExportDocumentsProvider.folder(activity):DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree)); }
        catch(Exception error){externalFallback("保存目录地址无效，请重新选择目录。",null);return;}
        openExternal(document);
    }

    private void openExternal(Uri document) {
        int result=SystemDirectory.openFileManager(activity,document);
        if(result==SystemDirectory.UNAVAILABLE)
            externalFallback("未找到可用的系统文件管理器。请选择其他打开方式。",document);
        else if(result==SystemDirectory.HOME){
            Toast.makeText(activity,"已打开系统文件管理器；若未定位，请手动进入保存目录。",Toast.LENGTH_LONG).show();
            new AlertDialog.Builder(activity).setTitle("保存目录位置")
                .setMessage("已打开系统文件管理器。此设备不支持直接定位到该目录，请手动打开以下位置：\n\n"+location()+
                    "\n\n若应用目录不可见，可使用文档管理或应用内查看；也可在首页选择可见的公共文件夹用于后续下载。")
                .setPositiveButton("确定",null)
                .setNeutralButton("复制位置",(d,w)->((ClipboardManager)activity.getSystemService(Activity.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("保存目录",location())))
                .setNegativeButton("其他打开方式",(d,w)->externalFallback("请选择其他打开方式",document)).show();
        }
    }

    private void externalFallback(String message,Uri document){
        if(document==null){new AlertDialog.Builder(activity).setTitle("打开保存目录").setMessage(message).setPositiveButton("关闭",null).show();return;}
        new AlertDialog.Builder(activity).setTitle(message)
            .setItems(new String[]{"系统文档管理","选择其他应用","应用内查看当前目录"},(d,index)->{
                if(index==0){
                    if(!SystemDirectory.open(activity,SystemDirectory.directory(document),true)&&
                        !SystemDirectory.open(activity,SystemDirectory.picker(document),false))
                        externalFallback("文档管理不可用，请选择其他方式。",document);
                } else if(index==1){
                    if(!SystemDirectory.choose(activity,document))externalFallback("没有可打开此目录的应用，请使用应用内查看。",document);
                } else if(dialog==null||!dialog.isShowing())show();
            }).setNegativeButton("关闭",null).show();
    }

    public void show() {
        LinearLayout form=new LinearLayout(activity); form.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(16*activity.getResources().getDisplayMetrics().density); form.setPadding(pad,pad,pad,pad);
        status=new TextView(activity); status.setTextIsSelectable(true); form.addView(status);
        up=new ActionButton(activity); up.setText("上一级"); up.setEnabled(false);
        up.setOnClickListener(v->{if(!parents.isEmpty()){parents.remove(parents.size()-1);load();}});
        Button refresh=new ActionButton(activity); refresh.setText("刷新"); refresh.setOnClickListener(v->load());
        form.addView(new ActionRow(activity,up,refresh));
        Button external=new ActionButton(activity);external.setText("在文件管理器中打开");external.setOnClickListener(v->{
            if(parents.isEmpty())openExternal();
            else try{
                Uri current=parents.get(parents.size()-1).uri;
                openExternal(tree==null?ExportDocumentsProvider.folder(activity,AlbumStorage.local(activity,current)):current);
            }catch(Exception failure){externalFallback("保存目录地址无效，请重新选择目录。",null);}
        });form.addView(external);
        ListView list=new ListView(activity); adapter=new ArrayAdapter<>(activity,android.R.layout.simple_list_item_1,labels); list.setAdapter(adapter);
        form.addView(list,new LinearLayout.LayoutParams(-1,(int)(320*activity.getResources().getDisplayMetrics().density)));
        list.setOnItemClickListener((p,v,position,id)->{
            Item item=items.get(position);
            if(item.directory){parents.add(item);load();}
            else new AlertDialog.Builder(activity).setTitle(item.name).setItems(new String[]{"打开文件","分享文件"},(d,index)->open(item,index==1)).show();
        });
        dialog=new AlertDialog.Builder(activity).setTitle("漫画保存目录").setView(form).setNegativeButton("关闭",null).create();
        dialog.setOnDismissListener(d->{generation++; if(cancellation!=null)cancellation.cancel();});
        dialog.show(); load();
    }

    private String location() {
        if(tree==null){try{return parents.isEmpty()?AlbumStorage.root(activity).getAbsolutePath():AlbumStorage.local(activity,parents.get(parents.size()-1).uri).getAbsolutePath();}catch(Exception e){return AlbumStorage.root(activity).getAbsolutePath();}}
        StringBuilder path=new StringBuilder(label);
        for(Item parent:parents)path.append(" / ").append(parent.name);
        return path.toString();
    }

    private void load() {
        if(cancellation!=null)cancellation.cancel();
        final CancellationSignal signal=cancellation=new CancellationSignal();
        final int ticket=++generation;
        final String path=location();
        final String documentId=tree==null?null:parents.isEmpty()?DocumentsContract.getTreeDocumentId(tree):parents.get(parents.size()-1).id;
        up.setEnabled(!parents.isEmpty()); items.clear(); labels.clear(); adapter.notifyDataSetChanged(); status.setText(path+"\n正在读取…");
        Thread worker=new Thread(()->{
            ArrayList<Item> found=new ArrayList<>(); String error=null;
            try {
                if(tree==null){
                    File folder=new File(path);
                    if(folder.exists()){
                        File[] files=folder.listFiles();
                        if(files==null)throw new IOException("目录无法读取");
                        for(File file:files){
                            signal.throwIfCanceled();
                            String name=file.getName();
                            if(!name.startsWith(".")&&!name.contains(".partial")&&!java.nio.file.Files.isSymbolicLink(file.toPath())&&(file.isDirectory()||LibraryRules.supported(name)||name.endsWith(".jpg"))&&folder.getCanonicalFile().equals(file.getCanonicalFile().getParentFile()))
                                found.add(new Item(name,"",file.isDirectory()?DocumentsContract.Document.MIME_TYPE_DIR:name.endsWith(".jpg")?"image/jpeg":name.endsWith(".pdf")?"application/pdf":"application/zip",ExportProvider.uri(activity,file)));
                        }
                    }
                } else {
                    String[] columns={DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE};
                    Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(tree,documentId);
                    try(Cursor cursor=activity.getContentResolver().query(children,columns,null,null,null,signal)){
                        if(cursor==null)throw new IOException("存储服务未返回目录内容");
                        while(cursor.moveToNext()){
                            signal.throwIfCanceled();
                            String id=cursor.getString(0),name=cursor.getString(1),mime=cursor.getString(2);
                            if(name==null||id==null||name.endsWith(".partial"))continue;
                            found.add(new Item(name,id,mime==null?"application/octet-stream":mime,DocumentsContract.buildDocumentUriUsingTree(tree,id)));
                        }
                    }
                }
                found.sort((a,b)->a.directory!=b.directory?(a.directory?-1:1):a.name.compareToIgnoreCase(b.name));
            } catch(SecurityException denied){error="目录访问权限已失效，请返回首页重新选择保存目录。";}
              catch(Exception failure){error="无法读取保存目录："+failure.getClass().getSimpleName()+"。请确认目录仍存在、存储设备可用，并重新选择目录。";}
            final String message=error;
            main.post(()->{
                if(ticket!=generation||activity.isFinishing()||activity.isDestroyed()||!dialog.isShowing())return;
                items.addAll(found);
                for(Item item:found)labels.add((item.directory?"[目录] ":"")+item.name);
                adapter.notifyDataSetChanged();
                status.setText(path+"\n"+(message!=null?message:found.isEmpty()?"此目录暂无可查看的文件。":"共 "+found.size()+" 项；点击文件可打开或分享。"));
            });
        },"saved-directory-list"); worker.setDaemon(true);worker.start();
    }

    private void open(Item item, boolean share) {
        String name=item.name.toLowerCase(Locale.ROOT);
        if(!share&&(name.endsWith(".pdf")||name.endsWith(".zip"))){
            ReaderActivity.open(activity,new LibraryStore.Entry(LibraryRules.idFromName(item.name),item.name,item.uri.toString(),tree==null?"":tree.toString(),label,name.endsWith(".pdf")?"pdf":"zip",false));
            return;
        }
        Intent intent=new Intent(share?Intent.ACTION_SEND:Intent.ACTION_VIEW).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.setClipData(ClipData.newRawUri("文件",item.uri));
        if(share){intent.setType(item.mime);intent.putExtra(Intent.EXTRA_STREAM,item.uri);}else intent.setDataAndType(item.uri,item.mime);
        try{activity.startActivity(Intent.createChooser(intent,share?"分享文件":"打开文件"));}
        catch(Exception failure){Toast.makeText(activity,"无法打开文件：文件可能已移动、目录授权失效，或没有支持此格式的应用。",Toast.LENGTH_LONG).show();}
    }
}
