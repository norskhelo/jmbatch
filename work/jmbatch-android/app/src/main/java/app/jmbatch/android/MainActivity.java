package app.jmbatch.android;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.DocumentsContract;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;

public final class MainActivity extends Activity {
    private final int BG=Ui.BG,INK=Ui.INK,MUTED=Ui.MUTED,ACCENT=Ui.ACCENT;
    private Store store;
    private GithubUpdates updates;
    private DownloadCovers downloadCovers;
    private LinearLayout layout,taskActions;
    private LinearLayout queue;
    private InputFocusLayout inputFocus;
    private LinearLayout shell;
    private View settingsPage;
    private SettingsScreen settingsScreen;
    private android.animation.ValueAnimator settingsAnimation;
    private LibraryScreen libraryScreen;
    private EditText ids,rangeFirst,rangeLast;
    private TextView output,summary,global;
    private Button start,pause,more;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Map<String,Row> rows=new LinkedHashMap<>();
    private int limit=50;
    private FrameLayout pages,downloadPage,libraryHost;
    private LinearLayout taskSheet;
    private FrameLayout downloadPanel;
    private View pageSwitch;
    private int pageOffset;

    private PageExchange pageExchange;

    private TextView selectedCount;
    private final Set<String> selected=new LinkedHashSet<>();
    private final Map<String,String> previousStates=new HashMap<>();
    private boolean selecting,libraryVisible;
    private AlertDialog addDialog;
    FrameLayout libraryHost(){return libraryHost;}
    void hideLibrary(){setFrontPage(false,true);render();}
    @Override public void onBackPressed(){if(settingsAnimation!=null)return;if(settingsPage!=null){closeSettings();return;}if(pageExchange!=null)return;if(libraryVisible){if(libraryScreen==null||!libraryScreen.back())hideLibrary();return;}if(selecting){exitSelection();return;}super.onBackPressed();}
    @Override public boolean dispatchTouchEvent(MotionEvent event){return pageExchange!=null||settingsAnimation!=null||super.dispatchTouchEvent(event);}
    @Override public boolean dispatchGenericMotionEvent(MotionEvent event){return pageExchange!=null||settingsAnimation!=null||super.dispatchGenericMotionEvent(event);}
    @Override public boolean dispatchKeyEvent(KeyEvent event){return pageExchange!=null||settingsAnimation!=null||super.dispatchKeyEvent(event);}

    private AlertDialog chapterDialog;
    private Store.Task chapterTask;
    private final Runnable refresh=new Runnable(){public void run(){render();handler.postDelayed(this,700);}};

    public void onCreate(Bundle state){
        super.onCreate(state);store=Store.get(this);downloadCovers=new DownloadCovers(this);
        for(Store.Task task:store.snapshot())if(task.discardRequested&&task.status.equals("cancelling")){send(DownloadService.CLEANUP,null);break;}
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        inputFocus=new InputFocusLayout(this);inputFocus.setBackgroundColor(BG);setContentView(inputFocus);
        shell=column();shell.setPadding(dp(16),dp(12),dp(16),dp(12));inputFocus.addView(shell,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout header=horizontal(),brandBox=column();TextView brand=text("JM Batch",26,INK);brand.setTypeface(null,Typeface.BOLD);brandBox.addView(brand);brandBox.addView(text("ver "+Core.VERSION,12,MUTED));header.addView(brandBox,new LinearLayout.LayoutParams(0,-2,1));Button settingsButton=button("⚙",v->settings());settingsButton.setContentDescription("设置");settingsButton.setTooltipText("设置");settingsButton.setTextSize(28);Ui.smallIconGlyph(settingsButton);Ui.square(settingsButton);header.addView(settingsButton,new LinearLayout.LayoutParams(-2,-2));shell.addView(header);
        Button updateButton=button("检查更新",v->{});updates=new GithubUpdates(this,updateButton);handler.postDelayed(()->updates.startup(),1500);
        pages=new FrameLayout(this);LinearLayout.LayoutParams pageParams=new LinearLayout.LayoutParams(-1,0,1);pageParams.topMargin=dp(12);shell.addView(pages,pageParams);
        pageOffset=Math.max(dp(124),(int)(getResources().getDisplayMetrics().heightPixels*.14))+dp(28);
        pages.setBackground(Ui.shape(this,BG,18,false));pages.setClipToOutline(true);
        FrameLayout panel=downloadPanel=new FrameLayout(this);downloadPage=panel;panel.setBackground(pageBackground(false));pages.addView(panel,new FrameLayout.LayoutParams(-1,-1));
        layout=column();layout.setPadding(dp(14),dp(10),dp(14),dp(12));panel.addView(layout,new FrameLayout.LayoutParams(-1,-1));layout.addView(Ui.heading(this,"下载页面"));
        start=buttonAccent("开始全部",v->{if(store.running)send(DownloadService.PAUSE,null);else startQueue();});pause=button("暂停全部",v->send(DownloadService.PAUSE,null));
        taskActions=horizontal();taskActions.addView(start,new LinearLayout.LayoutParams(-2,-2));Button clear=Ui.iconButton(this,"trash","清除下载记录",()->confirmRemoval(this::clearHistory));LinearLayout.LayoutParams clearParams=new LinearLayout.LayoutParams(-2,-2);clearParams.leftMargin=dp(8);taskActions.addView(clear,clearParams);layout.addView(taskActions);
        summary=text("",12,MUTED);global=text("",12,MUTED);
        FrameLayout listPanel=new FrameLayout(this);listPanel.setBackground(Ui.shape(this,Color.WHITE,18,true));LinearLayout.LayoutParams listParams=new LinearLayout.LayoutParams(-1,0,1);listParams.topMargin=dp(16);listParams.bottomMargin=dp(12);layout.addView(listPanel,listParams);
        LinearLayout listBody=column();listBody.setPadding(dp(18),dp(10),dp(18),dp(22));listPanel.addView(listBody,new FrameLayout.LayoutParams(-1,-1));TextView listTitle=Ui.heading(this,"下载列表");listTitle.setTextSize(17);listBody.addView(listTitle);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setOnScrollChangeListener((view,x,y,oldX,oldY)->{refreshDownloadCovers();if(y>oldY&&y+scroll.getHeight()>=queue.getHeight()-dp(50)&&limit<store.snapshot().size()){limit+=50;render();}});
        queue=column();scroll.addView(queue);listBody.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));more=button("显示更多任务",v->{limit+=50;render();});
        TextView hint=text("点击任务停止 · 长按批量操作",12,MUTED);hint.setGravity(Gravity.CENTER);hint.setPadding(0,dp(16),0,dp(4));listBody.addView(hint);
        Button add=buttonAccent("＋",v->addDownload());add.setTextSize(Ui.ADD_ACTION_TEXT_SIZE);Ui.square(add);add.setContentDescription("添加下载");add.setBackground(Ui.circle(ACCENT));add.setElevation(dp(5));FrameLayout.LayoutParams fab=new FrameLayout.LayoutParams(-2,Ui.controlHeight(add),Gravity.BOTTOM|Gravity.RIGHT);fab.setMargins(0,0,dp(16),dp(14));listPanel.addView(add,fab);hint.setPadding(0,dp(16),Ui.controlHeight(add)+dp(16),dp(4));
        taskSheet=column();taskSheet.setPadding(dp(18),dp(20),dp(18),dp(24));taskSheet.setBackground(Ui.shape(this,Color.WHITE,18,true));taskSheet.setElevation(dp(10));selectedCount=text("",16,INK);selectedCount.setGravity(Gravity.CENTER);selectedCount.setTypeface(null,Typeface.BOLD);taskSheet.addView(selectedCount);Ui.gap(taskSheet,20);taskSheet.addView(Ui.pair(this,buttonAccent("删除任务",v->removeSelected()),button("返回",v->exitSelection())));FrameLayout.LayoutParams sheetParams=new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM);panel.addView(taskSheet,sheetParams);taskSheet.setVisibility(View.GONE);
        libraryHost=new FrameLayout(this);libraryHost.setBackground(pageBackground(false));pages.addView(libraryHost,new FrameLayout.LayoutParams(-1,-1));
        pageSwitch=new View(this){
            final android.graphics.Paint paint=new android.graphics.Paint(3);
            android.graphics.Bitmap strip;
            @Override protected void onDraw(android.graphics.Canvas canvas){
                View rear=libraryVisible?downloadPanel:libraryHost;
                float boundary=pageOffset,opacity=1;
                if(pageExchange!=null){
                    boolean swapped=pageExchange.progress>=1f/3f;
                    rear=swapped?pageExchange.outgoing:pageExchange.incoming;
                    boundary=(swapped?pageExchange.incoming:pageExchange.outgoing).getTranslationY();
                    opacity=pageExchange.outgoing.getAlpha();
                }
                int header=(rear==libraryHost&&libraryScreen!=null?libraryScreen.headerBottom():taskActions.getBottom())+Math.round(rear.getTranslationY());
                int bottom=Math.min(getHeight(),Math.round(boundary)),band=Math.max(0,Math.min(dp(54),bottom-header-dp(4))),edge=dp(14),top=bottom-band;
                if(rear.getWidth()<2||band<1)return;
                // Only this narrow seam is sampled. The two full pages remain live views.
                int w=Math.max(1,getWidth()/8),h=Math.max(1,band/8);
                if(strip==null||strip.getWidth()!=w||strip.getHeight()!=h)strip=android.graphics.Bitmap.createBitmap(w,h,android.graphics.Bitmap.Config.ARGB_8888);
                strip.eraseColor(Color.WHITE);
                android.graphics.Canvas small=new android.graphics.Canvas(strip);small.scale(w/(float)getWidth(),h/(float)band);small.translate(0,-top+rear.getTranslationY());rear.draw(small);
                int saved=canvas.saveLayerAlpha(edge,top,getWidth()-edge,bottom,Math.round(255*opacity));canvas.clipRect(edge,top,getWidth()-edge,bottom);
                int layer=canvas.saveLayer(edge,top,getWidth()-edge,bottom,null);
                canvas.drawBitmap(strip,null,new android.graphics.Rect(0,top,getWidth(),bottom),paint);
                paint.setShader(new android.graphics.LinearGradient(0,top,0,bottom,0x00ffffff,0xffffffff,android.graphics.Shader.TileMode.CLAMP));paint.setXfermode(new android.graphics.PorterDuffXfermode(android.graphics.PorterDuff.Mode.DST_IN));canvas.drawRect(edge,top,getWidth()-edge,bottom,paint);paint.setXfermode(null);canvas.restoreToCount(layer);
                paint.setShader(new android.graphics.LinearGradient(0,top,0,bottom,new int[]{0x00ffffff,0x00ffffff,0xffffffff},null,android.graphics.Shader.TileMode.CLAMP));canvas.drawRect(edge,top,getWidth()-edge,bottom,paint);paint.setShader(null);canvas.restoreToCount(saved);
            }
        };
        final float[] touch={0,0};final boolean[] click={false};final int slop=ViewConfiguration.get(this).getScaledTouchSlop();
        pageSwitch.setOnTouchListener((v,e)->{switch(e.getActionMasked()){
            case MotionEvent.ACTION_DOWN:touch[0]=e.getX();touch[1]=e.getY();click[0]=e.getY()<pageOffset;return true;
            case MotionEvent.ACTION_MOVE:if(Math.abs(e.getX()-touch[0])+Math.abs(e.getY()-touch[1])>slop)click[0]=false;return true;
            case MotionEvent.ACTION_UP:if(pageExchange==null&&click[0]&&e.getY()<pageOffset)setFrontPage(!libraryVisible,true);click[0]=false;return true;
            case MotionEvent.ACTION_CANCEL:click[0]=false;return true;
            default:return true;
        }});
        pages.addView(pageSwitch,new FrameLayout.LayoutParams(-1,pageOffset));
        pages.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{if(r-l!=or-ol||b-t!=ob-ot){finishPageExchange();layoutPages();}});
        output=text(OutputDirectory.display(this,store.settings.outputUri),14,INK);inputFocus.requestFocus();
        if(!store.note.isEmpty())toast(store.note);
        GalleryPrivacy.start(this,store);
        libraryScreen=new LibraryScreen(this,store);libraryScreen.show(state==null?null:state.getBundle("library"));
        libraryVisible=state!=null&&state.getBoolean("libraryVisible",false);
        pages.post(()->{layoutPages();settlePages();});
    }

    private android.graphics.drawable.Drawable pageBackground(boolean rear){
        android.graphics.drawable.Drawable surface=Ui.shape(this,Color.WHITE,18,true);
        // The rear page continues behind the front page without an exposed bottom corner.
        if(rear)return new android.graphics.drawable.InsetDrawable(surface,0,0,0,-dp(36));
        // Reveal the continuous rear surface only through the top corners.
        android.graphics.drawable.Drawable backing=new android.graphics.drawable.ColorDrawable(BG){
            @Override public void draw(android.graphics.Canvas canvas){
                android.graphics.Rect b=getBounds();int save=canvas.save();
                canvas.clipRect(b.left,b.top+dp(18),b.right,b.bottom);super.draw(canvas);canvas.restoreToCount(save);
            }
        };
        return new android.graphics.drawable.LayerDrawable(new android.graphics.drawable.Drawable[]{backing,surface});
    }

    private void showLibrary(){setFrontPage(true,true);}
    private void layoutPages(){
        int height=pages.getHeight();if(height<2)return;
        int compact=Math.max(dp(124),(int)(getResources().getDisplayMetrics().heightPixels*.14))+dp(28);
        int header=Math.max(taskActions.getBottom(),libraryScreen==null?0:libraryScreen.headerBottom());
        pageOffset=Math.min(Math.max(compact,header+dp(16)),height/2);
        for(FrameLayout card:new FrameLayout[]{downloadPanel,libraryHost}){
            FrameLayout.LayoutParams p=(FrameLayout.LayoutParams)card.getLayoutParams();p.height=height+dp(28);p.topMargin=0;card.setLayoutParams(p);
        }
        FrameLayout.LayoutParams body=(FrameLayout.LayoutParams)layout.getLayoutParams();body.height=Math.max(1,height-pageOffset);layout.setLayoutParams(body);
        // The card extends below the viewport for page exchange; anchor actions to its visible body.
        FrameLayout.LayoutParams sheet=(FrameLayout.LayoutParams)taskSheet.getLayoutParams();
        sheet.bottomMargin=((FrameLayout.LayoutParams)downloadPanel.getLayoutParams()).height-body.height;taskSheet.setLayoutParams(sheet);
        if(libraryHost.getChildCount()>0){View child=libraryHost.getChildAt(0);FrameLayout.LayoutParams p=(FrameLayout.LayoutParams)child.getLayoutParams();p.height=Math.max(1,height-pageOffset);child.setLayoutParams(p);}
        settlePages();
    }
    private void settlePages(){
        downloadPanel.setTranslationY(libraryVisible?0:pageOffset);libraryHost.setTranslationY(libraryVisible?pageOffset:0);
        downloadPanel.setAlpha(1);libraryHost.setAlpha(1);
        downloadPanel.setLayerType(View.LAYER_TYPE_NONE,null);libraryHost.setLayerType(View.LAYER_TYPE_NONE,null);
        downloadPanel.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);libraryHost.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);
        (libraryVisible?libraryHost:downloadPanel).bringToFront();
        downloadPanel.setImportantForAccessibility(libraryVisible?View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS:View.IMPORTANT_FOR_ACCESSIBILITY_AUTO);
        libraryHost.setImportantForAccessibility(libraryVisible?View.IMPORTANT_FOR_ACCESSIBILITY_AUTO:View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        FrameLayout.LayoutParams hit=(FrameLayout.LayoutParams)pageSwitch.getLayoutParams();hit.height=pageOffset;pageSwitch.setLayoutParams(hit);
        pageSwitch.setContentDescription(libraryVisible?"下载页面":"漫画库");pageSwitch.bringToFront();pageSwitch.invalidate();
    }
    private void setFrontPage(boolean library,boolean animate){
        if(pageExchange!=null&&animate)return;
        finishPageExchange();if(library==libraryVisible){settlePages();return;}
        boolean previous=libraryVisible;libraryVisible=library;
        if(!animate||pages.getHeight()<2){settlePages();return;}
        pageExchange=new PageExchange(previous);
        downloadPanel.setDescendantFocusability(ViewGroup.FOCUS_BLOCK_DESCENDANTS);libraryHost.setDescendantFocusability(ViewGroup.FOCUS_BLOCK_DESCENDANTS);
        downloadPanel.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);libraryHost.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        // Only the input shield covers the views; it contains no page image.
        FrameLayout.LayoutParams hit=(FrameLayout.LayoutParams)pageSwitch.getLayoutParams();hit.height=-1;pageSwitch.setLayoutParams(hit);
        pageSwitch.bringToFront();pageSwitch.invalidate();inputFocus.requestFocus();
        pages.postOnAnimation(pageExchange);
    }
    private void finishPageExchange(){
        PageExchange exchange=pageExchange;pageExchange=null;
        if(exchange!=null){pages.removeCallbacks(exchange);libraryVisible=exchange.direction<0?exchange.sourceLibrary:!exchange.sourceLibrary;settlePages();}
    }
    private final class PageExchange implements Runnable {
        final boolean sourceLibrary;final View incoming,outgoing;int direction=1;float progress;long lastFrame=SystemClock.uptimeMillis();boolean incomingOnTop;
        PageExchange(boolean source){sourceLibrary=source;outgoing=source?libraryHost:downloadPanel;incoming=source?downloadPanel:libraryHost;}
        private float ease(float t){return t*t*(3-2*t);}
        @Override public void run(){
            if(pageExchange!=this)return;
            long now=SystemClock.uptimeMillis();progress=Math.max(0,Math.min(1,progress+direction*(now-lastFrame)/990f));lastFrame=now;
            boolean onTop=progress>=1f/3f;
            if(onTop!=incomingOnTop){incomingOnTop=onTop;(onTop?incoming:outgoing).bringToFront();pageSwitch.bringToFront();}
            if(!onTop){float t=ease(progress/(1f/3f));incoming.setTranslationY(-dp(28)*t);incoming.setAlpha(1);outgoing.setTranslationY(pageOffset);outgoing.setAlpha(1-t);}
            else{float t=ease((progress-1f/3f)/(2f/3f));incoming.setTranslationY(-dp(28)+(pageOffset+dp(28))*t);incoming.setAlpha(1);outgoing.setTranslationY(pageOffset*(1-t));outgoing.setAlpha(t);}
            pageSwitch.invalidate();
            if(direction>0&&progress>=1||direction<0&&progress<=0)finishPageExchange();else pages.postOnAnimation(this);
        }
    }
    private void refreshPreview(){if(libraryScreen!=null)libraryScreen.refresh();if(pageSwitch!=null)pageSwitch.invalidate();}
    private void addDownload(){
        LinearLayout body=column();ids=edit("请输入数字编号，多个编号请用空格隔开",false);ids.setTextSize(13);ids.setMinLines(1);ids.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);body.addView(ids);Ui.gap(body,14);
        RadioGroup formats=new RadioGroup(this);formats.setOrientation(RadioGroup.HORIZONTAL);String[] labels={"pdf","zip","文件夹"},values={"pdf","zip","images"};
        for(int i=0;i<values.length;i++){RadioButton b=new RadioButton(this);b.setId(View.generateViewId());b.setText(labels[i]);b.setTextColor(INK);b.setButtonTintList(android.content.res.ColorStateList.valueOf(ACCENT));b.setTag(values[i]);formats.addView(b,new RadioGroup.LayoutParams(0,-2,1));if(values[i].equals(store.settings.format))formats.check(b.getId());}body.addView(formats);Ui.gap(body,18);
        addDialog=Ui.modal(this,body,false,40,10);Button accept=buttonAccent("添加",v->{String format=(String)formats.findViewById(formats.getCheckedRadioButtonId()).getTag();store.settings.format=format;save();if(addIds(ids.getText().toString())){inputFocus.finishEditing();addDialog.dismiss();PermissionAccess.requestDownloadNotifications(this);startForegroundService(new Intent(this,DownloadService.class).setAction(DownloadService.SELECTED));}});ActionRow addActions=Ui.pair(this,accept,button("返回",v->addDialog.dismiss()));body.addView(addActions);addDialog.show();
    }
    private void selectTask(Store.Task task){if(!selecting){selecting=true;Ui.sheet(taskSheet);}if(!selected.add(task.key))selected.remove(task.key);render();}
    private void exitSelection(){selecting=false;selected.clear();taskSheet.setVisibility(View.GONE);render();}
    private void confirmRemoval(Runnable action){
        Ui.confirm(this,"是否删除任务记录",action);
    }
    private void removeSelected(){
        if(selected.isEmpty())return;
        Set<String> keys=new HashSet<>(selected);
        confirmRemoval(()->removeRecords(keys));
    }
    private void clickTask(Store.Task task){if(selecting){selectTask(task);return;}if(task.status.equals("running")||task.status.equals("resetting")){send(DownloadService.PAUSE_ONE,task.key);}else if(task.status.equals("failed")){retry(task);}else if(task.status.equals("done")){open(task,false);}else if(task.status.equals("paused")||task.status.equals("cancelled")){retry(task);}}
    @Override protected void onSaveInstanceState(Bundle state){
        super.onSaveInstanceState(state);state.putBoolean("libraryVisible",libraryVisible);if(libraryScreen!=null){Bundle library=libraryScreen.saveState();if(library!=null)state.putBundle("library",library);}
    }

    private void clearHistory(){removeRecords(null);}
    private void removeRecords(Set<String> keys){
        try{
            TaskRecordRemoval.Result result=TaskRecordRemoval.prepare(store,keys);
            if(result.cleaning>0)send(DownloadService.CLEANUP,null);
            if(keys!=null)exitSelection();else render();
            if(selecting&&selected.isEmpty())exitSelection();
            if(result.completed+result.cleaning>0){
                refreshPreview();
                String message=result.completed>0?"已清除 "+result.completed+" 条成功记录，成品保留":"";
                if(result.cleaning>0)message+=(message.isEmpty()?"":"；")+"正在清理 "+result.cleaning+" 条未成功任务及文件";
                if(result.remaining>0)message+="；其余 "+result.remaining+" 条任务已保留";
                toast(message);
            }else toast(result.remaining==0?"暂无下载记录可清除":"没有可清除的记录，请先暂停下载或等待文件清理完成");
        }catch(Exception error){render();showError("任务未删除完成："+error.getMessage());}
    }

    private boolean addIds(String value){try{int added=store.add(Core.parseIds(value),store.settings);toast("已添加 "+added+" 个任务，重复项自动跳过");render();return true;}catch(Exception error){showError(error.getMessage());return false;}}
    private void startQueue(){
        boolean ready=false;for(Store.Task t:store.snapshot())if(t.status.equals("queued")||t.status.equals("paused"))ready=true;
        if(!ready){toast("请添加任务，或在失败任务中选择重试");return;}
        PermissionAccess.requestDownloadNotifications(this);
        Intent intent=new Intent(this,DownloadService.class).setAction(DownloadService.START);startForegroundService(intent);
    }
    private void send(String action,String key){Intent intent=new Intent(this,DownloadService.class).setAction(action);if(key!=null)intent.putExtra("key",key);startService(intent);}

    private void refreshDownloadCovers(){
        for(Store.Task task:store.snapshot()){
            Row row=rows.get(task.key);
            if(row!=null)downloadCovers.bind(task,row.cover);
        }
    }

    private void render(){
        if(queue==null)return;
        List<Store.Task> tasks=store.snapshot();int completed=0,failed=0,active=0;long speed=0;
        Set<String> visible=new HashSet<>();
        for(int i=0;i<tasks.size();i++){
            Store.Task task=tasks.get(i);if(task.status.equals("done"))completed++;if(task.status.equals("failed"))failed++;if(task.status.equals("running")||task.status.equals("resetting")){active++;speed+=task.speed;}
            if(i>=limit)continue;visible.add(task.key);Row row=rows.get(task.key);if(row==null){row=new Row(task);rows.put(task.key,row);queue.addView(row.card);}
            Ui.setText(row.title,task.title.isEmpty()?"JM"+task.id:task.title);
            Ui.setText(row.state,Store.status(task.status)+(task.status.equals("done")?"":" · "+task.done+"/"+task.total));Ui.setText(row.percent,String.format(Locale.ROOT,"%.0f%%",DownloadDisplay.percent(task.done,task.total,task.status)));
            row.state.setTextColor(task.status.equals("failed")?Color.rgb(180,35,54):task.status.equals("done")?ACCENT:MUTED);
            row.progress.setIndeterminate(task.status.equals("running")&&task.total==0);row.progress.setProgress((int)(DownloadDisplay.percent(task.done,task.total,task.status)*10));
            Ui.setText(row.phase,DownloadDisplay.size(task.status.equals("done")?task.resultBytes:task.imageBytes)+" / "+(task.status.equals("done")?DownloadDisplay.size(task.resultBytes):task.done>0&&task.total>0?DownloadDisplay.size(task.imageBytes*(double)task.total/task.done):"—")+(task.status.equals("running")||task.status.equals("resetting")?" · "+DownloadDisplay.speed(task.speed):""));row.open.setVisibility(View.GONE);row.chosen.bind(selecting,selected.contains(task.key));String old=previousStates.put(task.key,task.status);if(old!=null&&!old.equals("done")&&task.status.equals("done")){Ui.notice(this,"下载完成");refreshPreview();}
            downloadCovers.bind(task,row.cover);
        }
        Iterator<Map.Entry<String,Row>> iterator=rows.entrySet().iterator();while(iterator.hasNext()){Map.Entry<String,Row> entry=iterator.next();if(!visible.contains(entry.getKey())){entry.getValue().cover.remove();queue.removeView(entry.getValue().card);iterator.remove();}}
        Ui.setText(summary,"共 "+tasks.size()+" 本  ·  完成 "+completed+"  ·  失败 "+failed);
        Ui.setText(global,active==0?(store.running?"正在启动…":store.note.isEmpty()?(completed>0&&completed==tasks.size()?"下载完成":"暂无正在下载的任务"):store.note):"同时下载 "+active+" 本 · 总实时速度 "+DownloadDisplay.speed(speed));
        if(!store.galleryNotice.isEmpty())global.append("\n"+store.galleryNotice);
        if(!store.cleanupNotice.isEmpty())global.append("\n最近清理："+store.cleanupNotice);
        start.setEnabled(true);Ui.setText(start,store.running?"Ⅱ  暂停全部":"▶  开始全部");pause.setEnabled(store.running);selected.retainAll(visible);Ui.setText(selectedCount,"已选中"+selected.size()+"项");more.setVisibility(tasks.size()>limit?View.VISIBLE:View.GONE);
        if(pageExchange==null)pageSwitch.invalidate();
        showChapterSelection();
    }

    private void showChapterSelection(){
        if(isFinishing()||isDestroyed())return;
        if(chapterDialog!=null){
            if(!chapterTask.status.equals("selecting")){chapterDialog.dismiss();chapterDialog=null;}
            else return;
        }
        // A worker must leave its cache before this task can be rescheduled.
        if(store.running&&store.activeKeys.isEmpty())return;
        Store.Task next=null;
        for(Store.Task task:store.snapshot())if(task.status.equals("selecting")&&!store.activeKeys.contains(task.key)){next=task;break;}
        if(next==null)return;
        final Store.Task task=next;chapterTask=task;
        final List<ChapterRules.Chapter> options=task.chapterOptions;
        String[] labels=new String[options.size()];boolean[] checked=new boolean[options.size()];Arrays.fill(checked,true);
        for(int i=0;i<labels.length;i++)labels[i]="第 "+options.get(i).number+" 章 · "+options.get(i).title;
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("JM"+task.id+" · 选择下载章节")
            .setMultiChoiceItems(labels,checked,(d,index,value)->checked[index]=value)
            .setPositiveButton("下载所选章节",null).setNeutralButton("取消全选",null)
            .setNegativeButton("稍后选择",(d,w)->postponeChapter(task)).create();
        chapterDialog=dialog;
        dialog.setOnCancelListener(d->postponeChapter(task));
        dialog.setOnDismissListener(d->{if(chapterDialog==dialog){chapterDialog=null;chapterTask=null;}});
        dialog.setOnShowListener(d->{
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->{
                boolean all=true;for(boolean value:checked)all&=value;
                Arrays.fill(checked,!all);for(int i=0;i<checked.length;i++)dialog.getListView().setItemChecked(i,!all);
                dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setText(all?"全选":"取消全选");
            });
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
                try{
                    synchronized(store){
                        if(!task.status.equals("selecting")||store.activeKeys.contains(task.key))throw new IOException("任务状态已变化，请稍后再试");
                        Set<String> ids=new HashSet<>();for(int i=0;i<checked.length;i++)if(checked[i])ids.add(options.get(i).id);
                        List<ChapterRules.Chapter> chosen=ChapterRules.select(options,ids);
                        task.selectedChapters=chosen;task.status="queued";task.phase="等待下载所选章节";store.save();
                    }
                    dialog.dismiss();if(!store.running)startForegroundService(new Intent(this,DownloadService.class).setAction(DownloadService.SELECTED));
                }catch(Exception error){toast(error.getMessage());}
            });
        });dialog.show();
    }
    private void postponeChapter(Store.Task task){
        if(task.status.equals("selecting")){task.status="paused";task.phase="已暂停，点击“开始下载”继续选择章节";save();}
    }

    private final class Row{
        LinearLayout card,heading,description;FrameLayout frame;TextView title,state,percent,phase;TaskSelectionBox chosen;ProgressBar progress;Button open;DownloadCovers.Target cover;
        Row(Store.Task task){
            card=column();card.setPadding(0,dp(12),0,dp(12));LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2);card.setLayoutParams(params);
            heading=horizontal();card.addView(heading);
            frame=new FrameLayout(MainActivity.this);frame.setBackgroundColor(Color.rgb(232,237,241));
            LinearLayout.LayoutParams coverParams=new LinearLayout.LayoutParams(dp(66),dp(86));coverParams.rightMargin=dp(12);heading.addView(frame,coverParams);
            ImageView image=new ImageView(MainActivity.this);image.setScaleType(ImageView.ScaleType.CENTER_CROP);frame.addView(image,new FrameLayout.LayoutParams(-1,-1));
            TextView placeholder=text("暂无\n封面",11,MUTED);placeholder.setGravity(Gravity.CENTER);frame.addView(placeholder,new FrameLayout.LayoutParams(-1,-1));cover=new DownloadCovers.Target(image,placeholder);
            description=column();heading.addView(description,new LinearLayout.LayoutParams(0,-2,1));
            title=text("",15,INK);title.setTypeface(null,Typeface.BOLD);title.setMaxLines(2);description.addView(title,new LinearLayout.LayoutParams(-1,-2));
            chosen=new TaskSelectionBox(MainActivity.this);chosen.setContentDescription("选择任务 "+task.id);chosen.setOnClickListener(v->selectTask(task));LinearLayout.LayoutParams selectionParams=new LinearLayout.LayoutParams(dp(48),dp(48));selectionParams.leftMargin=dp(8);heading.addView(chosen,selectionParams);
            state=text("",12,MUTED);state.setPadding(0,dp(5),0,dp(6));LinearLayout stateRow=horizontal();stateRow.addView(state,new LinearLayout.LayoutParams(0,-2,1));percent=text("",12,MUTED);stateRow.addView(percent);description.addView(stateRow);
            progress=new ProgressBar(MainActivity.this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(1000);progress.setProgressTintList(android.content.res.ColorStateList.valueOf(ACCENT));description.addView(progress,new LinearLayout.LayoutParams(-1,dp(6)));
            phase=text("",12,MUTED);phase.setPadding(0,dp(7),0,0);description.addView(phase);
            View separator=new View(MainActivity.this);separator.setBackgroundColor(Ui.LINE);LinearLayout.LayoutParams line=new LinearLayout.LayoutParams(-1,dp(1));line.topMargin=dp(20);card.addView(separator,line);open=button("阅读",v->open(task,false));card.setOnClickListener(v->clickTask(task));card.setOnLongClickListener(v->{selectTask(task);return true;});
        }
    }

    private void retry(Store.Task task){
        if(task.discardRequested){send(DownloadService.CANCEL,task.key);return;}
        if(store.activeKeys.contains(task.key)){toast("任务正在停止，请稍后重试。");return;}
        if(!Arrays.asList("failed","paused","cancelled").contains(task.status)){toast("仅失败、暂停或取消的任务可重试");return;}
        String outputUri=task.settings.outputUri,outputLabel=task.settings.outputLabel,format=task.settings.format;
        task.settings=new Store.Settings(store.settings.json());task.settings.outputUri=outputUri;task.settings.outputLabel=outputLabel;task.settings.format=format;
        task.status="queued";task.resets=0;task.error="";task.phase="等待重试";save();if(!store.running)startQueue();
    }
    private void details(Store.Task task){
        String message="JM"+task.id+" · "+task.title+"\n\n"+Store.status(task.status)+"："+task.phase+"\n图片 "+task.done+"/"+task.total+"，复用 "+task.cached+" 张\n图片线程 "+task.settings.threads+"，自动重连 "+task.resets+"/"+task.settings.maxResets+"\n耗时 "+String.format(Locale.ROOT,"%.1f",task.elapsed/1000.0)+" 秒\n保存位置："+task.settings.outputLabel;
        if(!task.error.isEmpty())message+="\n\n错误原因：\n"+task.error;
        TextView content=text(message,14,INK);content.setPadding(dp(20),dp(10),dp(20),dp(10));content.setTextIsSelectable(true);ScrollView scroll=new ScrollView(this);LinearLayout details=column();details.addView(content);details.addView(button("打开保存目录",v->new SavedDirectory(this,task.settings.outputUri,task.settings.outputLabel).openExternal()));scroll.addView(details);
        AlertDialog.Builder builder=new AlertDialog.Builder(this).setTitle("任务详情").setView(scroll).setNegativeButton("关闭",null);
        if(task.status.equals("failed"))details.addView(button("权限与联网检测",v->PermissionActivity.open(this,task)));
        if(task.status.equals("done"))builder.setPositiveButton("导出漫画",(d,w)->new ExportScreen(this,store,albumEntry(task)).show());
        else builder.setPositiveButton(task.discardRequested?"重试清理":"取消并删除文件",(d,w)->{send(DownloadService.CANCEL,task.key);});
        if(!task.status.equals("running")&&!task.status.equals("resetting"))builder.setNeutralButton("清理下载缓存",(d,w)->CleanupScreen.show(this,store,task));
        builder.show();
    }
    private LibraryStore.Entry albumEntry(Store.Task task){return new LibraryStore.Entry(task.id,task.title,task.resultUri,task.settings.outputUri,task.settings.outputLabel,task.settings.format,false);}
    private void open(Store.Task task,boolean share){
        if(!share){if(!task.resultUri.isEmpty())ReaderActivity.open(this,albumEntry(task));return;}
        if(task.settings.format.equals("images")){if(!task.resultUri.isEmpty())ReaderActivity.open(this,albumEntry(task));return;}
        if(task.resultUri.isEmpty())return;Uri uri=Uri.parse(task.resultUri);String mime=task.settings.format.equals("pdf")?"application/pdf":"application/zip";
        Intent intent=new Intent(share?Intent.ACTION_SEND:Intent.ACTION_VIEW).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        if(share){intent.setType(mime);intent.putExtra(Intent.EXTRA_STREAM,uri);intent.setClipData(ClipData.newRawUri("文件",uri));}else intent.setDataAndType(uri,mime);
        try{startActivity(Intent.createChooser(intent,share?"分享导出文件":"打开导出文件"));}catch(Exception error){showError("没有可打开此文件的应用，或文件已被移动/删除。可在保存目录中查看。");}
    }

    private void chooseDirectory(){
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION|Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        try{startActivityForResult(intent,1);}catch(Exception error){showError("系统文件选择器不可用，可使用应用下载目录");}
    }
    protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);if(ExportScreen.onResult(request,result,data))return;if(request!=1||result!=RESULT_OK||data==null||data.getData()==null)return;
        try{
            Uri uri=data.getData();int flags=data.getFlags()&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            // Choosing our read-only system-browser root means the app's normal export folder.
            if((getPackageName()+".documents").equals(uri.getAuthority())){
                store.settings.outputUri="";store.settings.outputLabel="应用下载目录";save();output.setText(OutputDirectory.display(this,store.settings.outputUri));return;
            }
            if((flags&Intent.FLAG_GRANT_WRITE_URI_PERMISSION)==0)throw new IOException("所选目录没有写入权限");
            getContentResolver().takePersistableUriPermission(uri,flags);
            String label=DocumentsContract.getTreeDocumentId(uri);Uri doc=DocumentsContract.buildDocumentUriUsingTree(uri,DocumentsContract.getTreeDocumentId(uri));
            try(Cursor cursor=getContentResolver().query(doc,new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())label=cursor.getString(0)+"（"+label+"）";}
            store.settings.outputUri=uri.toString();store.settings.outputLabel=label;save();output.setText(OutputDirectory.display(this,store.settings.outputUri));
            GalleryPrivacy.start(this,store);
        }catch(Exception error){showError("无法保留目录授权："+error.getMessage());}
    }

    private void settings(){
        if(settingsPage!=null||pageExchange!=null||settingsAnimation!=null)return;
        inputFocus.finishEditing();settingsScreen=new SettingsScreen(this,store,updates,this::chooseDirectory,()->output,()->save());
        settingsPage=settingsScreen.build(this::closeSettings);settingsPage.setTranslationX(inputFocus.getWidth());inputFocus.addView(settingsPage,new FrameLayout.LayoutParams(-1,-1));slideSettings(true);
    }
    private void closeSettings(){
        if(settingsPage==null||settingsAnimation!=null)return;
        inputFocus.finishEditing();settingsScreen.save();slideSettings(false);
    }
    private void slideSettings(boolean entering){
        final View page=settingsPage;
        shell.setTranslationX(entering?0:-inputFocus.getWidth());shell.setVisibility(View.VISIBLE);
        inputFocus.setDescendantFocusability(ViewGroup.FOCUS_BLOCK_DESCENDANTS);inputFocus.requestFocus();
        shell.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);page.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        android.animation.ValueAnimator animation=android.animation.ValueAnimator.ofFloat(0,1);settingsAnimation=animation;
        animation.setDuration(300);animation.setInterpolator(t->t*t*(3-2*t));
        animation.addUpdateListener(value->{float eased=(Float)value.getAnimatedValue(),progress=entering?eased:1-eased;int width=inputFocus.getWidth();shell.setTranslationX(-progress*width);page.setTranslationX((1-progress)*width);});
        animation.addListener(new android.animation.AnimatorListenerAdapter(){@Override public void onAnimationEnd(android.animation.Animator value){
            if(settingsAnimation!=animation)return;settingsAnimation=null;
            shell.setTranslationX(0);page.setTranslationX(0);inputFocus.setDescendantFocusability(ViewGroup.FOCUS_BEFORE_DESCENDANTS);
            if(entering){shell.setVisibility(View.GONE);page.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_AUTO);}
            else{inputFocus.removeView(page);settingsPage=null;settingsScreen=null;shell.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_AUTO);}
            inputFocus.requestFocus();
        }});animation.start();
    }

    private void selfTest(){
        if(store.running){toast("请先暂停下载，再运行离线诊断。");return;}
        toast("正在运行离线诊断，无需联网…");new Thread(()->{String result;try{result=Diagnostics.run(this);}catch(Throwable error){result="诊断未完成："+Core.error(error,"");}String message=result;runOnUiThread(()->new AlertDialog.Builder(this).setTitle("离线诊断结果").setMessage(message).setPositiveButton("确定",null).show());},"offline-check").start();
    }
    protected void onResume(){super.onResume();if(output!=null&&store!=null)output.setText(store.settings.outputLabel);if(inputFocus!=null)inputFocus.prepareForResume();if(libraryScreen!=null)libraryScreen.resume();handler.removeCallbacks(refresh);handler.post(refresh);}
    protected void onPause(){finishPageExchange();if(settingsAnimation!=null)settingsAnimation.end();if(inputFocus!=null)inputFocus.finishEditing();handler.removeCallbacks(refresh);if(chapterDialog!=null){chapterDialog.dismiss();chapterDialog=null;}save();super.onPause();}
    protected void onDestroy(){if(libraryScreen!=null)libraryScreen.close();if(downloadCovers!=null)downloadCovers.close();for(Row row:rows.values())row.cover.remove();super.onDestroy();}
    private void save(){try{store.save();}catch(Exception error){store.note=error.getMessage();toast(store.note);}}
    private void showError(String message){new AlertDialog.Builder(this).setTitle("无法完成操作").setMessage(message).setPositiveButton("确定",null).show();}
    private void toast(String message){Toast.makeText(this,message,Toast.LENGTH_LONG).show();}
    private int dp(int value){return (int)(getResources().getDisplayMetrics().density*value+.5f);}
    private LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;}
    private LinearLayout horizontal(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.HORIZONTAL);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    private LinearLayout card(){LinearLayout v=column();v.setPadding(dp(14),dp(14),dp(14),dp(14));GradientDrawable shape=new GradientDrawable();shape.setColor(Color.WHITE);shape.setCornerRadius(dp(14));v.setBackground(shape);return v;}
    private TextView text(String value,int size,int color){TextView v=new TextView(this);v.setText(value);v.setTextSize(size);v.setTextColor(color);v.setLineSpacing(dp(2),1);return v;}
    private EditText editLegacy(String hint,boolean number){EditText v=new EditText(this);v.setTextSize(15);v.setTextColor(INK);v.setHintTextColor(MUTED);v.setHint(hint);v.setSingleLine(number);if(number)v.setInputType(InputType.TYPE_CLASS_NUMBER);v.setSelectAllOnFocus(false);return v;}
    private EditText edit(String hint,boolean number){return Ui.input(this,hint,number);}
    private Button button(String label,View.OnClickListener click){Button v=new ActionButton(this);v.setText(label);v.setTextSize(15);v.setTextColor(INK);v.setOnClickListener(click);return v;}
    private Button buttonAccent(String label,View.OnClickListener click){Button v=button(label,click);Ui.primary(v);return v;}
    private void add(View view,int top,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(top);p.bottomMargin=dp(bottom);layout.addView(view,p);}
}
