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
    // Geometry outlives decoded bitmaps, including row recycling and width changes.
    private final Map<Integer,int[]> pageSizes=new HashMap<>();
    private final Set<Integer> retries=new HashSet<>();
    private boolean checking,checkScheduled,firstPageAttempted;
    private String checkStatus="";
    private long openingNoticeTime;
    private final Runnable refreshVisible=()->loadVisible();
    private final Runnable backgroundCheck=()->checkBackground();
    private final TreeSet<Integer> marks=new TreeSet<>();
    private LibraryStore.Entry entry;
    private ReaderSource source;
    private int[] chapters,pageNumbers;
    private List<Integer> starts;
    private int page;
    private int dialogTarget=-1,scrollTarget=-1;
    private boolean splitChapters;
    private int scopeStart,scopeEnd;
    private volatile int generation;
    private boolean scroll=true,ready,stateWritable=true,favoriteBusy;
    private volatile boolean closed;
    private FrameLayout viewport;
    private ReaderChrome chrome;
    private ListView list;
    private ReaderPager pager;
    private String lastSaved="";
    private int viewportWidth,viewportHeight;
    private int noticeTarget=-1;
    private TextView status;
    private final Runnable loadingNotice=()->{if(!closed&&pager!=null&&pager.target()!=pager.displayed()&&cache.get(job(pager.target()).key)==null&&!errors.containsKey(pager.target()))status.setText(statusText()+"\n正在加载第 "+(pager.target()+1)+" 页…");};
    private Button chapterButton,favoriteButton,modeButton,markButton;
    private ActionRow pageNavigation;
    private PopupWindow bookmarkPanel;
    private final Map<Integer,String> bookmarkNames=new HashMap<>();
    private boolean verticalPages;

    private BaseAdapter adapter;
    private SharedPreferences history;
    private final Runnable savePosition=()->save();

    private int dp(int value){return (int)(value*getResources().getDisplayMetrics().density);}
    private void text(TextView view,String value){if(!value.contentEquals(view.getText()))view.setText(value);}
    private Button button(String title,Runnable action){Button result=new ActionButton(this);result.setText(title);result.setTextSize(14);result.setOnClickListener(v->action.run());return result;}
    private void row(LinearLayout body,View...views){body.addView(new ActionRow(this,views));}
    private void message(String text){if(!closed)new AlertDialog.Builder(this).setMessage(text).setPositiveButton("关闭",null).show();}
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        try{entry=new LibraryStore.Entry(new JSONObject(getIntent().getStringExtra("entry")));}catch(Exception error){finish();return;}
        history=getSharedPreferences("reader-history",MODE_PRIVATE);
        splitChapters=Store.get(this).settings.chapterViewMode==2;
        getWindow().setStatusBarColor(Ui.BG);getWindow().setNavigationBarColor(Ui.BG);getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        LinearLayout controls=Ui.column(this);controls.setBackgroundColor(android.graphics.Color.WHITE);controls.setPadding(dp(12),dp(8),dp(12),dp(10));
        TextView title=Ui.text(this,entry.title,18);title.setTypeface(null,Typeface.BOLD);title.setSingleLine(true);title.setGravity(Gravity.CENTER);title.setEllipsize(android.text.TextUtils.TruncateAt.END);controls.addView(title);Ui.gap(controls,12);
        chapterButton=button("章节列表",this::chooseChapter);favoriteButton=button("收藏",this::favorite);modeButton=button("滚动阅读",this::toggleMode);
        markButton=button("书签",this::showBookmarkInput);controls.addView(new ActionRow(this,2,chapterButton,favoriteButton,markButton,button("跳转",this::jumpPage)));
        viewport=new ReaderViewport(this);viewport.setBackgroundColor(Color.WHITE);viewport.setOnClickListener(v->{if(ready&&!closed){chrome.toggle();updateChromeDescription();}});
        LinearLayout navigation=Ui.column(this);navigation.setBackgroundColor(Color.WHITE);navigation.setPadding(dp(12),dp(4),dp(12),dp(10));
        status=Ui.text(this,"正在读取漫画…",12);status.setGravity(Gravity.CENTER);status.setTextColor(Ui.MUTED);status.setLines(2);
        pageNavigation=Ui.pair(this,button("上一页",()->step(-1)),button("下一页",()->step(1)));navigation.addView(pageNavigation);
        chrome=new ReaderChrome(this,new ControlScroll(this,controls),new ControlScroll(this,navigation),viewport,()->{
            if(closed)return;
            getWindow().getDecorView().setSystemUiVisibility(chrome.controlsVisible()?View.SYSTEM_UI_FLAG_VISIBLE:
                View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
            resizeViewport();
        });
        setContentView(chrome);updateChromeDescription();
        viewport.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{
            resizeViewport();
        });
        worker.execute(()->{
            try{
                LibraryStore library=LibraryStore.get(this);Store store=Store.get(this);
                synchronized(store){library.sync(new ArrayList<>(store.tasks));}
                for(LibraryStore.Entry item:library.list("",false))if(item.uri.equals(entry.uri)){entry=item;break;}
                source=new ReaderSource(getApplicationContext(),entry,()->{if(closed||Thread.currentThread().isInterrupted())throw new InterruptedIOException("已关闭阅读器");},text->{
                    long now=System.nanoTime();if(now-openingNoticeTime<100_000_000L)return;openingNoticeTime=now;
                    main.post(()->{if(!closed&&!ready)status.setText(text+"\n完成后优先打开上次阅读页，点击返回可取消。");});
                });
                library.importFound(Collections.singletonList(entry));
                main.post(()->{
                    if(closed)return;chapters=source.chapters;pageNumbers=source.pageNumbers;starts=ReaderRules.starts(chapters);restore();ready=true;checkStatus=entry.format.equals("images")?"正在加载第 "+(page+1)+" 页，随后检查后续 4 页":"";viewport.post(()->{if(!closed){buildPages();update();}});
                });
            }catch(Exception|OutOfMemoryError error){main.post(()->{if(!closed){status.setText("无法阅读："+error.getMessage());message("无法阅读，请检查文件和目录授权："+error.getMessage());}});}
        });
    }
    private void updateChromeDescription(){
        viewport.setContentDescription(chrome.controlsVisible()?"漫画阅读区，点按隐藏工具栏":"漫画阅读区，点按显示工具栏");
        if(list!=null)list.setVerticalScrollBarEnabled(chrome.controlsVisible());
    }
    private void resizeViewport(){
        if(!ready||closed||chrome.animating()||viewport.getWidth()==0||viewport.getHeight()==0)return;
        int width=viewport.getWidth(),height=viewport.getHeight();
        if(width==viewportWidth&&height==viewportHeight)return;
        boolean reload=width!=viewportWidth||!scroll;
        viewportWidth=width;viewportHeight=height;
        if(reload){generation++;requests.clear();errors.clear();cache.evictAll();}
        if(pager!=null)pager.post(()->{if(!closed)loadVisible();});else loadVisible();
    }
    private void restore(){
        try{
            JSONObject saved=new JSONObject(history.getString(entry.uri,"{}"));page=ReaderRules.clamp(saved.optInt("page",0),chapters.length);String preference=Store.get(this).settings.readingMode;String mode=preference.isEmpty()?saved.optString("mode","scroll"):preference;scroll=mode.equals("scroll");verticalPages=mode.equals("vertical");JSONObject names=saved.optJSONObject("bookmarkNames");if(names!=null){Iterator<String> keys=names.keys();while(keys.hasNext()){String key=keys.next();try{bookmarkNames.put(Integer.parseInt(key),names.optString(key));}catch(NumberFormatException ignored){}}}
            JSONArray items=saved.optJSONArray("bookmarks");if(items!=null)for(int i=0;i<items.length();i++){int mark=items.getInt(i);if(mark>=0&&mark<chapters.length)marks.add(mark);}
        }catch(Exception error){stateWritable=false;message("阅读记录损坏，原记录保留，本次不覆盖。"+error.getMessage());}
    }
    private void save(){
        if(!ready||!stateWritable)return;
        try{
            JSONArray items=new JSONArray();for(int mark:marks)items.put(mark);
            JSONObject names=new JSONObject();for(int mark:marks)if(bookmarkNames.containsKey(mark))names.put(Integer.toString(mark),bookmarkNames.get(mark));String value=new JSONObject().put("page",page).put("mode",scroll?"scroll":verticalPages?"vertical":"paged").put("bookmarks",items).put("bookmarkNames",names).toString();
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
        text(favoriteButton,entry.favorite?"取消收藏":"收藏");text(modeButton,scroll?"滚动阅读":"左右翻页");text(markButton,"书签");pageNavigation.setVisibility(scroll?View.GONE:View.VISIBLE);
        if(!ready)return;
        int chapter=ReaderRules.chapter(starts,page);
        text(chapterButton,"章节列表");
        text(status,statusText()+"\n"+(checkStatus.isEmpty()?"点按漫画隐藏或显示工具栏"+(!scroll?(verticalPages?" · 上下滑动翻页":" · 左右滑动翻页"):""):checkStatus));
    }
    private String statusText(){
        int chapter=ReaderRules.chapter(starts,page),end=chapter+1<starts.size()?starts.get(chapter+1):chapters.length;
        return "本章 "+(page-starts.get(chapter)+1)+"/"+(end-starts.get(chapter))+" 页 · 总页码 "+(page+1)+"/"+chapters.length+(splitChapters?" · 分章节观看（章末请切换下一章）":" · 多章节合一")+(entry.format.equals("pdf")?" · PDF 按一个章节显示":"");
    }
    private void buildPages(){
        if(!ready||closed)return;
        int chapter=ReaderRules.chapter(starts,page);
        scopeStart=splitChapters?starts.get(chapter):0;
        scopeEnd=splitChapters&&chapter+1<starts.size()?starts.get(chapter+1):chapters.length;
        viewportWidth=viewport.getWidth();viewportHeight=viewport.getHeight();
        main.removeCallbacks(loadingNotice);noticeTarget=-1;generation++;requests.clear();errors.clear();cache.evictAll();
        releaseRows();
        if(pager!=null){pager.dispose();pager=null;}viewport.removeAllViews();
        if(scroll){
            list=new ListView(this);list.setDivider(null);list.setDividerHeight(0);list.setBackgroundColor(Color.rgb(32,37,44));
            adapter=new BaseAdapter(){
                public int getCount(){return scopeEnd-scopeStart;}public Object getItem(int position){return scopeStart+position;}public long getItemId(int position){return scopeStart+position;}
                public View getView(int position,View convert,ViewGroup parent){PageRow row=convert instanceof PageRow?(PageRow)convert:new PageRow();bind(row,scopeStart+position);return row;}
            };
            list.setRecyclerListener(view->{if(view instanceof PageRow)((PageRow)view).release();});
            list.setAdapter(adapter);viewport.addView(list,new FrameLayout.LayoutParams(-1,-1));
            final ListView opening=list;
            // setSelectionFromTop is deferred. A size change before its layout can
            // restore the old first row; keep the request until a drawn frame agrees.
            opening.getViewTreeObserver().addOnPreDrawListener(()->{
                if(closed||list!=opening||scrollTarget<0)return true;
                View first=opening.getChildAt(0);
                if(opening.getFirstVisiblePosition()==scrollTarget-scopeStart&&first!=null&&first.getTop()==opening.getPaddingTop()){
                    page=scrollTarget;scrollTarget=-1;update();scheduleSave();return true;
                }
                opening.setSelectionFromTop(scrollTarget-scopeStart,0);return false;
            });
            scrollTarget=page;list.setSelectionFromTop(scrollTarget-scopeStart,0);
            updateChromeDescription();
            list.setOnScrollListener(new AbsListView.OnScrollListener(){
                public void onScrollStateChanged(AbsListView view,int state){if(view!=list)return;if(state==SCROLL_STATE_TOUCH_SCROLL)scrollTarget=-1;if(state==SCROLL_STATE_IDLE)loadVisible();}
                public void onScroll(AbsListView view,int first,int count,int total){if(view==list&&count>0){if(scrollTarget<0){page=scopeStart+first;update();scheduleSave();}main.removeCallbacks(refreshVisible);main.post(refreshVisible);}}
            });
        }else{
            scrollTarget=-1;list=null;pager=new ReaderPager(this,chapters.length,page,new ReaderPager.Listener(){
                public Bitmap lookup(int index){return index<scopeStart||index>=scopeEnd?null:cache.get(job(index).key);}
                public void requested(){planPages();}
                public void committed(int index){page=index;main.removeCallbacks(loadingNotice);update();scheduleSave();}
            });
            pager.setVerticalPaging(verticalPages);pager.setRange(scopeStart,scopeEnd);
            viewport.addView(pager,new FrameLayout.LayoutParams(-1,-1));
            final ReaderPager opening=pager;
            opening.post(()->{if(!closed&&pager==opening)opening.go(opening.target());});
        }
    }
    private final class PageRow extends FrameLayout {
        final ImageView image;final TextView label;
        Bitmap shown;
        PageRow(){super(ReaderActivity.this);image=new ImageView(ReaderActivity.this);image.setScaleType(ImageView.ScaleType.FIT_XY);label=new TextView(ReaderActivity.this);label.setTextColor(Color.LTGRAY);label.setGravity(Gravity.CENTER);label.setTextSize(12);addView(image,new FrameLayout.LayoutParams(-1,dp(300)));addView(label,new FrameLayout.LayoutParams(-1,-1));}
        void release(){shown=null;setTag(null);image.setImageDrawable(null);}
    }
    private void releaseRows(){
        if(list!=null)for(int i=0;i<list.getChildCount();i++){View row=list.getChildAt(i);if(row instanceof PageRow)((PageRow)row).release();}
    }
    private int pageHeight(int index,int width){
        int[] size=pageSizes.get(index);
        return size==null?Math.max(1,(int)(width*1.4)):Math.max(1,(int)((long)size[1]*width/size[0]));
    }
    private void bind(PageRow row,int index){
        ReaderRequests.Job job=job(index);int width=job.width;
        String key=job.key;if(!key.equals(row.getTag())){row.release();row.setTag(key);}
        // A visible row still owns its valid image even if the shared LRU evicted it.
        Bitmap bitmap=row.shown;
        if(bitmap==null||bitmap.isRecycled())bitmap=cache.get(key);
        if(bitmap!=null&&bitmap!=row.shown)pageSizes.put(index,new int[]{bitmap.getWidth(),bitmap.getHeight()});
        if(bitmap==null)text(row.label,errors.containsKey(index)?"本页读取失败，可继续翻页："+errors.get(index):"第 "+(index+1)+" 页 · 正在加载…");
        row.label.setVisibility(bitmap==null?View.VISIBLE:View.GONE);
        // Images keep their fitted height; notices overlay the placeholder.
        FrameLayout.LayoutParams params=(FrameLayout.LayoutParams)row.image.getLayoutParams();int height=pageHeight(index,width);
        // Permit even a short final page to sit at the top after a bookmark jump.
        // Space is only after the final image; adjacent pages still meet exactly.
        int minimum=index==scopeEnd-1?viewportHeight:0;
        if(row.getMinimumHeight()!=minimum)row.setMinimumHeight(minimum);
        if(params.height!=height){params.height=height;row.image.setLayoutParams(params);}
        if(bitmap!=null){if(row.shown!=bitmap){row.shown=bitmap;row.image.setImageBitmap(bitmap);}return;}
        if(errors.containsKey(index)||closed)return;
        requests.offer(job);pump();
    }
    private ReaderRequests.Job job(int index){return new ReaderRequests.Job(generation,index,Math.max(100,viewportWidth-(scroll?0:dp(8))),scroll?0:Math.max(100,viewportHeight-dp(8)));}
    private void planPages(){
        if(closed||scroll||pager==null)return;
        pager.ready();int target=pager.target();List<ReaderRequests.Job> jobs=new ArrayList<>();
        if(target!=noticeTarget){noticeTarget=target;main.removeCallbacks(loadingNotice);update();main.postDelayed(loadingNotice,180);}
        ReaderRequests.Job first=job(target);
        long estimate=Math.min(4000000L,(long)Math.min(1600,first.width)*Math.min(8192,first.height))*4;
        int limit=(int)Math.max(1,Math.min(6,32L*1024*1024/Math.max(1,estimate)));
        int direction=pager.direction();
        int[] desired=pager.busy()?new int[]{target}:new int[]{target,target+direction,target+2*direction,target+3*direction,target+4*direction,target-direction};
        int count=0;for(int index:desired){
            if(index<scopeStart||index>=scopeEnd)continue;if(count++>=limit)break;
            ReaderRequests.Job candidate=job(index);if(cache.get(candidate.key)==null&&!errors.containsKey(index))jobs.add(candidate);
        }
        requests.replace(jobs);pump();
        if(errors.containsKey(target)){main.removeCallbacks(loadingNotice);status.setText(statusText()+"\n第 "+(target+1)+" 页读取失败，可跳过或再次跳转重试："+errors.get(target));}
    }
    private void pump(){
        if(closed||checking)return;
        ReaderRequests.Job job=requests.take();if(job==null){scheduleCheck();return;}
        boolean retry=retries.remove(job.index);
        try{worker.execute(()->{
            Bitmap result=null;String failure=null;
            try{if(!closed&&job.generation==generation){if(retry)source.retry(job.index);result=source.render(job.index,job.width,job.height);result.prepareToDraw();}}catch(Exception|OutOfMemoryError error){failure=error.getMessage()==null?"页面无法解码":error.getMessage();}
            final Bitmap loaded=result;final String error=failure;final String progress=source.progress();
            main.post(()->{
                requests.complete(job);
                if(closed||job.generation!=generation){if(loaded!=null)loaded.recycle();pump();return;}
                if(loaded!=null){pageSizes.put(job.index,new int[]{loaded.getWidth(),loaded.getHeight()});cache.put(job.key,loaded);}else errors.put(job.index,error);
                if(job.index==(pager!=null?pager.target():page))firstPageAttempted=true;
                checkStatus=progress;update();
                loadVisible();pump();
            });
        });}catch(RejectedExecutionException error){requests.complete(job);}
    }
    private void loadVisible(){
        if(closed||!ready)return;
        if(scroll&&list!=null){
            requests.clear();int first=scopeStart+list.getFirstVisiblePosition(),count=list.getChildCount();long budget=32L*1024*1024;
            for(int i=0;i<count;i++){
                int index=first+i;if(index>=scopeEnd)break;
                View row=list.getChildAt(i);if(row instanceof PageRow)bind((PageRow)row,index);
                Bitmap image=row instanceof PageRow?((PageRow)row).shown:null;
                // Touch only visible cached pages; retained row images count toward the budget too.
                cache.get(job(index).key);budget-=image==null?16_000_000:image.getByteCount();
            }
            // Current visible rows always win. Unknown images reserve the maximum decoded size.
            Map<String,Bitmap> available=cache.snapshot();
            for(int i=first+count;count>0&&i<Math.min(scopeEnd,first+count+4);i++){
                // Budget inspection must not promote an offscreen page above visible pages in LRU order.
                ReaderRequests.Job next=job(i);Bitmap image=available.get(next.key);long bytes=image==null?16_000_000:image.getByteCount();
                if(bytes>budget)break;budget-=bytes;
                if(image==null&&!errors.containsKey(i))requests.offer(next);
            }
            pump();
        }
        else if(pager!=null)planPages();
    }
    private void scheduleCheck(){
        if(closed||checksFinished||checking||checkScheduled||requests.running()||!ready||!firstPageAttempted||!entry.format.equals("images"))return;
        checkScheduled=true;main.postDelayed(backgroundCheck,40);
    }
    private boolean checksFinished;
    private void checkBackground(){
        checkScheduled=false;
        if(closed||checksFinished||checking||requests.running())return;
        if(requests.waiting()>0){pump();return;}
        checking=true;final int anchor=pager!=null?pager.target():page;
        try{worker.execute(()->{
            Map<Integer,String> failed=Collections.emptyMap();String progress="";boolean done=false;
            try{failed=source.check(anchor);progress=source.progress();done=!source.hasChecks();}
            catch(Exception|OutOfMemoryError error){progress="后台检查已暂停，可继续阅读";done=true;}
            final Map<Integer,String> failures=failed;final String text=progress;final boolean finished=done;
            main.post(()->{checking=false;if(closed)return;errors.putAll(failures);checkStatus=text;checksFinished=finished;update();loadVisible();pump();});
        });}catch(RejectedExecutionException error){checking=false;}
    }
    private void go(int target){
        if(!ready||closed)return;
        dialogTarget=-1;
        target=ReaderRules.clamp(target,chapters.length);
        if(target<scopeStart||target>=scopeEnd){page=target;buildPages();update();scheduleSave();return;}
        if(errors.remove(target)!=null)retries.add(target);
        if(!scroll&&pager!=null){
            errors.remove(target);main.removeCallbacks(loadingNotice);update();pager.go(target);main.postDelayed(loadingNotice,180);return;
        }
        page=target;scrollTarget=target;
        if(list!=null){list.smoothScrollBy(0,0);list.setSelectionFromTop(target-scopeStart,0);}
        update();scheduleSave();
    }
    private void jumpFromDialog(DialogInterface dialog,int target){
        dialogTarget=ReaderRules.clamp(target,chapters.length);
        // Android dismisses standard buttons after invoking their click callback.
        // Wait for both dismissal and reader focus before changing list geometry
        // or starting a page animation underneath the outgoing dialog.
        ((Dialog)dialog).setOnDismissListener(ignored->postDialogJump());
        dialog.dismiss();
    }
    private void postDialogJump(){
        viewport.post(()->{if(!closed&&dialogTarget>=0&&hasWindowFocus())go(dialogTarget);});
    }
    @Override public void onWindowFocusChanged(boolean focused){
        super.onWindowFocusChanged(focused);
        if(focused&&dialogTarget>=0&&viewport!=null)postDialogJump();
    }
    private void step(int delta){go(Math.max(scopeStart,Math.min(scopeEnd-1,(!scroll&&pager!=null?pager.target():page)+delta)));}
    private void chapterStep(int delta){if(ready)go(starts.get(ReaderRules.clamp(ReaderRules.chapter(starts,page)+delta,starts.size())));}
    private void chooseChapter(){
        if(!ready)return;
        String[] labels=new String[starts.size()];for(int i=0;i<labels.length;i++)labels[i]="第 "+chapters[starts.get(i)]+" 章 · "+((i+1<starts.size()?starts.get(i+1):chapters.length)-starts.get(i))+" 页";
        new AlertDialog.Builder(this).setTitle("选择章节").setSingleChoiceItems(labels,ReaderRules.chapter(starts,page),(dialog,index)->jumpFromDialog(dialog,starts.get(index))).setNegativeButton("关闭",null).show();
    }
    private void toggleMode(){if(ready){if(pager!=null)page=pager.target();scroll=!scroll;buildPages();update();save();}}
    private void showBookmarkInput(){
        if(!ready)return;if(bookmarkPanel!=null&&bookmarkPanel.isShowing()){bookmarkPanel.dismiss();return;}
        LinearLayout body=Ui.column(this);int pad=dp(14);body.setPadding(pad,pad,pad,pad);body.setBackground(Ui.shape(this,Color.WHITE,12,true));EditText name=Ui.input(this,"请输入名称",false);name.setSingleLine(true);body.addView(name);Ui.gap(body,12);
        int[] anchor=new int[2];markButton.getLocationOnScreen(anchor);int center=anchor[0]+markButton.getWidth()/2;
        android.graphics.Rect bounds=new android.graphics.Rect();markButton.getWindowVisibleDisplayFrame(bounds);
        int width=Math.max(1,Math.min(dp(310),2*Math.min(center-bounds.left-dp(14),bounds.right-dp(14)-center)));
        LinearLayout popup=Ui.column(this);View pointer=new View(this){@Override protected void onDraw(android.graphics.Canvas c){float middle=getWidth()/2f;android.graphics.Paint p=new android.graphics.Paint(3);android.graphics.Path path=new android.graphics.Path();path.moveTo(middle-dp(9),dp(9));path.lineTo(middle,0);path.lineTo(middle+dp(9),dp(9));p.setColor(Color.WHITE);c.drawPath(path,p);p.setColor(Ui.LINE);p.setStyle(android.graphics.Paint.Style.STROKE);p.setStrokeWidth(dp(1));c.drawPath(path,p);}};popup.addView(pointer,new LinearLayout.LayoutParams(-1,dp(9)));popup.addView(body);bookmarkPanel=new PopupWindow(popup,width,-2,true);bookmarkPanel.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(Color.TRANSPARENT));bookmarkPanel.setElevation(dp(8));bookmarkPanel.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        Button add=button("添加",()->{String value=name.getText().toString().trim();if(value.isEmpty()){name.setError("请输入名称");return;}if(value.length()>80){name.setError("名称最多 80 个字符");return;}marks.add(page);bookmarkNames.put(page,value);save();bookmarkPanel.dismiss();Ui.notice(this,"书签已添加");});Ui.primary(add);body.addView(Ui.pair(this,add,button("取消",()->bookmarkPanel.dismiss())));bookmarkPanel.showAsDropDown(markButton,(markButton.getWidth()-width)/2,dp(6),Gravity.LEFT);
    }
    private void jumpPage(){
        if(!ready)return;if(bookmarkPanel!=null)bookmarkPanel.dismiss();
        LinearLayout body=Ui.column(this);EditText input=Ui.input(this,"请输入页码",true);body.addView(input);Ui.gap(body,12);LinearLayout items=Ui.column(this);ScrollView scrollView=new ScrollView(this);scrollView.addView(items);body.addView(scrollView,new LinearLayout.LayoutParams(-1,dp(190)));
        final AlertDialog[] targetDialog={null};
        for(int mark:marks){Button item=button(bookmarkNames.getOrDefault(mark,"第 "+(mark+1)+" 页"),()->jumpFromDialog(targetDialog[0],mark));item.setOnLongClickListener(v->{marks.remove(mark);bookmarkNames.remove(mark);save();items.removeView(item);return true;});item.setGravity(Gravity.LEFT|Gravity.CENTER_VERTICAL);item.setBackground(Ui.shape(this,Ui.BG,6,false));items.addView(item);Ui.gap(items,6);}Ui.gap(body,16);
        AlertDialog dialog=Ui.modal(this,body,true);targetDialog[0]=dialog;Button jump=button("跳转",()->{try{int target=Integer.parseInt(input.getText().toString());if(target<1||target>chapters.length)throw new NumberFormatException();jumpFromDialog(dialog,target-1);}catch(NumberFormatException error){input.setError("请输入 1–"+chapters.length+" 的页码");}});Ui.primary(jump);body.addView(Ui.pair(this,jump,button("取消",dialog::dismiss)));dialog.show();
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
        new AlertDialog.Builder(this).setTitle("书签").setItems(labels,(dialog,index)->new AlertDialog.Builder(this).setTitle(labels[index]).setPositiveButton("跳转",(d,w)->jumpFromDialog(d,pages[index])).setNeutralButton("删除书签",(d,w)->{marks.remove(pages[index]);save();update();}).setNegativeButton("取消",null).show()).setNegativeButton("关闭",null).show();
    }
    @Override public boolean onKeyDown(int code,android.view.KeyEvent event){if(ready&&(code==KeyEvent.KEYCODE_DPAD_LEFT||code==KeyEvent.KEYCODE_PAGE_UP)){step(-1);return true;}if(ready&&(code==KeyEvent.KEYCODE_DPAD_RIGHT||code==KeyEvent.KEYCODE_PAGE_DOWN)){step(1);return true;}return super.onKeyDown(code,event);}
    @Override protected void onPause(){main.removeCallbacks(savePosition);save();super.onPause();}
    @Override public void onBackPressed(){if(chrome!=null&&!chrome.controlsVisible()){chrome.show(true);updateChromeDescription();}else super.onBackPressed();}
    @Override protected void onDestroy(){
        closed=true;dialogTarget=scrollTarget=-1;if(chrome!=null)chrome.dispose();main.removeCallbacks(savePosition);main.removeCallbacks(loadingNotice);main.removeCallbacks(refreshVisible);main.removeCallbacks(backgroundCheck);requests.clear();if(pager!=null)pager.dispose();
        releaseRows();pageSizes.clear();
        worker.execute(()->{if(source!=null)source.close();});worker.shutdown();libraryWorker.shutdown();cache.evictAll();super.onDestroy();
    }
}
