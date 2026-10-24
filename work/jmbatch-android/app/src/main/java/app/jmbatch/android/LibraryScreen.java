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
import android.view.inputmethod.InputMethodManager;
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
    private FrameLayout page;
    private LinearLayout sheet,moveBar;
    private TextView selectionTitle;
    private Button sortButton;
    private String sort="name";private boolean moving;
    private boolean chapterScanning;
    private final Set<String> chapterScanAttempted=new HashSet<>();
    private List<LibraryStore.Entry> movingItems;
    private String moveOrigin="";
    private boolean checkingAll;
    private final ExecutorService updateWorker=Executors.newSingleThreadExecutor();
    public boolean back(){if(moving){cancelMove();return true;}if(batchMode){setBatchMode(false);return true;}if(!collection.isEmpty()){navigate("");return true;}return false;}

    private EditText query;
    private CheckBox favorites;
    private TextView status;
    private TextView breadcrumb;
    private Button backButton;
    private String collection="";
    private Map<String,List<LibraryStore.Entry>> collectionPreviews=new HashMap<>();
    private LibraryGridView list;
    private boolean tiles;
    private RadioGroup displaySelector;
    private Button stop;
    private Button modeButton;
    private TextView hint;
    private LinearLayout selectionControls,batchActions;
    private final List<Button> singleButtons=new ArrayList<>(),batchButtons=new ArrayList<>();
    private boolean batchMode;
    private BaseAdapter adapter;
    private final ThreadPoolExecutor coverWorker=new ThreadPoolExecutor(1,1,0L,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(24));
    private static final class Cover {final Bitmap bitmap;Cover(Bitmap bitmap){this.bitmap=bitmap;}}
    private final LruCache<String,Cover> coverCache=new LruCache<String,Cover>(8*1024*1024){protected int sizeOf(String key,Cover cover){return cover.bitmap==null?1024:cover.bitmap.getByteCount();}};
    private final Set<String> coverPending=new HashSet<>();
    private int coverGeneration;
    private List<LibraryStore.Entry> entries=new ArrayList<>();
    private boolean busy,loading;
    private boolean returningFromReader;
    private Bundle pendingViewState;
    private int generation;
    private String filter="",report="";
    private volatile CancellationSignal scanSignal;
    private volatile JmApi.Control updateControl;
    private final ChapterUpdates.Fetch chapterUpdateFetch;
    public LibraryScreen(Activity activity,Store store){this(activity,store,ChapterUpdates::fetch);}
    LibraryScreen(Activity activity,Store store,ChapterUpdates.Fetch fetch){this.activity=activity;this.store=store;this.chapterUpdateFetch=fetch;}
    private int dp(int n){return (int)(n*activity.getResources().getDisplayMetrics().density);}
    private boolean visible(){return page!=null&&page.getParent()!=null&&!activity.isFinishing()&&!activity.isDestroyed()&&(dialog==null||dialog.isShowing());}
    private String title(LibraryStore.Entry e){return e.id.isEmpty()?e.title:"JM"+e.id+" · "+e.title;}
    private Button button(String text,Runnable action){Button b=new ActionButton(activity);b.setText(text);b.setTextSize(12);b.setOnClickListener(v->{if(!busy&&!loading)action.run();});return b;}
    private void row(LinearLayout body,Button... buttons){body.addView(new ActionRow(activity,buttons));}
    public boolean isOpen(){return visible();}
    public void close(){if(dialog!=null){dialog.dismiss();return;}dispose();if(page!=null&&page.getParent()!=null)((ViewGroup)page.getParent()).removeView(page);}
    private void dispose(){generation++;resetCovers();cancel();worker.shutdown();updateWorker.shutdownNow();coverWorker.shutdownNow();}
    public void refresh(){load();}
    public void resume(){if(returningFromReader&&visible()){returningFromReader=false;load();}}
    public Bundle saveState(){
        if(!visible())return null;
        Bundle state=new Bundle();state.putString("query",query.getText().toString());state.putBoolean("favorites",favorites.isChecked());
        state.putBoolean("batch",batchMode);state.putStringArrayList("selected",new ArrayList<>(selected));state.putString("report",report);
        state.putString("collection",collection);
        Bundle viewport=pendingViewState!=null?pendingViewState:viewportState();state.putBundle("viewport",viewport);
        return state;
    }
    private Bundle viewportState(){
        Bundle state=new Bundle();int first=list.getFirstVisiblePosition();View child=list.getChildAt(0);
        state.putInt("first",first);state.putInt("top",child==null?0:child.getTop());
        if(first>=0&&first<entries.size())state.putString("anchor",entries.get(first).uri);
        return state;
    }
    private void restoreViewport(Bundle state){
        if(state==null||entries.isEmpty())return;
        int first=Math.max(0,Math.min(state.getInt("first"),entries.size()-1));String anchor=state.getString("anchor","");
        for(int i=0;i<entries.size();i++)if(entries.get(i).uri.equals(anchor)){first=i;break;}
        list.restorePosition(first,state.getInt("top"));
    }
    public void show(){show(null);}
    public void show(Bundle saved){
        if(visible())return;
        page=new FrameLayout(activity);page.setBackground(Ui.shape(activity,android.graphics.Color.WHITE,18,true));
        LinearLayout root=Ui.column(activity);root.setPadding(dp(12),dp(8),dp(12),dp(8));root.setFocusableInTouchMode(true);page.addView(root,new FrameLayout.LayoutParams(-1,-1));
        root.addView(Ui.heading(activity,"漫画库"));
        hint=new TextView(activity);hint.setTextSize(12);query=new EditText(activity);favorites=new CheckBox(activity);modeButton=button("批量处理",()->setBatchMode(!batchMode));displaySelector=new RadioGroup(activity);selectionControls=Ui.column(activity);
        sortButton=button("排序方式",this::sortMenu);Button newCollection=Ui.iconButton(activity,"folder","",()->editCollection(null));newCollection.setContentDescription("新建收藏夹");root.addView(Ui.pair(activity,button("检查更新",this::checkAllUpdates),sortButton,newCollection));
        breadcrumb=Ui.text(activity,"漫画库",12);breadcrumb.setTextColor(Ui.MUTED);backButton=button("返回漫画库",()->navigate(""));
        status=Ui.text(activity,"",12);status.setTextColor(Ui.MUTED);
        Ui.gap(root,20);tiles=true;list=new LibraryGridView(activity);list.setStretchMode(GridView.STRETCH_COLUMN_WIDTH);list.setHorizontalSpacing(dp(8));list.setVerticalSpacing(dp(8));list.setNumColumns(4);list.setChoiceMode(ListView.CHOICE_MODE_NONE);adapter=new CoverAdapter();list.setAdapter(adapter);root.addView(list,new LinearLayout.LayoutParams(-1,0,1));
        list.setOnScrollListener(new AbsListView.OnScrollListener(){public void onScroll(AbsListView v,int first,int count,int total){}public void onScrollStateChanged(AbsListView v,int state){if(state==SCROLL_STATE_IDLE)adapter.notifyDataSetChanged();}});
        list.setOnItemClickListener((p,v,position,id)->itemClick(position));list.setOnItemLongClickListener((p,v,position,id)->itemLongClick(position));

        sheet=Ui.column(activity);sheet.setPadding(dp(16),dp(18),dp(16),dp(20));sheet.setBackground(Ui.shape(activity,android.graphics.Color.WHITE,18,true));sheet.setElevation(dp(12));selectionTitle=Ui.text(activity,"",16);selectionTitle.setTypeface(null,android.graphics.Typeface.BOLD);selectionTitle.setGravity(Gravity.CENTER);sheet.addView(selectionTitle);Ui.gap(sheet,14);
        batchActions=Ui.column(activity);sheet.addView(batchActions);
        Button export=button("导出",()->{List<LibraryStore.Entry> items=selection();if(!items.isEmpty())new ExportScreen(activity,store,items,this::load).show();}),delete=button("删除",()->confirmRemove(true)),share=Ui.iconButton(activity,"share","",this::shareSelection),favorite=button("收藏",()->{List<LibraryStore.Entry> items=selection();boolean all=true;for(LibraryStore.Entry e:items)all&=e.favorite;favorite(!all);}),move=button("移动",this::beginMove),cancel=button("取消",()->setBatchMode(false));
        batchButtons.addAll(Arrays.asList(export,delete,share,favorite,move));batchActions.addView(Ui.pair(activity,export,delete,share));Ui.gap(batchActions,8);batchActions.addView(Ui.pair(activity,favorite,move,cancel));
        moveBar=Ui.column(activity);moveBar.addView(Ui.pair(activity,button("确认",this::commitMove),button("返回",this::cancelMove)));moveBar.setVisibility(View.GONE);sheet.addView(moveBar);page.addView(sheet,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));sheet.setVisibility(View.GONE);
        stop=button("停止操作",this::cancel);stop.setEnabled(false);
        if(activity instanceof MainActivity){page.setBackgroundColor(Color.TRANSPARENT);((MainActivity)activity).libraryHost().addView(page,new FrameLayout.LayoutParams(-1,-1));}
        else{dialog=new Dialog(activity);dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);dialog.setContentView(page);dialog.setOnKeyListener((d,key,event)->{if(key==KeyEvent.KEYCODE_BACK&&event.getAction()==KeyEvent.ACTION_UP)return back();return false;});dialog.setOnDismissListener(d->dispose());dialog.show();dialog.getWindow().setLayout(-1,(int)(activity.getResources().getDisplayMetrics().heightPixels*.93));}
        setBatchMode(saved!=null&&saved.getBoolean("batch"));
        if(saved!=null){
            collection=saved.getString("collection","");
            query.setText(saved.getString("query",""));favorites.setChecked(saved.getBoolean("favorites"));report=saved.getString("report","");
            ArrayList<String> choices=saved.getStringArrayList("selected");if(batchMode&&choices!=null)selected.addAll(choices);
            filter=query.getText().toString()+"|"+favorites.isChecked()+"|"+collection;pendingViewState=saved.getBundle("viewport");
        }
        root.requestFocus();
        query.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int st,int c,int a){}public void onTextChanged(CharSequence s,int st,int before,int count){load();}public void afterTextChanged(Editable e){}});
        favorites.setOnCheckedChangeListener((b,c)->load());load();
    }
    private void changeDisplay(boolean value){
        if(busy||loading||tiles==value)return;
        Bundle state=viewportState();tiles=value;list.setNumColumns(tiles?4:1);adapter.notifyDataSetChanged();
        list.post(()->restoreViewport(state));
    }
    private void read(LibraryStore.Entry entry){
        if(entry.isCollection()){navigate(entry.uri);return;}
        returningFromReader=true;
        query.clearFocus();list.requestFocus();
        InputMethodManager keyboard=(InputMethodManager)activity.getSystemService(Context.INPUT_METHOD_SERVICE);
        if(keyboard!=null)keyboard.hideSoftInputFromWindow(query.getWindowToken(),0);
        ReaderActivity.open(activity,entry);
    }
    private void itemClick(int position){
        if(busy||position<0||position>=entries.size()||!list.isEnabled())return;
        LibraryStore.Entry entry=entries.get(position);
        if(entry.isCollection()){navigate(entry.uri);return;}
        if(moving)return;
        if(!batchMode){read(entry);return;}
        if(!selected.add(entry.uri))selected.remove(entry.uri);
        list.setItemChecked(position,selected.contains(entry.uri));counts();
    }
    private boolean itemLongClick(int position){
        if(!busy&&position>=0&&position<entries.size()&&list.isEnabled()){
            if(entries.get(position).isCollection()){manageCollection(entries.get(position).uri);return true;}
            if(!batchMode)setBatchMode(true);
            selected.add(entries.get(position).uri);list.setItemChecked(position,true);counts();
        }
        return true;
    }
    private void setBatchMode(boolean value){
        if(busy||loading)return;
        batchMode=value;selected.clear();list.clearChoices();
        list.setChoiceMode(value?ListView.CHOICE_MODE_MULTIPLE:ListView.CHOICE_MODE_NONE);
        modeButton.setText(value?"完成":"批量处理");
        hint.setText(value?"勾选漫画后可移入收藏夹；点击“完成”退出。":"点击漫画阅读，点击收藏夹进入；长按可管理。");
        selectionControls.setVisibility(View.GONE);batchActions.setVisibility(value?View.VISIBLE:View.GONE);
        if(value){selectionTitle.setVisibility(View.VISIBLE);moveBar.setVisibility(View.GONE);Ui.sheet(sheet);}else if(!moving)sheet.setVisibility(View.GONE);
        adapter.notifyDataSetChanged();counts();
    }
    private void resetCovers(){coverGeneration++;coverWorker.getQueue().clear();coverPending.clear();coverCache.evictAll();}
    private final class CoverRow extends LinearLayout implements Checkable {
        final ImageView image;final TextView placeholder,star,number;final CheckedTextView text;final boolean tile=tiles;
        final TaskSelectionBox choice;boolean choosing;String boundUri;
        CoverRow(){
            super(activity);setOrientation(tile?LinearLayout.VERTICAL:LinearLayout.HORIZONTAL);setGravity(Gravity.CENTER_VERTICAL);setPadding(dp(tile?2:4),dp(tile?4:8),dp(tile?2:4),dp(tile?6:8));
            FrameLayout frame=new FrameLayout(activity){
                @Override protected void onMeasure(int widthSpec,int heightSpec){
                    // Four columns can be much narrower than the old fixed 136dp cover.
                    if(tile&&MeasureSpec.getMode(widthSpec)!=MeasureSpec.UNSPECIFIED)
                        heightSpec=MeasureSpec.makeMeasureSpec(Math.max(1,Math.round(MeasureSpec.getSize(widthSpec)*4f/3f)),MeasureSpec.EXACTLY);
                    super.onMeasure(widthSpec,heightSpec);
                }
            };frame.setBackgroundColor(Ui.BG);setBackground(Ui.shape(activity,android.graphics.Color.WHITE,10,true));
            image=new ImageView(activity);image.setScaleType(ImageView.ScaleType.CENTER_CROP);frame.addView(image,new FrameLayout.LayoutParams(-1,-1));
            placeholder=new TextView(activity);placeholder.setText("暂无\n封面");placeholder.setTextSize(12);placeholder.setGravity(Gravity.CENTER);placeholder.setTextColor(Color.rgb(97,115,135));frame.addView(placeholder,new FrameLayout.LayoutParams(-1,-1));
            star=Ui.text(activity,"★",22);star.setTextColor(0xffd6a039);FrameLayout.LayoutParams badge=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.RIGHT);badge.rightMargin=dp(4);frame.addView(star,badge);
            choice=new TaskSelectionBox(activity);choice.setFocusable(false);choice.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);frame.addView(choice,new FrameLayout.LayoutParams(dp(28),dp(28),Gravity.TOP|Gravity.RIGHT));
            addView(frame,new LinearLayout.LayoutParams(tile?-1:dp(64),tile?-2:dp(86)));
            text=new CheckedTextView(activity);text.setTextSize(tile?12:14);text.setSingleLine(true);text.setTextColor(Ui.INK);text.setGravity(Gravity.CENTER);text.setEllipsize(TextUtils.TruncateAt.MARQUEE);text.setMarqueeRepeatLimit(-1);text.setSelected(true);text.setPadding(tile?dp(2):dp(12),tile?dp(4):0,tile?dp(2):0,0);
            addView(text,tile?new LinearLayout.LayoutParams(-1,-2):new LinearLayout.LayoutParams(0,-2,1));number=Ui.text(activity,"",11);number.setSingleLine(true);number.setEllipsize(TextUtils.TruncateAt.END);number.setTextColor(Ui.MUTED);number.setGravity(Gravity.CENTER);addView(number);
        }
        private void bindChoice(boolean show,boolean checked,boolean sameEntry){
            choosing=show;text.setCheckMarkDrawable(null);text.setChecked(show&&checked);
            FrameLayout.LayoutParams badge=(FrameLayout.LayoutParams)star.getLayoutParams();int margin=dp(show?28:4);if(badge.rightMargin!=margin){badge.rightMargin=margin;star.setLayoutParams(badge);}
            choice.bind(show,show&&checked,sameEntry);
            // Binding recycled rows or refreshed covers is not a user selection change.
            text.jumpDrawablesToCurrentState();
        }
        public boolean isChecked(){return text.isChecked();}public void setChecked(boolean value){text.setChecked(choosing&&value);choice.bind(choosing,choosing&&value);}public void toggle(){setChecked(!isChecked());}
    }
    private final class CoverAdapter extends BaseAdapter {
        public int getCount(){return entries.size();}public Object getItem(int position){return entries.get(position);}public long getItemId(int position){return position;}
        public View getView(int position,View recycled,ViewGroup parent){
            CoverRow row=recycled instanceof CoverRow&&((CoverRow)recycled).tile==tiles?(CoverRow)recycled:new CoverRow();LibraryStore.Entry entry=entries.get(position);
            if(!entry.title.contentEquals(row.text.getText()))row.text.setText(entry.title);row.number.setText(entry.isCollection()?"":entry.id);row.number.setVisibility(entry.isCollection()?View.GONE:View.VISIBLE);row.star.setVisibility(entry.favorite?View.VISIBLE:View.GONE);
            row.bindChoice(batchMode&&!entry.isCollection(),selected.contains(entry.uri),entry.uri.equals(row.boundUri));row.boundUri=entry.uri;
            row.text.setSelected(true);
            Cover cover=coverCache.get(entry.uri);Bitmap bitmap=cover==null?null:cover.bitmap;
            row.image.setImageBitmap(bitmap);row.image.setContentDescription(entry.isCollection()?"收藏夹内漫画封面预览":bitmap==null?"暂无封面":"第一页封面");row.placeholder.setText(entry.isCollection()?"收藏夹":"暂无\n封面");row.placeholder.setVisibility(bitmap==null?View.VISIBLE:View.GONE);
            if(cover==null&&!coverPending.contains(entry.uri)&&!coverWorker.isShutdown()){
                final int ticket=coverGeneration;coverPending.add(entry.uri);
                final List<LibraryStore.Entry> previews=collectionPreviews.getOrDefault(entry.uri,Collections.emptyList());
                try{coverWorker.execute(()->{Bitmap result=entry.isCollection()?CollectionCover.load(activity.getApplicationContext(),previews):LibraryCover.load(activity.getApplicationContext(),entry);main.post(()->{
                    if(!visible()||ticket!=coverGeneration)return;coverPending.remove(entry.uri);coverCache.put(entry.uri,new Cover(result));adapter.notifyDataSetChanged();
                });});}catch(RejectedExecutionException error){coverPending.remove(entry.uri);}
            }
            return row;
        }
    }
    private void cancel(){cancelled.set(true);if(scanSignal!=null)scanSignal.cancel();if(updateControl!=null)updateControl.cancel("检查已取消");}
    private void counts(){selectionTitle.setText("已选中"+selected.size()+"项");status.setText("共 "+entries.size()+" 项"+(batchMode?"，已选 "+selected.size()+" 项":"")+(report.isEmpty()?"":"\n"+report));modeButton.setEnabled(!busy&&!loading);backButton.setEnabled(!busy&&!loading&&!collection.isEmpty());for(int i=0;i<displaySelector.getChildCount();i++)displaySelector.getChildAt(i).setEnabled(!busy&&!loading);for(Button b:singleButtons)b.setEnabled(!busy&&!loading&&selected.size()==1);for(Button b:batchButtons)b.setEnabled(!busy&&!loading&&!selected.isEmpty());}
    private void select(int mode){if(busy||loading||!batchMode)return;for(int i=0;i<entries.size();i++){LibraryStore.Entry entry=entries.get(i);if(entry.isCollection())continue;String uri=entry.uri;boolean checked=mode==0||(mode==1&&!selected.contains(uri));if(checked)selected.add(uri);else selected.remove(uri);list.setItemChecked(i,checked);}counts();}
    private List<LibraryStore.Entry> selection(){List<LibraryStore.Entry> result=new ArrayList<>();for(LibraryStore.Entry e:entries)if(!e.isCollection()&&selected.contains(e.uri))result.add(e);return result;}
    private void acceptEntries(List<LibraryStore.Entry> result){
        loading=false;entries=result;Set<String> present=new HashSet<>();list.clearChoices();
        for(LibraryStore.Entry e:result)if(!e.isCollection())present.add(e.uri);selected.retainAll(present);
        for(int i=0;i<entries.size();i++)list.setItemChecked(i,selected.contains(entries.get(i).uri));
        adapter.notifyDataSetChanged();restoreViewport(pendingViewState);pendingViewState=null;list.setEnabled(true);counts();
    }
    private void load(){
        if(!visible()||busy)return;
        final int ticket=++generation;String search=query.getText().toString();boolean only=favorites.isChecked();String requestedCollection=collection;String nextFilter=search+"|"+only+"|"+collection;
        if(!filter.equals(nextFilter)){selected.clear();filter=nextFilter;pendingViewState=new Bundle();}
        else if(pendingViewState==null)pendingViewState=viewportState();
        loading=true;counts();status.setText("正在读取…");list.setEnabled(false);
        worker.execute(()->{
            try{
                library=LibraryStore.get(activity);library.sync(store.snapshot());
                String folder=library.collectionName(requestedCollection)==null?"":requestedCollection;
                List<LibraryStore.Entry> result=LibrarySort.sorted(activity,library.browse(search,only,folder),sort);Map<String,List<LibraryStore.Entry>> previews=library.collectionPreviews();String name=library.collectionName(folder);
                main.post(()->{if(!visible()||ticket!=generation)return;collection=folder;breadcrumb.setText(folder.isEmpty()?"漫画库（默认收藏夹）":"漫画库 / "+name);collectionPreviews=previews;resetCovers();acceptEntries(result);prepareChapterCounts();});
            }catch(Exception error){main.post(()->{if(visible()&&ticket==generation){loading=false;list.setEnabled(true);counts();status.setText(error.getMessage());}});}
        });
    }
    private interface Operation{String run()throws Exception;}
    private void perform(Operation operation,Runnable success){
        if(busy||loading||!visible())return;busy=true;generation++;cancelled.set(false);stop.setEnabled(true);list.setEnabled(false);query.setEnabled(false);favorites.setEnabled(false);if(dialog!=null)dialog.setCancelable(false);counts();status.setText("正在处理…");
        worker.execute(()->{String failure=null,result="";try{library=LibraryStore.get(activity);result=operation.run();}catch(OperationCanceledException | CancellationException e){result="操作已取消，未导入文件";}catch(SecurityException e){failure="目录授权失效或没有写入权限，请重新选择原保存目录授权后重试。";}catch(Exception e){failure=e.getMessage()==null?e.getClass().getSimpleName():e.getMessage();}
            final String error=failure,done=result;main.post(()->{busy=false;scanSignal=null;if(!visible())return;stop.setEnabled(false);list.setEnabled(true);query.setEnabled(true);favorites.setEnabled(true);if(dialog!=null)dialog.setCancelable(true);report=error==null?done:"操作未完成";if(error!=null)message(error);else if(success!=null)success.run();load();});});
    }
    private void message(String text){if(visible())new AlertDialog.Builder(activity).setMessage(text).setPositiveButton("确定",null).show();}
    private void navigate(String key){
        if(busy||loading)return;
        if(!moving)setBatchMode(false);collection=key;pendingViewState=new Bundle();
        // Suppress intermediate text/filter loads while resetting navigation.
        busy=true;query.setText("");favorites.setChecked(false);busy=false;
        query.clearFocus();list.requestFocus();load();
    }
    private void editCollection(String key){
        LinearLayout body=Ui.column(activity);TextView title=Ui.heading(activity,key==null?"新建收藏夹":"重命名收藏夹");title.setGravity(Gravity.CENTER);body.addView(title);EditText name=Ui.input(activity,"请输入名称",false);name.setSingleLine(true);if(key!=null)name.setText(library.collectionName(key));body.addView(name);Ui.gap(body,18);AlertDialog modal=Ui.modal(activity,body,false);Button accept=Ui.button(activity,"确认",()->{String value=name.getText().toString().trim();if(value.isEmpty()||value.length()>40){name.setError("请输入 1–40 个字符");return;}modal.dismiss();perform(()->{if(key==null)library.createCollection(value);else library.renameCollection(key,value);return "收藏夹已保存";},null);});Ui.primary(accept);body.addView(Ui.pair(activity,accept,Ui.button(activity,"取消",modal::dismiss)));modal.show();
    }
    private interface CollectionChoice {void chosen(String key);}
    private void chooseCollection(String title,boolean includeDefault,CollectionChoice action){
        try{
            LinkedHashMap<String,String> choices=new LinkedHashMap<>();if(includeDefault)choices.put("","漫画库（默认收藏夹）");choices.putAll(library.collections());
            if(choices.isEmpty()){message("请先新建收藏夹");return;}
            List<String> keys=new ArrayList<>(choices.keySet());new AlertDialog.Builder(activity).setTitle(title).setItems(choices.values().toArray(new String[0]),(d,i)->action.chosen(keys.get(i))).setNegativeButton("取消",null).show();
        }catch(Exception error){message(error.getMessage());}
    }
    private void manageCollection(){if(!collection.isEmpty())manageCollection(collection);else chooseCollection("选择要管理的收藏夹",false,this::manageCollection);}
    private void manageCollection(String key){
        new AlertDialog.Builder(activity).setTitle(library.collectionName(key)).setItems(new String[]{"打开收藏夹","重命名","删除收藏夹"},(d,i)->{
            if(i==0)navigate(key);
            else if(i==1)editCollection(key);
            else new AlertDialog.Builder(activity).setTitle("删除收藏夹").setMessage("仅删除收藏夹，其中漫画将回到漫画库。文件、星标和阅读记录保留。")
                .setNegativeButton("取消",null).setPositiveButton("删除收藏夹",(confirm,w)->perform(()->{library.deleteCollection(key);return "收藏夹已删除，漫画已回到漫画库";},()->{if(collection.equals(key))collection="";})).show();
        }).setNegativeButton("关闭",null).show();
    }
    private void moveToCollection(){
        List<LibraryStore.Entry> items=selection();if(items.isEmpty())return;
        chooseCollection("移入收藏夹",true,key->perform(()->"已将 "+library.moveToCollection(items,key)+" 本漫画移入"+library.collectionName(key),null));
    }
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
        List<LibraryStore.Entry> items=selection();if(items.isEmpty())return;
        if(!delete){Ui.confirm(activity,"是否移除记录（文件保留）",()->perform(()->library.removeMany(store,items,false,cancelled::get,(d,t)->{}).summary(),null));return;}
        Map<String,ChapterDeletion.Plan> plans=new LinkedHashMap<>();
        perform(()->{for(LibraryStore.Entry item:items)plans.put(item.uri,ChapterDeletion.inspect(activity,item,cancelled::get));return "请选择要删除的文件或章节";},()->{
            LinearLayout choices=Ui.column(activity);Map<String,Set<Integer>> removed=new LinkedHashMap<>();
            for(LibraryStore.Entry item:items){ChapterDeletion.Plan plan=plans.get(item.uri);Set<Integer> selectedChapters=new LinkedHashSet<>(plan.counts.keySet());removed.put(item.uri,selectedChapters);if(plan.counts.size()<2)continue;choices.addView(Ui.text(activity,title(item),14));
                for(Integer chapter:plan.counts.keySet()){CheckBox choice=new CheckBox(activity);choice.setText(plan.counts.size()>1?"第 "+chapter+" 章 · "+plan.counts.get(chapter)+" 页":"整本漫画");choice.setChecked(true);choice.setOnCheckedChangeListener((v,on)->{if(on)selectedChapters.add(chapter);else selectedChapters.remove(chapter);});choices.addView(choice);}}
            ScrollView scroll=new ScrollView(activity);scroll.addView(choices);scroll.setLayoutParams(new LinearLayout.LayoutParams(-1,Math.min(dp(300),dp(64)*items.size()+dp(36)*plans.values().stream().mapToInt(p->p.counts.size()).sum())));
            Ui.confirm(activity,"是否删除文件",choices.getChildCount()==0?null:scroll,()->perform(()->{List<LibraryStore.Entry> full=new ArrayList<>();StringBuilder result=new StringBuilder();for(LibraryStore.Entry item:items){Set<Integer> selectedChapters=removed.get(item.uri);ChapterDeletion.Plan plan=plans.get(item.uri);if(selectedChapters.isEmpty())continue;if(selectedChapters.size()==plan.counts.size())full.add(item);else result.append(ChapterDeletion.delete(activity,store,item,plan,selectedChapters,cancelled::get,text->{})).append("\n");}if(!full.isEmpty())result.append(library.removeMany(store,full,true,cancelled::get,(d,t)->{}).summary());return result.toString();},()->setBatchMode(false)));
        });
    }
    private void sortCached(){
        try{
            pendingViewState=viewportState();
            acceptEntries(LibrarySort.sorted(activity,library.browse(query.getText().toString(),favorites.isChecked(),collection),sort));
        }catch(Exception error){message(error.getMessage());}
    }
    private void prepareChapterCounts(){
        if(chapterScanning||!visible())return;
        List<LibraryStore.Entry> pending=new ArrayList<>();
        try{for(LibraryStore.Entry item:library.list("",false))if(item.chapterCount<0&&chapterScanAttempted.add(item.uri))pending.add(item);}
        catch(Exception error){status.setText(error.getMessage());return;}
        if(pending.isEmpty())return;chapterScanning=true;
        worker.execute(()->{
            boolean changed=false;String failure=null;
            try{changed=library.fillChapterCounts(pending);}catch(Exception error){failure=error.getMessage();}
            final boolean updated=changed;final String problem=failure;
            main.post(()->{
                chapterScanning=false;if(!visible())return;
                if(problem!=null){status.setText("章节信息保存失败："+problem);return;}
                if(updated&&sort.equals("chapters")&&!busy&&!loading)sortCached();
                prepareChapterCounts();
            });
        });
    }
    private void sortMenu(){PopupMenu menu=new PopupMenu(activity,sortButton);String[] names={"名称","时间","大小","章节数"},values={"name","time","size","chapters"};for(int i=0;i<names.length;i++)menu.getMenu().add(0,i,i,names[i]);menu.setOnMenuItemClickListener(item->{sort=values[item.getItemId()];if(sort.equals("chapters")||sort.equals("name"))sortCached();else load();return true;});menu.show();}

    private void shareSelection(){List<LibraryStore.Entry> items=selection();ArrayList<Uri> uris=new ArrayList<>();for(LibraryStore.Entry item:items){if(item.format.equals("images")){message("图片文件夹请先导出为 pdf 或 zip 后分享");return;}uris.add(Uri.parse(item.uri));}if(uris.isEmpty())return;Intent intent=new Intent(Intent.ACTION_SEND_MULTIPLE).setType("application/octet-stream").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.putParcelableArrayListExtra(Intent.EXTRA_STREAM,uris);android.content.ClipData clip=android.content.ClipData.newRawUri("漫画",uris.get(0));for(int i=1;i<uris.size();i++)clip.addItem(new android.content.ClipData.Item(uris.get(i)));intent.setClipData(clip);try{activity.startActivity(Intent.createChooser(intent,"分享"));}catch(Exception error){message("没有支持分享的应用");}}
    private void beginMove(){movingItems=selection();if(movingItems.isEmpty())return;moveOrigin=collection;moving=true;batchMode=false;selected.clear();list.clearChoices();batchActions.setVisibility(View.GONE);selectionTitle.setVisibility(View.GONE);moveBar.setVisibility(View.VISIBLE);collection="";load();}
    private void cancelMove(){moving=false;movingItems=null;collection=moveOrigin;sheet.setVisibility(View.GONE);load();}
    private void commitMove(){List<LibraryStore.Entry> items=movingItems;if(items==null)return;String target=collection;perform(()->"已移动 "+library.moveToCollection(items,target)+" 本漫画",()->{moving=false;movingItems=null;sheet.setVisibility(View.GONE);});}
    private void checkAllUpdates(){
        if(checkingAll){Ui.notice(activity,"正在检查章节更新");return;}checkingAll=true;Ui.notice(activity,"开始检查章节更新");Store.Settings options=new Store.Settings(store.settings.json());String cookie=store.cookie;
        updateWorker.execute(()->{List<LibraryStore.Entry> changed=new ArrayList<>();Map<String,ChapterUpdates.Result> results=new LinkedHashMap<>();int failures=0;JmApi.Control control=new JmApi.Control();updateControl=control;
            try{ChapterUpdates.record(activity,store.snapshot());Set<String> seen=new HashSet<>();for(LibraryStore.Entry item:library.list("",false)){if(!item.id.matches("[0-9]{1,10}")||!seen.add(item.id))continue;control.check();try{if(ChapterDeletion.inspect(activity,item,()->!control.stop.isEmpty()).counts.size()<2)continue;List<ChapterRules.Chapter> catalog=chapterUpdateFetch.get(item.id,options,cookie,control);if(catalog.size()<2)continue;ChapterUpdates.Result result=ChapterUpdates.compare(activity,item.id,catalog);if(!result.fresh.isEmpty()){changed.add(item);results.put(item.uri,result);}}catch(Exception e){if(!control.stop.isEmpty())break;failures++;}}}catch(Exception e){failures++;}finally{control.cancel("检查结束");updateControl=null;}
            final int failed=failures;main.post(()->{checkingAll=false;if(!visible())return;Ui.notice(activity,"检查完成"+(failed>0?"，"+failed+" 项失败":""));if(changed.isEmpty())return;StringBuilder text=new StringBuilder("发现新章节，是否下载？");for(LibraryStore.Entry item:changed)text.append("\n").append(item.title).append(" · ").append(results.get(item.uri).fresh.size()).append(" 章");Ui.confirm(activity,text.toString(),()->{try{for(LibraryStore.Entry item:changed){ChapterUpdates.Result result=results.get(item.uri);store.addChapterUpdate(item.id,result.catalog,result.fresh,options);}if(!store.running)activity.startForegroundService(new Intent(activity,DownloadService.class).setAction(DownloadService.SELECTED));Ui.notice(activity,"新章节已加入下载队列");}catch(Exception e){message(e.getMessage());}});});
        });
    }
    private void details(LibraryStore.Entry entry){
        new AlertDialog.Builder(activity).setTitle(title(entry)).setItems(new String[]{"开始阅读","分享文件",entry.favorite?"取消收藏":"加入收藏","打开保存目录","应用内查看目录","导出漫画","删除章节","检查更新"},(d,index)->{
            if(index==7){checkUpdates(entry);return;}
            if(index==6){deleteChapters(entry);return;}
            if(index==0){read(entry);return;}
            if(index==1&&entry.format.equals("images")){message("图片文件夹请先导出为 ZIP 或 PDF 后分享。");return;}
            if(index==5){new ExportScreen(activity,store,Collections.singletonList(entry),this::load).show();return;}
            if(index==0||index==1)perform(()->{library.check(entry);return "";},()->open(entry,index==1));
            else if(index==2)perform(()->{library.favorite(entry);return "已更新收藏";},null);
            else if(index==3)new SavedDirectory(activity,entry.tree,entry.label).openExternal();
            else new SavedDirectory(activity,entry.tree,entry.label).show();
        }).setNegativeButton("关闭",null).show();
    }
    private void checkUpdates(LibraryStore.Entry entry){
        if(!entry.id.matches("[0-9]{1,10}")){message("这条漫画记录没有有效的 JM 编号，无法检查更新。");return;}
        Store.Settings options=new Store.Settings(store.settings.json());String cookie=store.cookie;
        final ChapterUpdates.Result[] result=new ChapterUpdates.Result[1];
        perform(()->{
            JmApi.Control control=new JmApi.Control();updateControl=control;
            try{
                if(cancelled.get())throw new OperationCanceledException();
                List<ChapterRules.Chapter> catalog=chapterUpdateFetch.get(entry.id,options,cookie,control);
                if(cancelled.get())throw new OperationCanceledException();
                ChapterUpdates.record(activity,store.snapshot());result[0]=ChapterUpdates.compare(activity,entry.id,catalog);
                return "章节目录检查完成";
            }finally{updateControl=null;control.cancel("检查结束");}
        },()->{
            if(cancelled.get()||result[0]==null)return;
            ChapterUpdates.Result update=result[0];
            if(update.initialized){message("缺少原下载章节记录，已记录当前目录作为检查起点；以后可检查新增章节。");return;}
            if(update.fresh.isEmpty()){message("检查完成，暂无新章节。");return;}
            StringBuilder text=new StringBuilder("发现 "+update.fresh.size()+" 个新章节。\n");
            for(int i=0;i<Math.min(20,update.fresh.size());i++){ChapterRules.Chapter c=update.fresh.get(i);text.append("\n第 ").append(c.number).append(" 章 · ").append(c.title);}
            if(update.fresh.size()>20)text.append("\n……另 ").append(update.fresh.size()-20).append(" 章");
            text.append("\n\n是否使用正常下载功能下载？\n保存为独立漫画，原漫画保留。\n保存目录：").append(options.outputLabel).append("\n格式：").append(options.format.toUpperCase(Locale.ROOT));
            new AlertDialog.Builder(activity).setTitle("漫画章节更新").setMessage(text)
                .setNegativeButton("暂不下载",null).setPositiveButton("下载新章节",(d,w)->{
                    try{
                        store.addChapterUpdate(entry.id,update.catalog,update.fresh,options);
                        report="新章节已加入正常下载队列";
                        if(!store.running)activity.startForegroundService(new Intent(activity,DownloadService.class).setAction(DownloadService.SELECTED));
                    }catch(Exception error){message("无法开始下载："+error.getMessage()+"\n已入队的任务可在下载页继续。");}
                }).show();
        });
    }
    private void deleteChapters(LibraryStore.Entry entry){
        final ChapterDeletion.Plan[] result=new ChapterDeletion.Plan[1];
        perform(()->{result[0]=ChapterDeletion.inspect(activity,entry,cancelled::get,text->main.post(()->{if(visible())status.setText(text);}));return "请选择要删除的章节";},()->{
            ChapterDeletion.Plan plan=result[0];if(plan==null)return;
            if(plan.counts.size()<=1){message("本书仅识别到一个章节。PDF 或平铺 ZIP 没有可分辨的分章信息；删除整本请使用“删除文件”。");return;}
            List<Integer> chapters=new ArrayList<>(plan.counts.keySet());String[] labels=new String[chapters.size()];Set<Integer> removed=new HashSet<>();
            for(int i=0;i<labels.length;i++)labels[i]="第 "+chapters.get(i)+" 章 · "+plan.counts.get(chapters.get(i))+" 页";
            AlertDialog picker=new AlertDialog.Builder(activity).setTitle("删除章节（至少保留一章）")
                .setMultiChoiceItems(labels,new boolean[labels.length],(d,index,checked)->{if(checked)removed.add(chapters.get(index));else removed.remove(chapters.get(index));})
                .setNegativeButton("取消",null).setPositiveButton("删除所选章节",null).create();
            picker.setOnShowListener(d->picker.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
                if(removed.isEmpty()||removed.size()==chapters.size()){message("请选择要删除的章节，并至少保留一章。");return;}
                int pages=0;StringBuilder names=new StringBuilder();for(int c:chapters)if(removed.contains(c)){pages+=plan.counts.get(c);names.append("第 ").append(c).append(" 章、");}
                new AlertDialog.Builder(activity).setTitle("确认删除章节").setMessage("将永久删除 "+removed.size()+" 章，共 "+pages+" 页。\n"+names+"\n\n删除页的书签会移除。先校验保留章节再替换漫画，文件名会更新，需要临时可用空间；不进入回收站。")
                    .setNegativeButton("取消",null).setPositiveButton("删除章节",(confirm,which)->{
                        if(busy||loading){message("漫画库正在刷新，请稍后再次确认。");return;}
                        picker.dismiss();Set<Integer> selection=new HashSet<>(removed);
                        perform(()->ChapterDeletion.delete(activity,store,entry,plan,selection,cancelled::get,text->main.post(()->{if(visible())status.setText(text);})),()->{if(report.contains("清理未完成"))message(report);});
                    }).show();
            }));picker.show();
        });
    }
    private void open(LibraryStore.Entry entry,boolean share){
        if(!share){read(entry);return;}
        Uri uri=Uri.parse(entry.uri);String mime=entry.format.equals("pdf")?"application/pdf":"application/zip";
        Intent intent=new Intent(share?Intent.ACTION_SEND:Intent.ACTION_VIEW).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("漫画",uri));
        if(share){intent.setType(mime);intent.putExtra(Intent.EXTRA_STREAM,uri);}else intent.setDataAndType(uri,mime);
        try{activity.startActivity(Intent.createChooser(intent,share?"分享文件":"打开文件"));}catch(Exception e){message("没有支持此格式的应用，或文件权限不可用。");}
    }
}
