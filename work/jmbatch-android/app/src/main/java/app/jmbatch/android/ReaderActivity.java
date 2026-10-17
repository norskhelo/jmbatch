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
    private final ReaderRequests requests=new ReaderRequests();
    private static final ExecutorService historyWorker=Executors.newSingleThreadExecutor();
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
    private ReaderPager pager;
    private String lastSaved="";
    private int viewportWidth,viewportHeight;
    private int noticeTarget=-1;
    private TextView status;
    private final Runnable loadingNotice=()->{if(!closed&&pager!=null&&pager.target()!=pager.displayed()&&cache.get(job(pager.target()).key)==null&&!errors.containsKey(pager.target()))status.setText(statusText()+"\n正在加载第 "+(pager.target()+1)+" 页…");};
    private Button chapterButton,favoriteButton,modeButton,markButton;
    private BaseAdapter adapter;
    private SharedPreferences history;
    private final Runnable savePosition=()->save();

    private int dp(int value){return (int)(value*getResources().getDisplayMetrics().density);}
    private Button button(String title,Runnable action){Button result=new ActionButton(this);result.setText(title);result.setTextSize(12);result.setOnClickListener(v->action.run());return result;}
    private void row(LinearLayout body,View...views){body.addView(new ActionRow(this,views));}
    private void message(String text){if(!closed)new AlertDialog.Builder(this).setMessage(text).setPositiveButton("关闭",null).show();}
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        try{entry=new LibraryStore.Entry(new JSONObject(getIntent().getStringExtra("entry")));}catch(Exception error){finish();return;}
        history=getSharedPreferences("reader-history",MODE_PRIVATE);
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(6),dp(4),dp(6),dp(4));
        LinearLayout controls=new LinearLayout(this);controls.setOrientation(LinearLayout.VERTICAL);
        TextView title=new TextView(this);title.setText(entry.title);title.setTextSize(18);title.setSingleLine(true);title.setEllipsize(android.text.TextUtils.TruncateAt.END);controls.addView(title);
        chapterButton=button("章节",this::chooseChapter);favoriteButton=button("☆ 收藏",this::favorite);modeButton=button("模式：滚动",this::toggleMode);
        row(controls,button("返回",this::finish),chapterButton,favoriteButton,modeButton);
        markButton=button("添加书签",this::toggleMark);row(controls,button("上一章",()->chapterStep(-1)),button("下一章",()->chapterStep(1)),markButton,button("书签列表",this::bookmarks));
        body.addView(new ControlScroll(this,controls));
        viewport=new FrameLayout(this);viewport.setBackgroundColor(Color.rgb(32,37,44));body.addView(viewport,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout navigation=new LinearLayout(this);navigation.setOrientation(LinearLayout.VERTICAL);
        status=new TextView(this);status.setText("正在读取漫画…\n外部 ZIP 首次打开需准备缓存，可返回取消。");status.setTextSize(12);status.setLines(3);status.setEllipsize(android.text.TextUtils.TruncateAt.END);status.setGravity(Gravity.CENTER);navigation.addView(status);
        row(navigation,button("‹ 上一页",()->step(-1)),button("页码 / 跳页",this::jumpPage),button("下一页 ›",()->step(1)));
        body.addView(new ControlScroll(this,navigation));
        setContentView(body);
        viewport.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{
            if(!ready||closed||r-l==0||b-t==0)return;
            if(viewportWidth!=r-l||viewportHeight!=b-t){
                viewportWidth=r-l;viewportHeight=b-t;generation++;requests.clear();errors.clear();cache.evictAll();
                if(pager!=null)pager.post(()->{if(!closed)loadVisible();});else loadVisible();
            }
        });
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
            if(value.equals(lastSaved))return;
            lastSaved=value;final String key=entry.uri;final SharedPreferences preferences=history;
            historyWorker.execute(()->{
                boolean ok=false;try{ok=preferences.edit().putString(key,value).commit();}catch(Exception ignored){}
                if(!ok)main.post(()->{stateWritable=false;if(!closed)message("阅读记录未保存：存储不可写");});
            });
        }catch(Exception error){stateWritable=false;message("阅读记录未保存："+error.getMessage());}
    }
    private void scheduleSave(){main.removeCallbacks(savePosition);main.postDelayed(savePosition,700);}
    private void update(){
        favoriteButton.setText(entry.favorite?"★ 已收藏":"☆ 收藏");modeButton.setText(scroll?"模式：滚动":"模式：左右");markButton.setText(marks.contains(page)?"移除书签":"添加书签");
        if(!ready)return;
        int chapter=ReaderRules.chapter(starts,page);
        chapterButton.setText("第 "+chapters[page]+" 章");
        status.setText(statusText()+(!scroll?"\n左右拖动或点击两侧翻页":""));
    }
    private String statusText(){
        int chapter=ReaderRules.chapter(starts,page),end=chapter+1<starts.size()?starts.get(chapter+1):chapters.length;
        return "本章 "+(page-starts.get(chapter)+1)+"/"+(end-starts.get(chapter))+" 页 · 总页码 "+(page+1)+"/"+chapters.length+(entry.format.equals("pdf")?" · PDF 单章节":"");
    }
    private void buildPages(){
        if(!ready||closed)return;
        main.removeCallbacks(loadingNotice);noticeTarget=-1;generation++;requests.clear();errors.clear();cache.evictAll();
        if(pager!=null){pager.dispose();pager=null;}viewport.removeAllViews();
        if(scroll){
            list=new ListView(this);list.setDivider(null);list.setDividerHeight(0);list.setBackgroundColor(Color.rgb(32,37,44));
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
            list=null;pager=new ReaderPager(this,chapters.length,page,new ReaderPager.Listener(){
                public Bitmap lookup(int index){return index<0||index>=chapters.length?null:cache.get(job(index).key);}
                public void requested(){planPages();}
                public void committed(int index){page=index;main.removeCallbacks(loadingNotice);update();scheduleSave();}
            });
            viewport.addView(pager,new FrameLayout.LayoutParams(-1,-1));pager.post(()->{if(!closed&&pager!=null)pager.go(page);});
        }
    }
    private final class PageRow extends FrameLayout {
        final ImageView image;final TextView label;
        PageRow(){super(ReaderActivity.this);image=new ImageView(ReaderActivity.this);image.setScaleType(ImageView.ScaleType.FIT_XY);label=new TextView(ReaderActivity.this);label.setTextColor(Color.LTGRAY);label.setGravity(Gravity.CENTER);label.setTextSize(12);addView(image,new FrameLayout.LayoutParams(-1,dp(300)));addView(label,new FrameLayout.LayoutParams(-1,-1));}
    }
    private void bind(PageRow row,int index){
        ReaderRequests.Job job=job(index);int width=job.width;
        String key=job.key;if(!key.equals(row.getTag())){row.setTag(key);row.image.setImageDrawable(null);}
        Bitmap bitmap=cache.get(key);row.label.setText(errors.containsKey(index)?"本页读取失败，可继续翻页："+errors.get(index):"第 "+(index+1)+" 页 · 正在加载…");row.label.setVisibility(bitmap==null?View.VISIBLE:View.GONE);
        // The row is exactly the fitted image height; notices overlay its placeholder.
        FrameLayout.LayoutParams params=(FrameLayout.LayoutParams)row.image.getLayoutParams();int height=bitmap==null?(int)(width*1.4):Math.max(1,(int)((long)bitmap.getHeight()*width/bitmap.getWidth()));
        if(params.height!=height){params.height=height;row.image.setLayoutParams(params);}
        if(bitmap!=null){row.image.setImageBitmap(bitmap);return;}
        if(errors.containsKey(index)||closed)return;
        requests.offer(job);pump();
    }
    private ReaderRequests.Job job(int index){return new ReaderRequests.Job(generation,index,Math.max(100,viewport.getWidth()-(scroll?0:dp(8))),scroll?0:Math.max(100,viewport.getHeight()-dp(8)));}
    private void planPages(){
        if(closed||scroll||pager==null)return;
        pager.ready();int target=pager.target();List<ReaderRequests.Job> jobs=new ArrayList<>();
        if(target!=noticeTarget){noticeTarget=target;main.removeCallbacks(loadingNotice);update();main.postDelayed(loadingNotice,180);}
        ReaderRequests.Job first=job(target);
        long estimate=Math.min(4000000L,(long)Math.min(1600,first.width)*Math.min(8192,first.height))*4;
        int limit=(int)Math.max(1,Math.min(3,32L*1024*1024/Math.max(1,estimate)));
        int[] desired=pager.busy()?new int[]{target}:new int[]{target,target+pager.direction(),target-pager.direction()};
        int count=0;for(int index:desired){
            if(index<0||index>=chapters.length)continue;if(count++>=limit)break;
            ReaderRequests.Job candidate=job(index);if(cache.get(candidate.key)==null&&!errors.containsKey(index))jobs.add(candidate);
        }
        requests.replace(jobs);pump();
        if(errors.containsKey(target)){main.removeCallbacks(loadingNotice);status.setText(statusText()+"\n第 "+(target+1)+" 页读取失败，可跳过或再次跳转重试："+errors.get(target));}
    }
    private void pump(){
        if(closed)return;
        ReaderRequests.Job job=requests.take();if(job==null)return;
        try{worker.execute(()->{
            Bitmap result=null;String failure=null;
            try{if(!closed&&job.generation==generation){result=source.render(job.index,job.width,job.height);result.prepareToDraw();}}catch(Exception|OutOfMemoryError error){failure=error.getMessage()==null?"页面无法解码":error.getMessage();}
            final Bitmap loaded=result;final String error=failure;
            main.post(()->{
                requests.complete(job);
                if(closed||job.generation!=generation){if(loaded!=null)loaded.recycle();pump();return;}
                if(loaded!=null)cache.put(job.key,loaded);else errors.put(job.index,error);
                loadVisible();pump();
            });
        });}catch(RejectedExecutionException error){requests.complete(job);}
    }
    private void loadVisible(){
        if(closed||!ready)return;
        if(scroll&&list!=null){for(int i=0;i<list.getChildCount();i++){View row=list.getChildAt(i);if(row instanceof PageRow)bind((PageRow)row,list.getFirstVisiblePosition()+i);}}
        else if(pager!=null)planPages();
    }
    private void go(int target){
        if(!ready)return;
        target=ReaderRules.clamp(target,chapters.length);
        if(!scroll&&pager!=null){
            errors.remove(target);main.removeCallbacks(loadingNotice);update();pager.go(target);main.postDelayed(loadingNotice,180);return;
        }
        page=target;
        if(list!=null)list.setSelection(page);
        update();scheduleSave();
    }
    private void step(int delta){go((!scroll&&pager!=null?pager.target():page)+delta);}
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
    @Override public boolean onKeyDown(int code,android.view.KeyEvent event){if(ready&&(code==KeyEvent.KEYCODE_DPAD_LEFT||code==KeyEvent.KEYCODE_PAGE_UP)){step(-1);return true;}if(ready&&(code==KeyEvent.KEYCODE_DPAD_RIGHT||code==KeyEvent.KEYCODE_PAGE_DOWN)){step(1);return true;}return super.onKeyDown(code,event);}
    @Override protected void onPause(){main.removeCallbacks(savePosition);save();super.onPause();}
    @Override protected void onDestroy(){
        closed=true;main.removeCallbacks(savePosition);main.removeCallbacks(loadingNotice);requests.clear();if(pager!=null)pager.dispose();
        worker.execute(()->{if(source!=null)source.close();});worker.shutdown();libraryWorker.shutdown();cache.evictAll();super.onDestroy();
    }
}
