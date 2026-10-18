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
    private final Activity activity;private final Store store;private final List<LibraryStore.Entry> entries;private final Runnable finished;
    private String tree,label;private TextView destination;private AlertDialog dialog;
    public ExportScreen(Activity a,Store s,LibraryStore.Entry e){this(a,s,Collections.singletonList(e),()->{});}
    public ExportScreen(Activity a,Store s,List<LibraryStore.Entry> items,Runnable done){
        activity=a;store=s;finished=done;
        Map<String,LibraryStore.Entry> unique=new LinkedHashMap<>();for(LibraryStore.Entry e:items)unique.putIfAbsent(e.uri,e);
        entries=new ArrayList<>(unique.values());if(entries.isEmpty())throw new IllegalArgumentException("请先勾选漫画");
        tree=entries.get(0).tree;label=entries.get(0).label;
    }
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
        boolean allPdf=true;for(LibraryStore.Entry entry:entries)if(!entry.format.equals("pdf"))allPdf=false;final boolean pdfOnly=allPdf;
        LinearLayout form=new LinearLayout(activity);form.setOrientation(LinearLayout.VERTICAL);int pad=(int)(20*activity.getResources().getDisplayMetrics().density);form.setPadding(pad,pad,pad,pad);
        StringBuilder preview=new StringBuilder("已选择 "+entries.size()+" 本漫画");for(int i=0;i<Math.min(3,entries.size());i++){LibraryStore.Entry e=entries.get(i);String title=(e.id.isEmpty()?"":"JM"+e.id+" · ")+e.title;preview.append("\n").append(title.length()>100?title.substring(0,100)+"…":title);}if(entries.size()>3)preview.append("\n……另 ").append(entries.size()-3).append(" 本");
        TextView selected=new TextView(activity);selected.setText(preview);form.addView(selected);
        TextView hint=new TextView(activity);hint.setText("支持 PDF、ZIP 和图片文件夹之间的格式转换，保留源文件。PDF 转图片可能损失画质，所有页面归为一个章节。");form.addView(hint);
        TextView batchHint=new TextView(activity);batchHint.setText("使用同一格式和目录，逐本独立导出；单本失败继续其余漫画。同名文件不覆盖。停止后保留已完成的导出结果。");form.addView(batchHint);
        RadioGroup formats=new RadioGroup(activity);RadioButton pdf=new RadioButton(activity),zip=new RadioButton(activity),images=new RadioButton(activity);pdf.setId(android.view.View.generateViewId());zip.setId(android.view.View.generateViewId());images.setId(android.view.View.generateViewId());pdf.setText("PDF");zip.setText("ZIP 压缩包");images.setText("图片文件夹");formats.addView(pdf);formats.addView(zip);formats.addView(images);formats.check(pdfOnly?images.getId():pdf.getId());form.addView(formats);
        CheckBox numeric=new CheckBox(activity);numeric.setText("仅使用编号命名（分章节导出时附加章节序号）");form.addView(numeric);
        TextView layout=new TextView(activity);layout.setText("ZIP 和图片文件夹仅保存图片；多章节按章节分文件夹保存。");form.addView(layout);
        CheckBox split=new CheckBox(activity);split.setText("按章节分别导出 PDF（未勾选时合并为一本）");form.addView(split);
        formats.setOnCheckedChangeListener((g,id)->{split.setEnabled(id==pdf.getId()&&!pdfOnly);numeric.setEnabled(id!=images.getId());});
        split.setEnabled(pdf.isChecked()&&!pdfOnly);numeric.setEnabled(!images.isChecked());
        destination=new TextView(activity);destination.setText(label);form.addView(destination);
        Button choose=new ActionButton(activity);choose.setText("选择导出目录");choose.setOnClickListener(v->{pending=this;try{activity.startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION|Intent.FLAG_GRANT_PREFIX_URI_PERMISSION),DIRECTORY_REQUEST);}catch(Exception e){pending=null;error("系统目录选择器不可用");}});form.addView(choose);
        Button app=new ActionButton(activity);app.setText("导出到应用目录");app.setOnClickListener(v->{tree="";label="应用下载目录";destination.setText(label);});form.addView(app);
        ScrollView scroll=new ScrollView(activity);scroll.addView(form);
        dialog=new AlertDialog.Builder(activity).setTitle("导出漫画 · "+entries.size()+" 本").setView(scroll).setNegativeButton("取消",null).setPositiveButton("开始导出",null).create();
        dialog.setOnDismissListener(d->{if(pending==this)pending=null;});
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            synchronized(store){if(store.running||store.libraryBusy){error("请先暂停下载，并等待其他文件操作完成");return;}for(Store.Task t:store.snapshot())if(t.status.equals("running")||t.status.equals("resetting")){error("下载正在停止，请稍后重试");return;}store.libraryBusy=true;}
            String format=pdf.isChecked()?"pdf":zip.isChecked()?"zip":"images",outputTree=tree,outputLabel=label;boolean numbered=numeric.isChecked()&&!images.isChecked(),separate=split.isChecked()&&pdf.isChecked();dialog.dismiss();
            AtomicBoolean cancelled=new AtomicBoolean();ProgressDialog progress=new ProgressDialog(activity);progress.setTitle("导出漫画 · "+entries.size()+" 本");progress.setMessage("正在读取…");progress.setCancelable(false);progress.setButton(DialogInterface.BUTTON_NEGATIVE,"停止导出",(DialogInterface.OnClickListener)null);progress.show();
            progress.getButton(DialogInterface.BUTTON_NEGATIVE).setOnClickListener(stop->{cancelled.set(true);progress.getButton(DialogInterface.BUTTON_NEGATIVE).setEnabled(false);progress.setMessage("正在停止，已完成的导出结果将保留…");});
            new Thread(()->{
                String result;
                try{BatchExporter.Result done=BatchExporter.export(activity,entries,outputTree,outputLabel,format,numbered,separate,cancelled::get,message->activity.runOnUiThread(()->{if(progress.isShowing()&&!cancelled.get())progress.setMessage(message);}));
                    StringBuilder summary=new StringBuilder(done.summary()+"\n保存到："+outputLabel+"\n源文件已保留。");
                    for(String warning:done.warnings)summary.append("\n\n").append(warning);
                    for(String failure:done.errors.subList(0,Math.min(20,done.errors.size())))summary.append("\n\n").append(failure);
                    if(done.errors.size()>20)summary.append("\n……另 ").append(done.errors.size()-20).append(" 本失败");result=summary.toString();
                }catch(Exception e){result="导出未完成："+e.getMessage();}finally{store.libraryBusy=false;}
                String message=result;activity.runOnUiThread(()->{progress.dismiss();if(!activity.isFinishing()&&!activity.isDestroyed()){finished.run();error(message);}});
            },"album-export").start();
        }));dialog.show();
    }
}
