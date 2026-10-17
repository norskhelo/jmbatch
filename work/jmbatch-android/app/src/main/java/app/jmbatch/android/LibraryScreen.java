package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.content.res.TypedArray;
import android.util.LruCache;
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
    private BaseAdapter adapter;
    private final ThreadPoolExecutor coverWorker=new ThreadPoolExecutor(1,1,0L,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(24));
    private static final class Cover {final Bitmap bitmap;Cover(Bitmap bitmap){this.bitmap=bitmap;}}
    private final LruCache<String,Cover> coverCache=new LruCache<String,Cover>(8*1024*1024){protected int sizeOf(String key,Cover cover){return cover.bitmap==null?1024:cover.bitmap.getByteCount();}};
    private final Set<String> coverPending=new HashSet<>();
    private int coverGeneration;
    private List<LibraryStore.Entry> entries=new ArrayList<>();
    private boolean busy;
    private int generation;
    private String filter="",report="";
    private volatile CancellationSignal scanSignal;
    public LibraryScreen(Activity activity,Store store){this.activity=activity;this.store=store;}
    private int dp(int n){return (int)(n*activity.getResources().getDisplayMetrics().density);}
    private boolean visible(){return dialog!=null&&dialog.isShowing()&&!activity.isFinishing()&&!activity.isDestroyed();}
    private String title(LibraryStore.Entry e){return e.id.isEmpty()?e.title:"JM"+e.id+" · "+e.title;}
    private Button button(String text,Runnable action){Button b=new ActionButton(activity);b.setText(text);b.setTextSize(12);b.setOnClickListener(v->{if(!busy)action.run();});return b;}
    private void row(LinearLayout body,Button... buttons){body.addView(new ActionRow(activity,buttons));}
    public void show(){
        LinearLayout root=new LinearLayout(activity);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(12),dp(12),dp(12),dp(8));
        LinearLayout body=new LinearLayout(activity);body.setOrientation(LinearLayout.VERTICAL);
        TextView heading=new TextView(activity);heading.setText("漫画库");heading.setTextSize(21);body.addView(heading);
        TextView hint=new TextView(activity);hint.setText("以第一页为封面。选择漫画后可阅读、导出或收藏，长按可打开或分享文件。");hint.setTextSize(12);body.addView(hint);
        query=new EditText(activity);query.setSingleLine(true);query.setHint("搜索编号或标题");body.addView(query);
        favorites=new CheckBox(activity);favorites.setText("仅显示收藏");body.addView(new ActionRow(activity,favorites,button("扫描保存目录",this::scan),button("刷新",this::load)));
        row(body,button("全选",()->select(0)),button("反选",()->select(1)),button("取消选择",()->select(2)));
        status=new TextView(activity);status.setTextSize(12);body.addView(status);
        list=new ListView(activity);list.setChoiceMode(ListView.CHOICE_MODE_MULTIPLE);adapter=new CoverAdapter();list.setAdapter(adapter);
        list.setOnScrollListener(new AbsListView.OnScrollListener(){public void onScroll(AbsListView v,int first,int count,int total){}public void onScrollStateChanged(AbsListView v,int state){if(state==SCROLL_STATE_IDLE)adapter.notifyDataSetChanged();}});
        root.addView(new ControlScroll(activity,body));root.addView(list,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout actions=new LinearLayout(activity);actions.setOrientation(LinearLayout.VERTICAL);
        list.setOnItemClickListener((p,v,position,id)->{if(busy||position>=entries.size())return;String uri=entries.get(position).uri;if(list.isItemChecked(position))selected.add(uri);else selected.remove(uri);counts();});
        list.setOnItemLongClickListener((p,v,position,id)->{if(!busy&&position<entries.size())details(entries.get(position));return true;});
        row(actions,button("批量收藏",()->favorite(true)),button("取消收藏",()->favorite(false)),button("开始阅读",()->{List<LibraryStore.Entry> items=selection();if(items.size()==1){dialog.dismiss();ReaderActivity.open(activity,items.get(0));}else message("请选择一本漫画阅读");}));
        row(actions,button("导出漫画",()->{List<LibraryStore.Entry> items=selection();if(items.size()==1)new ExportScreen(activity,store,items.get(0)).show();else message("请选择一本漫画，再选择导出格式。");}),button("删除文件",()->confirmRemove(true)),button("仅移除记录",()->confirmRemove(false)));
        stop=new ActionButton(activity);stop.setText("停止操作");stop.setTextSize(12);stop.setEnabled(false);stop.setOnClickListener(v->cancel());
        row(actions,stop,button("关闭",()->dialog.dismiss()));root.addView(new ControlScroll(activity,actions));
        dialog=new Dialog(activity);dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);dialog.setContentView(root);
        dialog.setOnDismissListener(d->{generation++;resetCovers();cancel();worker.shutdown();coverWorker.shutdownNow();});dialog.show();dialog.getWindow().setLayout(-1,(int)(activity.getResources().getDisplayMetrics().heightPixels*0.93));dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        query.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int st,int c,int a){}public void onTextChanged(CharSequence s,int st,int before,int count){load();}public void afterTextChanged(Editable e){}});
        favorites.setOnCheckedChangeListener((b,c)->load());load();
    }
    private void resetCovers(){coverGeneration++;coverWorker.getQueue().clear();coverPending.clear();coverCache.evictAll();}
    private final class CoverRow extends LinearLayout implements Checkable {
        final ImageView image;final TextView placeholder;final CheckedTextView text;
        CoverRow(){
            super(activity);setGravity(Gravity.CENTER_VERTICAL);setPadding(dp(4),dp(8),dp(4),dp(8));
            FrameLayout frame=new FrameLayout(activity);frame.setBackgroundColor(Color.rgb(232,237,241));
            image=new ImageView(activity);image.setScaleType(ImageView.ScaleType.FIT_CENTER);frame.addView(image,new FrameLayout.LayoutParams(-1,-1));
            placeholder=new TextView(activity);placeholder.setText("暂无\n封面");placeholder.setTextSize(12);placeholder.setGravity(Gravity.CENTER);placeholder.setTextColor(Color.rgb(97,115,135));frame.addView(placeholder,new FrameLayout.LayoutParams(-1,-1));
            addView(frame,new LinearLayout.LayoutParams(dp(64),dp(86)));
            text=new CheckedTextView(activity);text.setTextSize(14);text.setMaxLines(4);text.setEllipsize(TextUtils.TruncateAt.END);text.setPadding(dp(12),0,0,0);
            TypedArray attrs=activity.obtainStyledAttributes(new int[]{android.R.attr.listChoiceIndicatorMultiple});text.setCheckMarkDrawable(attrs.getDrawable(0));attrs.recycle();
            addView(text,new LinearLayout.LayoutParams(0,-2,1));
        }
        public boolean isChecked(){return text.isChecked();}public void setChecked(boolean value){text.setChecked(value);}public void toggle(){setChecked(!isChecked());}
    }
    private final class CoverAdapter extends BaseAdapter {
        public int getCount(){return entries.size();}public Object getItem(int position){return entries.get(position);}public long getItemId(int position){return position;}
        public View getView(int position,View recycled,ViewGroup parent){
            CoverRow row=recycled instanceof CoverRow?(CoverRow)recycled:new CoverRow();LibraryStore.Entry entry=entries.get(position);
            row.text.setText((entry.favorite?"★ ":"")+title(entry)+"\n"+entry.format.toUpperCase(Locale.ROOT)+" · "+entry.label);row.setChecked(selected.contains(entry.uri));
            Cover cover=coverCache.get(entry.uri);Bitmap bitmap=cover==null?null:cover.bitmap;
            row.image.setImageBitmap(bitmap);row.image.setContentDescription(bitmap==null?"暂无封面":"第一页封面");row.placeholder.setVisibility(bitmap==null?View.VISIBLE:View.GONE);
            if(cover==null&&!coverPending.contains(entry.uri)&&!coverWorker.isShutdown()){
                final int ticket=coverGeneration;coverPending.add(entry.uri);
                try{coverWorker.execute(()->{Bitmap result=LibraryCover.load(activity.getApplicationContext(),entry);main.post(()->{
                    if(!visible()||ticket!=coverGeneration)return;coverPending.remove(entry.uri);coverCache.put(entry.uri,new Cover(result));adapter.notifyDataSetChanged();
                });});}catch(RejectedExecutionException error){coverPending.remove(entry.uri);}
            }
            return row;
        }
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
                main.post(()->{if(!visible()||ticket!=generation)return;resetCovers();entries=result;Set<String> present=new HashSet<>();list.clearChoices();for(LibraryStore.Entry e:result)present.add(e.uri);selected.retainAll(present);for(int i=0;i<entries.size();i++)list.setItemChecked(i,selected.contains(entries.get(i).uri));adapter.notifyDataSetChanged();list.setEnabled(true);counts();});
            }catch(Exception error){main.post(()->{if(visible()&&ticket==generation){list.setEnabled(true);status.setText(error.getMessage());}});}
        });
    }
    private interface Operation{String run()throws Exception;}
    private void perform(Operation operation,Runnable success){
        if(busy||!visible())return;busy=true;generation++;cancelled.set(false);stop.setEnabled(true);list.setEnabled(false);query.setEnabled(false);favorites.setEnabled(false);dialog.setCancelable(false);status.setText("正在处理…");
        worker.execute(()->{String failure=null,result="";try{library=LibraryStore.get(activity);result=operation.run();}catch(OperationCanceledException | CancellationException e){result="操作已取消，未导入文件";}catch(SecurityException e){failure="目录授权失效或没有写入权限，请重新选择原保存目录授权后重试。";}catch(Exception e){failure=e.getMessage()==null?e.getClass().getSimpleName():e.getMessage();}
            final String error=failure,done=result;main.post(()->{busy=false;scanSignal=null;if(!visible())return;stop.setEnabled(false);list.setEnabled(true);query.setEnabled(true);favorites.setEnabled(true);dialog.setCancelable(true);report=error==null?done:"操作未完成";if(error!=null)message(error);else if(success!=null)success.run();load();});});
    }
    private void message(String text){if(visible())new AlertDialog.Builder(activity).setMessage(text).setPositiveButton("确定",null).show();}
    private void scan(){
        String tree=store.settings.outputUri,label=store.settings.outputLabel;
        new AlertDialog.Builder(activity).setTitle("扫描保存目录").setMessage(label+"\n将此目录中可识别的图片文件夹、PDF 和 ZIP 添加到漫画库。已存在的漫画保留原有标题和收藏。\n其他目录请先在首页选择后再扫描。").setNegativeButton("取消",null).setPositiveButton("开始扫描",(d,w)->perform(()->{
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
        new AlertDialog.Builder(activity).setTitle(delete?"确认删除文件":"确认移除记录").setMessage(preview).setNegativeButton("取消",null).setPositiveButton(delete?"删除文件":"移除记录",(d,w)->perform(()->{
            BatchOperations.Result result=library.removeMany(store,items,delete,cancelled::get,(done,total)->main.post(()->{if(visible())status.setText("正在处理 "+done+" / "+total+" 项");}));
            if(!result.errors.isEmpty()){String errors=String.join("\n",result.errors.subList(0,Math.min(20,result.errors.size())));main.post(()->message(result.summary()+"\n失败记录已保留：\n"+errors));}
            return result.summary();
        },null)).show();
    }
    private void details(LibraryStore.Entry entry){
        new AlertDialog.Builder(activity).setTitle(title(entry)).setItems(new String[]{"开始阅读","分享文件",entry.favorite?"取消收藏":"加入收藏","打开保存目录","应用内查看目录","导出漫画"},(d,index)->{
            if(index==0){dialog.dismiss();ReaderActivity.open(activity,entry);return;}
            if(index==1&&entry.format.equals("images")){message("图片文件夹请先导出为 ZIP 或 PDF 后分享。");return;}
            if(index==5){new ExportScreen(activity,store,entry).show();return;}
            if(index==0||index==1)perform(()->{library.check(entry);return "";},()->open(entry,index==1));
            else if(index==2)perform(()->{library.favorite(entry);return "已更新收藏";},null);
            else if(index==3)new SavedDirectory(activity,entry.tree,entry.label).openExternal();
            else new SavedDirectory(activity,entry.tree,entry.label).show();
        }).setNegativeButton("关闭",null).show();
    }
    private void open(LibraryStore.Entry entry,boolean share){
        if(!share){ReaderActivity.open(activity,entry);return;}
        Uri uri=Uri.parse(entry.uri);String mime=entry.format.equals("pdf")?"application/pdf":"application/zip";
        Intent intent=new Intent(share?Intent.ACTION_SEND:Intent.ACTION_VIEW).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("漫画",uri));
        if(share){intent.setType(mime);intent.putExtra(Intent.EXTRA_STREAM,uri);}else intent.setDataAndType(uri,mime);
        try{activity.startActivity(Intent.createChooser(intent,share?"分享文件":"打开文件"));}catch(Exception e){message("没有支持此格式的应用，或文件权限不可用。");}
    }
}
