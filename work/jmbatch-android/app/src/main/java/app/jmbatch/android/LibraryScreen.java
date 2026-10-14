package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.text.*;
import android.view.*;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Searchable multiselect library; storage work never runs on the UI thread. */
public final class LibraryScreen {
    private final Activity activity;
    private final Store store;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final AtomicBoolean cancelled=new AtomicBoolean();
    private final Set<String> selected=new HashSet<>();
    private LibraryStore library;
    private Dialog dialog;
    private EditText query;
    private CheckBox favorites;
    private TextView status;
    private ListView list;
    private Button stop;
    private ArrayAdapter<String> adapter;
    private List<LibraryStore.Entry> entries=new ArrayList<>();
    private boolean busy;
    private int generation;
    private String filter="",report="";
    private volatile CancellationSignal scanSignal;
    public LibraryScreen(Activity activity,Store store){this.activity=activity;this.store=store;}
    private int dp(int n){return (int)(n*activity.getResources().getDisplayMetrics().density);}
    private boolean visible(){return dialog!=null&&dialog.isShowing()&&!activity.isFinishing()&&!activity.isDestroyed();}
    private String title(LibraryStore.Entry e){return e.id.isEmpty()?e.title:"JM"+e.id+" · "+e.title;}
    private Button button(String text,Runnable action){Button b=new Button(activity);b.setText(text);b.setTextSize(12);b.setOnClickListener(v->{if(!busy)action.run();});return b;}
    private void row(LinearLayout body,Button... buttons){LinearLayout row=new LinearLayout(activity);for(Button b:buttons)row.addView(b,new LinearLayout.LayoutParams(0,-2,1));body.addView(row);}
    public void show(){
        LinearLayout body=new LinearLayout(activity);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(12),dp(12),dp(12),dp(8));
        TextView heading=new TextView(activity);heading.setText("已下载漫画 / 收藏");heading.setTextSize(21);body.addView(heading);
        TextView hint=new TextView(activity);hint.setText("图片目录 / PDF / ZIP。选择图片漫画可导出，长按可打开或分享。");hint.setTextSize(12);body.addView(hint);
        query=new EditText(activity);query.setSingleLine(true);query.setHint("搜索编号 / 标题");body.addView(query);
        LinearLayout tools=new LinearLayout(activity);favorites=new CheckBox(activity);favorites.setText("只看收藏");tools.addView(favorites,new LinearLayout.LayoutParams(0,-2,1));tools.addView(button("扫描目录",this::scan));tools.addView(button("刷新",this::load));body.addView(tools);
        row(body,button("全选结果",()->select(0)),button("反选",()->select(1)),button("清空选择",()->select(2)));
        status=new TextView(activity);status.setTextSize(12);body.addView(status);
        list=new ListView(activity);list.setChoiceMode(ListView.CHOICE_MODE_MULTIPLE);adapter=new ArrayAdapter<>(activity,android.R.layout.simple_list_item_multiple_choice,new ArrayList<>());list.setAdapter(adapter);
        body.addView(list,new LinearLayout.LayoutParams(-1,0,1));
        list.setOnItemClickListener((p,v,position,id)->{if(busy||position>=entries.size())return;String uri=entries.get(position).uri;if(list.isItemChecked(position))selected.add(uri);else selected.remove(uri);counts();});
        list.setOnItemLongClickListener((p,v,position,id)->{if(!busy&&position<entries.size())details(entries.get(position));return true;});
        row(body,button("批量收藏",()->favorite(true)),button("取消收藏",()->favorite(false)),button("打开 / 详情",()->{List<LibraryStore.Entry> items=selection();if(items.size()==1)details(items.get(0));else message("请选择一项查看详情");}));
        row(body,button("导出",()->{List<LibraryStore.Entry> items=selection();if(items.size()==1)new ExportScreen(activity,store,items.get(0)).show();else message("请选择一本图片漫画导出");}),button("删除文件",()->confirmRemove(true)),button("仅移除记录",()->confirmRemove(false)));
        stop=new Button(activity);stop.setText("停止操作");stop.setTextSize(12);stop.setEnabled(false);stop.setOnClickListener(v->cancel());
        row(body,stop,button("关闭",()->dialog.dismiss()));
        dialog=new Dialog(activity);dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);dialog.setContentView(body);
        dialog.setOnDismissListener(d->{generation++;cancel();worker.shutdown();});dialog.show();dialog.getWindow().setLayout(-1,(int)(activity.getResources().getDisplayMetrics().heightPixels*0.93));dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        query.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int st,int c,int a){}public void onTextChanged(CharSequence s,int st,int before,int count){load();}public void afterTextChanged(Editable e){}});
        favorites.setOnCheckedChangeListener((b,c)->load());load();
    }
    private void cancel(){cancelled.set(true);if(scanSignal!=null)scanSignal.cancel();}
    private void counts(){status.setText("共 "+entries.size()+" 项，已选 "+selected.size()+" 项"+(report.isEmpty()?"":"\n"+report));}
    private void select(int mode){for(int i=0;i<entries.size();i++){String uri=entries.get(i).uri;boolean checked=mode==0||(mode==1&&!selected.contains(uri));if(checked)selected.add(uri);else selected.remove(uri);list.setItemChecked(i,checked);}counts();}
    private List<LibraryStore.Entry> selection(){List<LibraryStore.Entry> result=new ArrayList<>();for(LibraryStore.Entry e:entries)if(selected.contains(e.uri))result.add(e);return result;}
    private void load(){
        if(!visible()||busy)return;
        final int ticket=++generation;String search=query.getText().toString();boolean only=favorites.isChecked();String nextFilter=search+"|"+only;
        if(!filter.equals(nextFilter)){selected.clear();filter=nextFilter;}status.setText("正在读取…");list.setEnabled(false);
        worker.execute(()->{
            try{
                library=LibraryStore.get(activity);library.sync(store.snapshot());List<LibraryStore.Entry> result=library.list(search,only);
                main.post(()->{if(!visible()||ticket!=generation)return;entries=result;Set<String> present=new HashSet<>();adapter.clear();list.clearChoices();for(LibraryStore.Entry e:result){present.add(e.uri);adapter.add((e.favorite?"★ ":"")+title(e)+"\n"+e.format.toUpperCase(Locale.ROOT)+" · "+e.label);}selected.retainAll(present);for(int i=0;i<entries.size();i++)list.setItemChecked(i,selected.contains(entries.get(i).uri));adapter.notifyDataSetChanged();list.setEnabled(true);counts();});
            }catch(Exception error){main.post(()->{if(visible()&&ticket==generation){list.setEnabled(true);status.setText(error.getMessage());}});}
        });
    }
    private interface Operation{String run()throws Exception;}
    private void perform(Operation operation,Runnable success){
        if(busy||!visible())return;busy=true;generation++;cancelled.set(false);stop.setEnabled(true);list.setEnabled(false);query.setEnabled(false);favorites.setEnabled(false);dialog.setCancelable(false);status.setText("正在处理…");
        worker.execute(()->{String failure=null,result="";try{library=LibraryStore.get(activity);result=operation.run();}catch(OperationCanceledException | CancellationException e){result="操作已取消，未导入文件";}catch(SecurityException e){failure="目录授权失效或没有写入权限，请重新选择原保存目录授权后重试。";}catch(Exception e){failure=e.getMessage()==null?e.getClass().getSimpleName():e.getMessage();}
            final String error=failure,done=result;main.post(()->{busy=false;scanSignal=null;if(!visible())return;stop.setEnabled(false);list.setEnabled(true);query.setEnabled(true);favorites.setEnabled(true);dialog.setCancelable(true);report=error==null?done:"操作未完成";if(error!=null)message(error);else if(success!=null)success.run();load();});});
    }
    private void message(String text){if(visible())new AlertDialog.Builder(activity).setMessage(text).setPositiveButton("知道了",null).show();}
    private void scan(){
        String tree=store.settings.outputUri,label=store.settings.outputLabel;
        new AlertDialog.Builder(activity).setTitle("扫描保存目录？").setMessage(label+"\n导入本目录下的 JM Batch 图片目录和非空 PDF / ZIP；图片目录按清单验证，重复项保留收藏和标题。\n其他目录请先在首页选择后再扫描。").setNegativeButton("返回",null).setPositiveButton("开始扫描",(d,w)->perform(()->{
            CancellationSignal signal=new CancellationSignal();scanSignal=signal;if(cancelled.get())signal.cancel();
            LibraryScanner.Result found=LibraryScanner.scan(activity,tree,label,signal);if(cancelled.get())throw new OperationCanceledException();int added=library.importFound(found.entries);
            return "扫描完成：新增 "+added+" 项，已存在 "+(found.entries.size()-added)+" 项，跳过 "+found.skipped+" 项。";
        },null)).show();
    }
    private void favorite(boolean value){List<LibraryStore.Entry> items=selection();if(items.isEmpty()){message("请先勾选漫画");return;}perform(()->"已更新 "+library.setFavorites(items,value)+" 项收藏。",null);}
    private void confirmRemove(boolean delete){
        List<LibraryStore.Entry> items=selection();if(items.isEmpty()){message("请先勾选漫画");return;}
        StringBuilder preview=new StringBuilder(delete?"永久删除所选图片目录及其全部图片，或所选 PDF / ZIP；不进入回收站。":"只移除记录和收藏，文件保留，以后可重新扫描导入。");
        for(int i=0;i<Math.min(8,items.size());i++)preview.append("\n\n").append(title(items.get(i))).append("\n").append(Uri.parse(items.get(i).uri).getLastPathSegment());if(items.size()>8)preview.append("\n……另 ").append(items.size()-8).append(" 项");
        new AlertDialog.Builder(activity).setTitle("确认处理 "+items.size()+" 项？").setMessage(preview).setNegativeButton("返回",null).setPositiveButton(delete?"删除文件":"移除记录",(d,w)->perform(()->{
            BatchOperations.Result result=library.removeMany(store,items,delete,cancelled::get,(done,total)->main.post(()->{if(visible())status.setText("正在处理 "+done+" / "+total+" 项");}));
            if(!result.errors.isEmpty()){String errors=String.join("\n",result.errors.subList(0,Math.min(20,result.errors.size())));main.post(()->message(result.summary()+"\n失败记录已保留：\n"+errors));}
            return result.summary();
        },null)).show();
    }
    private void details(LibraryStore.Entry entry){
        if(entry.format.equals("images")){AlbumScreen.show(activity,store,entry);return;}
        new AlertDialog.Builder(activity).setTitle(title(entry)).setItems(new String[]{"打开文件","分享文件",entry.favorite?"取消收藏":"加入收藏","系统文件管理器打开目录","软件内查看目录"},(d,index)->{
            if(index==0||index==1)perform(()->{library.check(entry);return "";},()->open(entry,index==1));
            else if(index==2)perform(()->{library.favorite(entry);return "已更新收藏";},null);
            else if(index==3)new SavedDirectory(activity,entry.tree,entry.label).openExternal();
            else new SavedDirectory(activity,entry.tree,entry.label).show();
        }).setNegativeButton("关闭",null).show();
    }
    private void open(LibraryStore.Entry entry,boolean share){
        Uri uri=Uri.parse(entry.uri);String mime=entry.format.equals("pdf")?"application/pdf":"application/zip";
        Intent intent=new Intent(share?Intent.ACTION_SEND:Intent.ACTION_VIEW).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("漫画",uri));
        if(share){intent.setType(mime);intent.putExtra(Intent.EXTRA_STREAM,uri);}else intent.setDataAndType(uri,mime);
        try{activity.startActivity(Intent.createChooser(intent,share?"分享文件":"打开文件"));}catch(Exception e){message("没有支持此格式的应用，或文件权限不可用。");}
    }
}
