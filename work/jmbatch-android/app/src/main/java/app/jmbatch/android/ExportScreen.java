package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.widget.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ExportScreen {
    public static final int DIRECTORY_REQUEST=52;
    private static ExportScreen pending;
    private final Activity activity;private final Store store;private final LibraryStore.Entry entry;
    private String tree,label;private TextView destination;private AlertDialog dialog;
    public ExportScreen(Activity a,Store s,LibraryStore.Entry e){activity=a;store=s;entry=e;tree=e.tree;label=e.label;}
    public static boolean onResult(int request,int result,Intent data){
        if(request!=DIRECTORY_REQUEST)return false;ExportScreen screen=pending;pending=null;
        if(screen==null||screen.dialog==null||!screen.dialog.isShowing()||result!=Activity.RESULT_OK||data==null||data.getData()==null)return true;
        try{
            Uri uri=data.getData();int flags=data.getFlags()&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            if((screen.activity.getPackageName()+".documents").equals(uri.getAuthority())){screen.tree="";screen.label="应用下载目录";screen.destination.setText(screen.label);return true;}
            if((flags&Intent.FLAG_GRANT_WRITE_URI_PERMISSION)==0)throw new Exception("所选目录不可写");
            screen.activity.getContentResolver().takePersistableUriPermission(uri,flags);screen.tree=uri.toString();screen.label=android.provider.DocumentsContract.getTreeDocumentId(uri);screen.destination.setText(screen.label);
        }catch(Exception error){screen.error(error.getMessage());}return true;
    }
    private void error(String message){new AlertDialog.Builder(activity).setMessage(message).setPositiveButton("关闭",null).show();}
    public void show(){
        if(!entry.format.equals("images")){error("请选择图片漫画导出；旧版 PDF / ZIP 可直接打开或分享");return;}
        LinearLayout form=new LinearLayout(activity);form.setOrientation(LinearLayout.VERTICAL);int pad=(int)(20*activity.getResources().getDisplayMetrics().density);form.setPadding(pad,pad,pad,pad);
        TextView hint=new TextView(activity);hint.setText("导出保留原始图片，可重复导出。多章节 PDF 可合并为一本或每章一个文件。");form.addView(hint);
        RadioGroup formats=new RadioGroup(activity);RadioButton pdf=new RadioButton(activity),zip=new RadioButton(activity);pdf.setId(android.view.View.generateViewId());zip.setId(android.view.View.generateViewId());pdf.setText("PDF");zip.setText("ZIP 图片包");formats.addView(pdf);formats.addView(zip);formats.check(pdf.getId());form.addView(formats);
        CheckBox numeric=new CheckBox(activity);numeric.setText("文件名仅编号（分章节时附章节序号）");form.addView(numeric);
        TextView layout=new TextView(activity);layout.setText("ZIP：单章节图片平铺，多章节分目录；仅包含图片。");form.addView(layout);
        CheckBox split=new CheckBox(activity);split.setText("PDF 分章节导出（不勾选则统一导出）");form.addView(split);
        formats.setOnCheckedChangeListener((g,id)->split.setEnabled(id==pdf.getId()));
        destination=new TextView(activity);destination.setText(label);form.addView(destination);
        Button choose=new Button(activity);choose.setText("选择导出目录");choose.setOnClickListener(v->{pending=this;try{activity.startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION|Intent.FLAG_GRANT_PREFIX_URI_PERMISSION),DIRECTORY_REQUEST);}catch(Exception e){pending=null;error("系统目录选择器不可用");}});form.addView(choose);
        Button app=new Button(activity);app.setText("导出到应用目录");app.setOnClickListener(v->{tree="";label="应用下载目录";destination.setText(label);});form.addView(app);
        ScrollView scroll=new ScrollView(activity);scroll.addView(form);
        dialog=new AlertDialog.Builder(activity).setTitle("导出："+entry.title).setView(scroll).setNegativeButton("取消",null).setPositiveButton("开始导出",null).create();
        dialog.setOnDismissListener(d->{if(pending==this)pending=null;});
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            synchronized(store){if(store.running||store.libraryBusy){error("请先暂停下载，并等待其他文件操作完成");return;}for(Store.Task t:store.snapshot())if(t.status.equals("running")||t.status.equals("resetting")){error("下载正在停止，请稍后重试");return;}store.libraryBusy=true;}
            String format=pdf.isChecked()?"pdf":"zip",outputTree=tree,outputLabel=label;boolean numbered=numeric.isChecked(),flatten=true,separate=split.isChecked();dialog.dismiss();
            AtomicBoolean cancelled=new AtomicBoolean();ProgressDialog progress=new ProgressDialog(activity);progress.setTitle("导出漫画");progress.setMessage("正在读取原始图片…");progress.setCancelable(false);progress.setButton(DialogInterface.BUTTON_NEGATIVE,"取消",(x,w)->cancelled.set(true));progress.show();
            new Thread(()->{
                String result;
                try{List<LibraryStore.Entry> files=AlbumExporter.export(activity,Uri.parse(entry.uri),outputTree,outputLabel,format,numbered,flatten,separate,()->{if(cancelled.get())throw new java.io.InterruptedIOException("导出已取消，原始图片保留");},message->activity.runOnUiThread(()->{if(progress.isShowing())progress.setMessage(message);}));
                    LibraryStore.get(activity).importFound(files);result="导出完成："+files.size()+" 个文件\n保存到："+outputLabel+"\n原始图片保留，可在已下载漫画中打开或分享导出文件。";
                }catch(Exception e){result="导出未完成："+e.getMessage();}finally{store.libraryBusy=false;}
                String message=result;activity.runOnUiThread(()->{progress.dismiss();if(!activity.isFinishing()&&!activity.isDestroyed())error(message);});
            },"album-export").start();
        }));dialog.show();
    }
}
