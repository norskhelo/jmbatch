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
    private LinearLayout layout;
    private LinearLayout queue;
    private InputFocusLayout inputFocus;
    private LibraryScreen libraryScreen;
    private EditText ids,rangeFirst,rangeLast;
    private TextView output,summary,global;
    private Button start,pause,more;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Map<String,Row> rows=new LinkedHashMap<>();
    private int limit=50;
    private FrameLayout pages,downloadPage,libraryHost;
    private LinearLayout taskSheet,preview;
    private TextView selectedCount;
    private final Set<String> selected=new LinkedHashSet<>();
    private final Map<String,String> previousStates=new HashMap<>();
    private boolean selecting,libraryVisible;
    private AlertDialog addDialog;
    FrameLayout libraryHost(){return libraryHost;}
    void hideLibrary(){libraryVisible=false;if(libraryScreen!=null)libraryScreen.close();libraryHost.setVisibility(View.GONE);downloadPage.setVisibility(View.VISIBLE);downloadPage.setTranslationY(dp(80));downloadPage.animate().translationY(0).setDuration(240).start();refreshPreview();}
    @Override public void onBackPressed(){if(libraryVisible){if(libraryScreen==null||!libraryScreen.back())hideLibrary();return;}if(selecting){exitSelection();return;}super.onBackPressed();}

    private AlertDialog chapterDialog;
    private Store.Task chapterTask;
    private final Runnable refresh=new Runnable(){public void run(){render();handler.postDelayed(this,700);}};

    public void onCreate(Bundle state){
        super.onCreate(state);store=Store.get(this);downloadCovers=new DownloadCovers(this);
        for(Store.Task task:store.snapshot())if(task.discardRequested&&task.status.equals("cancelling"))send(DownloadService.CANCEL,task.key);
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        inputFocus=new InputFocusLayout(this);inputFocus.setBackgroundColor(BG);setContentView(inputFocus);
        LinearLayout shell=column();shell.setPadding(dp(16),dp(12),dp(16),dp(12));inputFocus.addView(shell,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout header=horizontal(),brandBox=column();TextView brand=text("JM Batch",26,INK);brand.setTypeface(null,Typeface.BOLD);brandBox.addView(brand);brandBox.addView(text("ver "+Core.VERSION,12,MUTED));header.addView(brandBox,new LinearLayout.LayoutParams(0,-2,1));header.addView(button("⚙ 设置",v->settings()));shell.addView(header);
        Button updateButton=button("检查更新",v->{});updates=new GithubUpdates(this,updateButton);handler.postDelayed(()->updates.startup(),1500);
        pages=new FrameLayout(this);LinearLayout.LayoutParams pageParams=new LinearLayout.LayoutParams(-1,0,1);pageParams.topMargin=dp(12);shell.addView(pages,pageParams);
        downloadPage=new FrameLayout(this);pages.addView(downloadPage,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout home=column();downloadPage.addView(home,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout libraryPreview=card();libraryPreview.addView(Ui.button(this,"漫画库  ↑",this::showLibrary));preview=horizontal();libraryPreview.addView(preview,new LinearLayout.LayoutParams(-1,dp(88)));home.addView(libraryPreview);
        View fade=new View(this);android.graphics.drawable.GradientDrawable gradient=new android.graphics.drawable.GradientDrawable(android.graphics.drawable.GradientDrawable.Orientation.TOP_BOTTOM,new int[]{Color.WHITE,BG});fade.setBackground(gradient);home.addView(fade,new LinearLayout.LayoutParams(-1,dp(18)));
        FrameLayout panel=new FrameLayout(this);panel.setBackground(Ui.shape(this,Color.WHITE,18,true));home.addView(panel,new LinearLayout.LayoutParams(-1,0,1));
        layout=column();layout.setPadding(dp(14),dp(10),dp(14),dp(12));panel.addView(layout,new FrameLayout.LayoutParams(-1,-1));layout.addView(Ui.heading(this,"下载页面"));
        start=buttonAccent("开始全部",v->{if(store.running)send(DownloadService.PAUSE,null);else startQueue();});pause=button("暂停全部",v->send(DownloadService.PAUSE,null));
        layout.addView(Ui.pair(this,start,button("清除下载记录",v->Ui.confirm(this,"是否删除任务记录",this::clearHistory))));
        summary=text("",12,MUTED);add(summary,8,3);global=text("",12,MUTED);add(global,0,6);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setOnScrollChangeListener((view,x,y,oldX,oldY)->refreshDownloadCovers());
        queue=column();queue.setPadding(0,0,0,dp(80));scroll.addView(queue);layout.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));more=button("显示更多任务",v->{limit+=50;render();});layout.addView(more);
        Button add=buttonAccent("＋",v->addDownload());add.setTextSize(28);add.setContentDescription("添加下载");add.setBackground(Ui.shape(this,ACCENT,32,false));add.setElevation(dp(5));FrameLayout.LayoutParams fab=new FrameLayout.LayoutParams(dp(58),dp(58),Gravity.BOTTOM|Gravity.RIGHT);fab.setMargins(0,0,dp(18),dp(18));panel.addView(add,fab);
        taskSheet=column();taskSheet.setPadding(dp(18),dp(20),dp(18),dp(24));taskSheet.setBackground(Ui.shape(this,Color.WHITE,18,true));taskSheet.setElevation(dp(10));selectedCount=text("",16,INK);selectedCount.setGravity(Gravity.CENTER);selectedCount.setTypeface(null,Typeface.BOLD);taskSheet.addView(selectedCount);Ui.gap(taskSheet,20);taskSheet.addView(Ui.pair(this,button("删除任务",v->removeSelected()),button("返回",v->exitSelection())));FrameLayout.LayoutParams sheetParams=new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM);panel.addView(taskSheet,sheetParams);taskSheet.setVisibility(View.GONE);
        libraryHost=new FrameLayout(this);libraryHost.setBackground(Ui.shape(this,Color.WHITE,18,true));pages.addView(libraryHost,new FrameLayout.LayoutParams(-1,-1));libraryHost.setVisibility(View.GONE);
        output=text(store.settings.outputLabel,14,INK);inputFocus.requestFocus();refreshPreview();
        if(!store.note.isEmpty())toast(store.note);
        GalleryPrivacy.start(this,store);
        if(state!=null&&state.getBundle("library")!=null){libraryVisible=true;downloadPage.setVisibility(View.GONE);libraryHost.setVisibility(View.VISIBLE);libraryScreen=new LibraryScreen(this,store);libraryScreen.show(state.getBundle("library"));}
    }

    private void showLibrary(){libraryVisible=true;downloadPage.setVisibility(View.GONE);libraryHost.setVisibility(View.VISIBLE);if(libraryScreen==null||!libraryScreen.isOpen())libraryScreen=new LibraryScreen(this,store);libraryScreen.show();libraryHost.setTranslationY(dp(120));libraryHost.animate().translationY(0).setDuration(260).start();}
    private void refreshPreview(){
        new Thread(()->{try{LibraryStore lib=LibraryStore.get(this);lib.sync(store.snapshot());List<LibraryStore.Entry> items=lib.list("",false);List<android.graphics.Bitmap> images=new ArrayList<>();for(int i=0;i<Math.min(4,items.size());i++)images.add(LibraryCover.load(getApplicationContext(),items.get(i)));
            runOnUiThread(()->{if(isDestroyed())return;preview.removeAllViews();if(images.isEmpty()){TextView empty=text("下载的漫画会显示在这里",13,MUTED);empty.setGravity(Gravity.CENTER);preview.addView(empty,new LinearLayout.LayoutParams(-1,-1));}for(android.graphics.Bitmap bitmap:images){ImageView image=new ImageView(this);image.setImageBitmap(bitmap);image.setScaleType(ImageView.ScaleType.CENTER_CROP);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-1,1);p.setMargins(dp(3),0,dp(3),0);preview.addView(image,p);}preview.setOnClickListener(v->showLibrary());});
        }catch(Exception ignored){}},"library-preview").start();
    }
    private void addDownload(){
        LinearLayout body=column();ids=edit("请输入数字编号，多个编号请用空格隔开",false);ids.setMinLines(3);ids.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);body.addView(ids);Ui.gap(body,14);
        RadioGroup formats=new RadioGroup(this);formats.setOrientation(RadioGroup.HORIZONTAL);String[] labels={"pdf","zip","文件夹"},values={"pdf","zip","images"};
        for(int i=0;i<values.length;i++){RadioButton b=new RadioButton(this);b.setId(View.generateViewId());b.setText(labels[i]);b.setTextColor(INK);b.setButtonTintList(android.content.res.ColorStateList.valueOf(ACCENT));b.setTag(values[i]);formats.addView(b,new RadioGroup.LayoutParams(0,-2,1));if(values[i].equals(store.settings.format))formats.check(b.getId());}body.addView(formats);Ui.gap(body,18);
        addDialog=Ui.modal(this,body,false);Button accept=buttonAccent("添加",v->{String format=(String)formats.findViewById(formats.getCheckedRadioButtonId()).getTag();store.settings.format=format;save();if(addIds(ids.getText().toString())){inputFocus.finishEditing();addDialog.dismiss();PermissionAccess.requestDownloadNotifications(this);startForegroundService(new Intent(this,DownloadService.class).setAction(DownloadService.SELECTED));}});body.addView(Ui.pair(this,accept,button("返回",v->addDialog.dismiss())));addDialog.show();
    }
    private void selectTask(Store.Task task){if(!selecting){selecting=true;Ui.sheet(taskSheet);}if(!selected.add(task.key))selected.remove(task.key);render();}
    private void exitSelection(){selecting=false;selected.clear();taskSheet.setVisibility(View.GONE);render();}
    private void removeSelected(){if(selected.isEmpty())return;Ui.confirm(this,"是否删除任务记录",()->{try{LibraryStore.get(this).sync(store.snapshot());synchronized(store){if(store.libraryBusy)throw new IOException("请等待文件操作完成");for(String key:selected)if(store.activeKeys.contains(key)||store.tasks.stream().anyMatch(t->t.key.equals(key)&&(t.discardRequested||t.status.equals("cancel_failed"))))throw new IOException("请先暂停选中的下载任务，等待停止后删除记录");store.tasks.removeIf(t->selected.contains(t.key));store.save();}exitSelection();refreshPreview();}catch(Exception e){showError(e.getMessage());}});}
    private void clickTask(Store.Task task){if(selecting){selectTask(task);return;}if(task.status.equals("running")||task.status.equals("resetting")){send(DownloadService.PAUSE_ONE,task.key);}else if(task.status.equals("failed")){retry(task);}else if(task.status.equals("done")){open(task,false);}else if(task.status.equals("paused")||task.status.equals("cancelled")){retry(task);}}
    private void taskMenu(Store.Task task,View anchor){PopupMenu menu=new PopupMenu(this,anchor);String[] labels={"任务信息","重试","阅读","分享","选择任务"};for(String label:labels)menu.getMenu().add(label);menu.setOnMenuItemClickListener(item->{switch(item.getTitle().toString()){case "任务信息":details(task);break;case "重试":retry(task);break;case "阅读":open(task,false);break;case "分享":open(task,true);break;default:selectTask(task);}return true;});menu.show();}
    @Override protected void onSaveInstanceState(Bundle state){
        super.onSaveInstanceState(state);if(libraryScreen!=null){Bundle library=libraryScreen.saveState();if(library!=null)state.putBundle("library",library);}
    }

    private void clearHistory(){
        try{
            LibraryStore.get(this).sync(store.snapshot());
            synchronized(store){
                if(store.libraryBusy)throw new IOException("正在管理漫画文件，请稍后再清理队列");
                Iterator<Store.Task> it=store.tasks.iterator();
                while(it.hasNext()){Store.Task t=it.next();if(!store.activeKeys.contains(t.key)&&(t.status.equals("done")||t.status.equals("cancelled")))it.remove();}
                store.save();
            }
            render();
        }catch(Exception error){showError("队列未清理完成："+error.getMessage());}
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
        if(libraryVisible){for(Store.Task task:store.snapshot()){String old=previousStates.put(task.key,task.status);if(old!=null&&!old.equals("done")&&task.status.equals("done"))Ui.notice(this,"下载完成");}showChapterSelection();return;}
        List<Store.Task> tasks=store.snapshot();int completed=0,failed=0,active=0;long speed=0;
        Set<String> visible=new HashSet<>();
        for(int i=0;i<tasks.size();i++){
            Store.Task task=tasks.get(i);if(task.status.equals("done"))completed++;if(task.status.equals("failed"))failed++;if(task.status.equals("running")||task.status.equals("resetting")){active++;speed+=task.speed;}
            if(i>=limit)continue;visible.add(task.key);Row row=rows.get(task.key);if(row==null){row=new Row(task);rows.put(task.key,row);queue.addView(row.card);}
            row.title.setText("JM"+task.id+" · "+task.title);
            row.state.setText(Store.status(task.status)+" · "+(task.settings.format.equals("images")?"图片":task.settings.format.toUpperCase(Locale.ROOT))+" · "+task.progressText()+" · 重连 "+task.resets);
            row.state.setTextColor(task.status.equals("failed")?Color.rgb(180,35,54):task.status.equals("done")?ACCENT:MUTED);
            row.progress.setIndeterminate(task.status.equals("running")&&task.total==0);row.progress.setProgress((int)(DownloadDisplay.percent(task.done,task.total,task.status)*10));
            row.phase.setText(task.phase+"\n"+task.sizeText()+(task.status.equals("running")||task.status.equals("resetting")?"\n"+DownloadDisplay.speed(task.speed)+" · "+task.etaText():""));row.open.setVisibility(View.GONE);row.chosen.setVisibility(selecting&&selected.contains(task.key)?View.VISIBLE:View.GONE);String old=previousStates.put(task.key,task.status);if(old!=null&&!old.equals("done")&&task.status.equals("done")){Ui.notice(this,"下载完成");refreshPreview();}
            downloadCovers.bind(task,row.cover);
        }
        Iterator<Map.Entry<String,Row>> iterator=rows.entrySet().iterator();while(iterator.hasNext()){Map.Entry<String,Row> entry=iterator.next();if(!visible.contains(entry.getKey())){entry.getValue().cover.remove();queue.removeView(entry.getValue().card);iterator.remove();}}
        summary.setText("共 "+tasks.size()+" 本  ·  完成 "+completed+"  ·  失败 "+failed);
        global.setText(active==0?(store.running?"正在启动…":store.note.isEmpty()?(completed>0&&completed==tasks.size()?"下载完成":"暂无正在下载的任务"):store.note):"同时下载 "+active+" 本 · 总实时速度 "+DownloadDisplay.speed(speed));
        if(!store.galleryNotice.isEmpty())global.append("\n"+store.galleryNotice);
        if(!store.cleanupNotice.isEmpty())global.append("\n最近清理："+store.cleanupNotice);
        start.setEnabled(true);start.setText(store.running?"暂停全部":"开始全部");pause.setEnabled(store.running);selected.retainAll(visible);selectedCount.setText("已选中"+selected.size()+"项");more.setVisibility(tasks.size()>limit?View.VISIBLE:View.GONE);
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
        LinearLayout card,heading,description;FrameLayout frame;TextView title,state,phase,chosen;ProgressBar progress;Button open;DownloadCovers.Target cover;
        Row(Store.Task task){
            card=card();LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2);params.bottomMargin=dp(10);card.setLayoutParams(params);
            heading=horizontal();card.addView(heading);
            frame=new FrameLayout(MainActivity.this);frame.setBackgroundColor(Color.rgb(232,237,241));
            LinearLayout.LayoutParams coverParams=new LinearLayout.LayoutParams(dp(66),dp(88));coverParams.rightMargin=dp(12);heading.addView(frame,coverParams);
            ImageView image=new ImageView(MainActivity.this);image.setScaleType(ImageView.ScaleType.CENTER_CROP);frame.addView(image,new FrameLayout.LayoutParams(-1,-1));
            TextView placeholder=text("暂无\n封面",11,MUTED);placeholder.setGravity(Gravity.CENTER);frame.addView(placeholder,new FrameLayout.LayoutParams(-1,-1));cover=new DownloadCovers.Target(image,placeholder);
            description=column();heading.addView(description,new LinearLayout.LayoutParams(0,-2,1));
            title=text("",15,INK);title.setTypeface(null,Typeface.BOLD);title.setMaxLines(2);LinearLayout titleRow=horizontal();titleRow.addView(title,new LinearLayout.LayoutParams(0,-2,1));Button dots=button("⋯",v->taskMenu(task,v));dots.setContentDescription("任务更多菜单");titleRow.addView(dots,new LinearLayout.LayoutParams(dp(44),dp(44)));description.addView(titleRow);chosen=text("✓",22,ACCENT);chosen.setContentDescription("已选中任务");heading.addView(chosen);chosen.setVisibility(View.GONE);state=text("",12,MUTED);state.setPadding(0,dp(7),0,dp(6));description.addView(state);
            progress=new ProgressBar(MainActivity.this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(1000);progress.setProgressTintList(android.content.res.ColorStateList.valueOf(ACCENT));description.addView(progress,new LinearLayout.LayoutParams(-1,dp(6)));
            phase=text("",12,MUTED);phase.setPadding(0,dp(7),0,0);description.addView(phase);
            open=button("阅读",v->open(task,false));card.setOnClickListener(v->clickTask(task));card.setOnLongClickListener(v->{selectTask(task);return true;});
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
                store.settings.outputUri="";store.settings.outputLabel="应用下载目录";save();output.setText(store.settings.outputLabel);return;
            }
            if((flags&Intent.FLAG_GRANT_WRITE_URI_PERMISSION)==0)throw new IOException("所选目录没有写入权限");
            getContentResolver().takePersistableUriPermission(uri,flags);
            String label=DocumentsContract.getTreeDocumentId(uri);Uri doc=DocumentsContract.buildDocumentUriUsingTree(uri,DocumentsContract.getTreeDocumentId(uri));
            try(Cursor cursor=getContentResolver().query(doc,new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())label=cursor.getString(0)+"（"+label+"）";}
            store.settings.outputUri=uri.toString();store.settings.outputLabel=label;save();output.setText(label);
            GalleryPrivacy.start(this,store);
        }catch(Exception error){showError("无法保留目录授权："+error.getMessage());}
    }

    private void settings(){new SettingsScreen(this,store,updates,this::chooseDirectory,()->output,()->save()).show();}

    private void selfTest(){
        if(store.running){toast("请先暂停下载，再运行离线诊断。");return;}
        toast("正在运行离线诊断，无需联网…");new Thread(()->{String result;try{result=Diagnostics.run(this);}catch(Throwable error){result="诊断未完成："+Core.error(error,"");}String message=result;runOnUiThread(()->new AlertDialog.Builder(this).setTitle("离线诊断结果").setMessage(message).setPositiveButton("确定",null).show());},"offline-check").start();
    }
    protected void onResume(){super.onResume();if(output!=null&&store!=null)output.setText(store.settings.outputLabel);if(inputFocus!=null)inputFocus.prepareForResume();if(libraryScreen!=null)libraryScreen.resume();handler.removeCallbacks(refresh);handler.post(refresh);}
    protected void onPause(){if(inputFocus!=null)inputFocus.finishEditing();handler.removeCallbacks(refresh);if(chapterDialog!=null){chapterDialog.dismiss();chapterDialog=null;}save();super.onPause();}
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
    private Button button(String label,View.OnClickListener click){Button v=new ActionButton(this);v.setText(label);v.setTextSize(13);v.setTextColor(INK);v.setOnClickListener(click);return v;}
    private Button buttonAccent(String label,View.OnClickListener click){Button v=button(label,click);Ui.primary(v);return v;}
    private void add(View view,int top,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(top);p.bottomMargin=dp(bottom);layout.addView(view,p);}
}
