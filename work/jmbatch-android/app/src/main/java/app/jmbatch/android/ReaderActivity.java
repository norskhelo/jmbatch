package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.graphics.*;
import android.os.*;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import android.util.LruCache;
import org.json.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

/** Internal reader with recycled continuous pages and single-page gestures. */
public final class ReaderActivity extends Activity {
    public static void open(Activity activity,LibraryStore.Entry entry){
        try{activity.startActivity(new Intent(activity,ReaderActivity.class).putExtra("entry",entry.json().toString()));}
        catch(Exception error){new AlertDialog.Builder(activity).setMessage("无法打开阅读器："+error.getMessage()).setPositiveButton("关闭",null).show();}
    }
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ThreadPoolExecutor worker=new ThreadPoolExecutor(1,1,0L,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(12));
    private final ExecutorService libraryWorker=Executors.newSingleThreadExecutor();
    private final LruCache<String,Bitmap> cache=new LruCache<String,Bitmap>(32*1024*1024){protected int sizeOf(String key,Bitmap value){return value.getByteCount();}};
    private final Set<String> pending=new HashSet<>();
    private final Map<Integer,String> errors=new HashMap<>();
    private final TreeSet<Integer> marks=new TreeSet<>();
    private LibraryStore.Entry entry;
    private ReaderSource source;
    private int[] chapters,pageNumbers;
    private List<Integer> starts;
    private int page;
    private volatile int generation;
    private boolean scroll=true,ready,stateWritable=true,favoriteBusy;
    private volatile boolean closed;
    private FrameLayout viewport;
    private ListView list;
    private PageRow single;
    private TextView status;
    private Button chapterButton,favoriteButton,modeButton,markButton;
    private BaseAdapter adapter;
    private SharedPreferences history;
    private final Runnable savePosition=()->save();

    private int dp(int value){return (int)(value*getResources().getDisplayMetrics().density);}
    private Button button(String title,Runnable action){Button result=new Button(this);result.setText(title);result.setTextSize(12);result.setPadding(dp(4),0,dp(4),0);result.setOnClickListener(v->action.run());return result;}
    private void row(LinearLayout body,View...views){LinearLayout row=new LinearLayout(this);for(View view:views)row.addView(view,new LinearLayout.LayoutParams(0,dp(46),1));body.addView(row);}
    private void message(String text){if(!closed)new AlertDialog.Builder(this).setMessage(text).setPositiveButton("关闭",null).show();}
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        try{entry=new LibraryStore.Entry(new JSONObject(getIntent().getStringExtra("entry")));}catch(Exception error){finish();return;}
        history=getSharedPreferences("reader-history",MODE_PRIVATE);
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(6),dp(4),dp(6),dp(4));
        TextView title=new TextView(this);title.setText(entry.title);title.setTextSize(18);title.setSingleLine(true);title.setEllipsize(android.text.TextUtils.TruncateAt.END);body.addView(title);
        chapterButton=button("章节",this::chooseChapter);favoriteButton=button("☆ 收藏",this::favorite);modeButton=button("模式：滚动",this::toggleMode);
        row(body,button("返回",this::finish),chapterButton,favoriteButton,modeButton);
        markButton=button("添加书签",this::toggleMark);row(body,button("上一章",()->chapterStep(-1)),button("下一章",()->chapterStep(1)),markButton,button("书签列表",this::bookmarks));
        viewport=new FrameLayout(this);viewport.setBackgroundColor(Color.rgb(32,37,44));body.addView(viewport,new LinearLayout.LayoutParams(-1,0,1));
        status=new TextView(this);status.setText("正在读取漫画…\n外部 ZIP 首次打开需准备缓存，可返回取消。");status.setTextSize(12);status.setGravity(Gravity.CENTER);body.addView(status);
        row(body,button("‹ 上一页",()->go(page-1)),button("页码 / 跳页",this::jumpPage),button("下一页 ›",()->go(page+1)));
        setContentView(body);
        worker.execute(()->{
            try{
                LibraryStore library=LibraryStore.get(this);Store store=Store.get(this);
                synchronized(store){library.sync(new ArrayList<>(store.tasks));}
                for(LibraryStore.Entry item:library.list("",false))if(item.uri.equals(entry.uri)){entry=item;break;}
                source=new ReaderSource(getApplicationContext(),entry,()->{if(closed||Thread.currentThread().isInterrupted())throw new InterruptedIOException("已关闭阅读器");});
                library.importFound(Collections.singletonList(entry));
                main.post(()->{
                    if(closed)return;chapters=source.chapters;pageNumbers=source.pageNumbers;starts=ReaderRules.starts(chapters);restore();ready=true;viewport.post(()->{if(!closed){buildPages();update();}});
                });
            }catch(Exception|OutOfMemoryError error){main.post(()->{if(!closed){status.setText("无法阅读："+error.getMessage());message("无法阅读，请检查文件和目录授权："+error.getMessage());}});}
        });
    }
    private void restore(){
        try{
            JSONObject saved=new JSONObject(history.getString(entry.uri,"{}"));page=ReaderRules.clamp(saved.optInt("page",0),chapters.length);scroll=!saved.optString("mode","scroll").equals("paged");
            JSONArray items=saved.optJSONArray("bookmarks");if(items!=null)for(int i=0;i<items.length();i++){int mark=items.getInt(i);if(mark>=0&&mark<chapters.length)marks.add(mark);}
        }catch(Exception error){stateWritable=false;message("阅读记录损坏，原记录保留，本次不覆盖。"+error.getMessage());}
    }
    private void save(){
        if(!ready||!stateWritable)return;
        try{
            JSONArray items=new JSONArray();for(int mark:marks)items.put(mark);
            String value=new JSONObject().put("page",page).put("mode",scroll?"scroll":"paged").put("bookmarks",items).toString();
            if(!history.edit().putString(entry.uri,value).commit())throw new IOException("存储不可写");
        }catch(Exception error){stateWritable=false;message("阅读记录未保存："+error.getMessage());}
    }
    private void scheduleSave(){main.removeCallbacks(savePosition);main.postDelayed(savePosition,700);}
    private void update(){
        favoriteButton.setText(entry.favorite?"★ 已收藏":"☆ 收藏");modeButton.setText(scroll?"模式：滚动":"模式：左右");markButton.setText(marks.contains(page)?"移除书签":"添加书签");
        if(!ready)return;
        int chapter=ReaderRules.chapter(starts,page),end=chapter+1<starts.size()?starts.get(chapter+1):chapters.length;
        chapterButton.setText("第 "+chapters[page]+" 章");
        status.setText("本章 "+(page-starts.get(chapter)+1)+"/"+(end-starts.get(chapter))+" 页 · 总页码 "+(page+1)+"/"+chapters.length+(entry.format.equals("pdf")?" · PDF 单章节":"")+(!scroll?"\n左右滑动或点击两侧翻页":""));
    }
    private void buildPages(){
        if(!ready||closed)return;
        generation++;worker.getQueue().clear();pending.clear();errors.clear();cache.evictAll();viewport.removeAllViews();
        if(scroll){
            list=new ListView(this);list.setDividerHeight(dp(8));list.setBackgroundColor(Color.rgb(32,37,44));
            adapter=new BaseAdapter(){
                public int getCount(){return chapters.length;}public Object getItem(int position){return position;}public long getItemId(int position){return position;}
                public View getView(int position,View convert,ViewGroup parent){PageRow row=convert instanceof PageRow?(PageRow)convert:new PageRow();bind(row,position);return row;}
            };
            list.setAdapter(adapter);viewport.addView(list,new FrameLayout.LayoutParams(-1,-1));list.setSelection(page);
            list.setOnScrollListener(new AbsListView.OnScrollListener(){
                public void onScrollStateChanged(AbsListView view,int state){if(state==SCROLL_STATE_IDLE)loadVisible();}
                public void onScroll(AbsListView view,int first,int count,int total){if(count>0){page=first;update();scheduleSave();}}
            });
        }else{
            list=null;single=new PageRow();viewport.addView(single,new FrameLayout.LayoutParams(-1,-1));
            final GestureDetector gestures=new GestureDetector(this,new GestureDetector.SimpleOnGestureListener(){
                public boolean onDown(android.view.MotionEvent event){return true;}
                public boolean onSingleTapUp(android.view.MotionEvent event){if(event.getX()<viewport.getWidth()*.35)go(page-1);else if(event.getX()>viewport.getWidth()*.65)go(page+1);return true;}
                public boolean onFling(android.view.MotionEvent start,android.view.MotionEvent end,float vx,float vy){if(start!=null&&Math.abs(end.getX()-start.getX())>dp(45)&&Math.abs(vx)>Math.abs(vy)){go(page+(end.getX()<start.getX()?1:-1));return true;}return false;}
            });
            single.setOnTouchListener((v,event)->gestures.onTouchEvent(event));bind(single,page);
        }
    }
    private final class PageRow extends LinearLayout {
        final ImageView image;final TextView label;
        PageRow(){super(ReaderActivity.this);setOrientation(VERTICAL);setGravity(Gravity.CENTER);image=new ImageView(ReaderActivity.this);image.setScaleType(ImageView.ScaleType.FIT_CENTER);label=new TextView(ReaderActivity.this);label.setTextColor(Color.LTGRAY);label.setGravity(Gravity.CENTER);label.setTextSize(12);addView(label,new LinearLayout.LayoutParams(-1,dp(25)));addView(image,new LinearLayout.LayoutParams(-1,dp(300)));}
    }
    private void bind(PageRow row,int index){
        int width=Math.max(100,viewport.getWidth()-dp(8)),height=scroll?0:Math.max(100,viewport.getHeight()-dp(30));
        String key=generation+":"+index;row.setTag(key);row.image.setImageDrawable(null);
        Bitmap bitmap=cache.get(key);row.label.setText(errors.containsKey(index)?"本页读取失败，可继续翻页："+errors.get(index):"第 "+(index+1)+" 页"+(bitmap==null?" · 正在加载…":""));
        LinearLayout.LayoutParams params=(LinearLayout.LayoutParams)row.image.getLayoutParams();params.height=scroll?(bitmap==null?(int)(width*1.4):Math.max(1,(int)((long)bitmap.getHeight()*width/bitmap.getWidth()))):height;row.image.setLayoutParams(params);
        if(bitmap!=null){row.image.setImageBitmap(bitmap);return;}
        if(errors.containsKey(index)||pending.contains(key)||closed)return;
        pending.add(key);final int ticket=generation;
        try{worker.execute(()->{
            if(closed||ticket!=generation)return;
            Bitmap result=null;String failure=null;
            try{result=source.render(index,width,height);}catch(Exception|OutOfMemoryError error){failure=error.getMessage()==null?"页面无法解码":error.getMessage();}
            final Bitmap loaded=result;final String error=failure;
            main.post(()->{
                pending.remove(key);if(closed||ticket!=generation){if(loaded!=null)loaded.recycle();return;}
                if(loaded!=null)cache.put(key,loaded);else errors.put(index,error);
                loadVisible();
            });
        });}catch(RejectedExecutionException error){pending.remove(key);}
    }
    private void loadVisible(){
        if(closed||!ready)return;
        if(scroll&&list!=null){for(int i=0;i<list.getChildCount();i++){View row=list.getChildAt(i);if(row instanceof PageRow)bind((PageRow)row,list.getFirstVisiblePosition()+i);}}
        else if(single!=null)bind(single,page);
    }
    private void go(int target){
        if(!ready)return;
        page=ReaderRules.clamp(target,chapters.length);
        if(!scroll){worker.getQueue().clear();pending.clear();}
        if(scroll&&list!=null)list.setSelection(page);else if(single!=null)bind(single,page);
        update();scheduleSave();
    }
    private void chapterStep(int delta){if(ready)go(starts.get(ReaderRules.clamp(ReaderRules.chapter(starts,page)+delta,starts.size())));}
    private void chooseChapter(){
        if(!ready)return;
        String[] labels=new String[starts.size()];for(int i=0;i<labels.length;i++)labels[i]="第 "+chapters[starts.get(i)]+" 章 · "+((i+1<starts.size()?starts.get(i+1):chapters.length)-starts.get(i))+" 页";
        new AlertDialog.Builder(this).setTitle("章节切换").setSingleChoiceItems(labels,ReaderRules.chapter(starts,page),(dialog,index)->{dialog.dismiss();go(starts.get(index));}).setNegativeButton("关闭",null).show();
    }
    private void toggleMode(){if(ready){scroll=!scroll;buildPages();update();save();}}
    private void jumpPage(){
        if(!ready)return;
        EditText input=new EditText(this);input.setInputType(InputType.TYPE_CLASS_NUMBER);input.setText(String.valueOf(page+1));input.selectAll();
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("跳到总页码（1–"+chapters.length+"）").setView(input).setPositiveButton("跳转",null).setNegativeButton("取消",null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{int target=Integer.parseInt(input.getText().toString());if(target<1||target>chapters.length)throw new NumberFormatException();go(target-1);dialog.dismiss();}catch(NumberFormatException error){input.setError("请输入有效页码");}}));dialog.show();
    }
    private void favorite(){
        if(!ready||favoriteBusy)return;favoriteBusy=true;favoriteButton.setEnabled(false);
        try{libraryWorker.execute(()->{
            try{LibraryStore library=LibraryStore.get(this);library.favorite(entry);LibraryStore.Entry updated=null;for(LibraryStore.Entry item:library.list("",false))if(item.uri.equals(entry.uri)){updated=item;break;}final LibraryStore.Entry result=updated;
                main.post(()->{if(!closed){if(result!=null)entry=result;favoriteBusy=false;favoriteButton.setEnabled(true);update();}});
            }catch(Exception error){main.post(()->{if(!closed){favoriteBusy=false;favoriteButton.setEnabled(true);message("收藏失败："+error.getMessage());}});}
        });}catch(RejectedExecutionException error){favoriteBusy=false;favoriteButton.setEnabled(true);message("页面正在加载，请稍后再试。");}
    }
    private void toggleMark(){if(!ready)return;if(!marks.add(page))marks.remove(page);save();update();}
    private void bookmarks(){
        if(!ready)return;
        if(marks.isEmpty()){message("暂无书签，阅读时点击“添加书签”保存当前页。");return;}
        Integer[] pages=marks.toArray(new Integer[0]);String[] labels=new String[pages.length];for(int i=0;i<pages.length;i++)labels[i]="第 "+chapters[pages[i]]+" 章 · 第 "+pageNumbers[pages[i]]+" 页（总第 "+(pages[i]+1)+" 页）";
        new AlertDialog.Builder(this).setTitle("书签").setItems(labels,(dialog,index)->new AlertDialog.Builder(this).setTitle(labels[index]).setPositiveButton("跳转",(d,w)->go(pages[index])).setNeutralButton("删除书签",(d,w)->{marks.remove(pages[index]);save();update();}).setNegativeButton("取消",null).show()).setNegativeButton("关闭",null).show();
    }
    @Override public boolean onKeyDown(int code,android.view.KeyEvent event){if(ready&&(code==KeyEvent.KEYCODE_DPAD_LEFT||code==KeyEvent.KEYCODE_PAGE_UP)){go(page-1);return true;}if(ready&&(code==KeyEvent.KEYCODE_DPAD_RIGHT||code==KeyEvent.KEYCODE_PAGE_DOWN)){go(page+1);return true;}return super.onKeyDown(code,event);}
    @Override protected void onPause(){main.removeCallbacks(savePosition);save();super.onPause();}
    @Override protected void onDestroy(){
        closed=true;main.removeCallbacks(savePosition);worker.getQueue().clear();
        worker.execute(()->{if(source!=null)source.close();});worker.shutdown();libraryWorker.shutdown();cache.evictAll();super.onDestroy();
    }
}
