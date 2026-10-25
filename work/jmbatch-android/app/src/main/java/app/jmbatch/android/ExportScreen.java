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
        LinearLayout form=Ui.column(activity);TextView title=Ui.heading(activity,"导出为");title.setGravity(android.view.Gravity.CENTER);title.setPadding(0,Ui.dp(activity,4),0,Ui.dp(activity,6));form.addView(title);Ui.gap(form,6);
        RadioGroup formats=new RadioGroup(activity);formats.setOrientation(RadioGroup.HORIZONTAL);formats.setGravity(android.view.Gravity.CENTER);RadioButton pdf=new RadioButton(activity),zip=new RadioButton(activity),images=new RadioButton(activity);pdf.setId(android.view.View.generateViewId());zip.setId(android.view.View.generateViewId());images.setId(android.view.View.generateViewId());pdf.setText("pdf");zip.setText("zip");formats.addView(pdf,new RadioGroup.LayoutParams(-2,-2));RadioGroup.LayoutParams second=new RadioGroup.LayoutParams(-2,-2);second.leftMargin=Ui.dp(activity,68);formats.addView(zip,second);pdf.setButtonTintList(android.content.res.ColorStateList.valueOf(Ui.MUTED));zip.setButtonTintList(android.content.res.ColorStateList.valueOf(Ui.MUTED));formats.check(pdfOnly?zip.getId():pdf.getId());form.addView(formats);
        RadioButton numeric=new RadioButton(activity){@Override public void toggle(){setChecked(!isChecked());}};
        CheckBox split=new CheckBox(activity);destination=new TextView(activity);destination.setText(label);
        numeric.setText("只保留编号");numeric.setTextColor(Ui.INK);numeric.setTextSize(16);numeric.setButtonTintList(android.content.res.ColorStateList.valueOf(Ui.MUTED));
        LinearLayout.LayoutParams numericLayout=new LinearLayout.LayoutParams(-2,Ui.dp(activity,48));numericLayout.gravity=android.view.Gravity.CENTER_HORIZONTAL;numericLayout.topMargin=Ui.dp(activity,4);form.addView(numeric,numericLayout);
        Ui.gap(form,12);dialog=Ui.modal(activity,form,false,14,14);Button confirm=Ui.button(activity,"确认",()->{});Ui.primary(confirm);form.addView(Ui.pair(activity,confirm,Ui.button(activity,"取消",dialog::dismiss)));
        dialog.setOnDismissListener(d->{if(pending==this)pending=null;});
        confirm.setOnClickListener(v->{
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
        });dialog.show();
    }
}
