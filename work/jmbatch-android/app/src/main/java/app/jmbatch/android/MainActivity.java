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
    private final int BG=Color.rgb(243,245,248),INK=Color.rgb(23,44,62),MUTED=Color.rgb(97,115,135),ACCENT=Color.rgb(8,127,140);
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
    private AlertDialog chapterDialog;
    private Store.Task chapterTask;
    private final Runnable refresh=new Runnable(){public void run(){render();handler.postDelayed(this,700);}};

    public void onCreate(Bundle state){
        super.onCreate(state);store=Store.get(this);downloadCovers=new DownloadCovers(this);
        for(Store.Task task:store.snapshot())if(task.discardRequested&&task.status.equals("cancelling"))send(DownloadService.CANCEL,task.key);
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(BG);
        scroll.setOnScrollChangeListener((view,x,y,oldX,oldY)->refreshDownloadCovers());
        layout=column();layout.setPadding(dp(18),dp(20),dp(18),dp(28));scroll.addView(layout);
        inputFocus=new InputFocusLayout(this);inputFocus.addView(scroll);setContentView(inputFocus);inputFocus.requestFocus();
        LinearLayout header=horizontal();TextView brand=text("JM Batch",27,INK);brand.setTypeface(null,Typeface.BOLD);header.addView(brand,new LinearLayout.LayoutParams(0,-2,1));header.addView(button("下载设置",v->settings()));layout.addView(header);
        add(text("Android  ·  "+Core.VERSION,12,MUTED),0,4);
        Button updateButton=button("软件更新",v->{});add(updateButton,0,10);updates=new GithubUpdates(this,updateButton);handler.postDelayed(()->updates.startup(),1500);
        add(button("漫画库",v->showLibrary()),0,6);
        add(button("清理下载缓存",v->CleanupScreen.show(this,store,null)),0,6);
        add(button("权限与联网检测",v->PermissionActivity.open(this)),0,6);

        LinearLayout target=card();target.addView(text("保存位置",13,MUTED));
        output=text(store.settings.outputLabel,14,INK);output.setPadding(0,dp(8),0,dp(6));target.addView(output);
        target.addView(new ActionRow(this,button("选择目录",v->chooseDirectory()),button("使用应用目录",v->{store.settings.outputUri="";store.settings.outputLabel="应用下载目录";save();output.setText(store.settings.outputLabel);})));
        target.addView(button("打开保存目录",v->new SavedDirectory(this,store.settings.outputUri,store.settings.outputLabel).openExternal()));
        RadioGroup formats=new RadioGroup(this);formats.setOrientation(RadioGroup.HORIZONTAL);
        String[] labels={"PDF","ZIP","文件夹"},values={"pdf","zip","images"};
        for(int index=0;index<values.length;index++){
            RadioButton choice=new RadioButton(this);choice.setId(View.generateViewId());choice.setText(labels[index]);choice.setTag(values[index]);formats.addView(choice);
            if(values[index].equals(store.settings.format))formats.check(choice.getId());
        }
        formats.setOnCheckedChangeListener((group,id)->{store.settings.format=(String)group.findViewById(id).getTag();save();});target.addView(formats);
        target.addView(button("导出漫画",v->showLibrary()));add(target,0,12);

        LinearLayout input=card();TextView title=text("添加下载编号",17,INK);title.setTypeface(null,Typeface.BOLD);input.addView(title);
        ids=edit("示例：123456, 123460-123465\n支持空格、换行、逗号及 JM 前缀",false);ids.setMinLines(2);ids.setMaxLines(5);ids.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);input.addView(ids);
        input.addView(buttonAccent("加入队列",v->{if(addIds(ids.getText().toString())){ids.setText("");inputFocus.finishEditing();}}));
        LinearLayout range=horizontal();rangeFirst=edit("起始编号",true);rangeLast=edit("结束编号",true);range.addView(rangeFirst,new LinearLayout.LayoutParams(0,-2,1));TextView to=text(" 至 ",14,MUTED);to.setGravity(Gravity.CENTER);range.addView(to);range.addView(rangeLast,new LinearLayout.LayoutParams(0,-2,1));input.addView(range);
        input.addView(button("添加连续编号",v->{if(addIds(rangeFirst.getText().toString().trim()+"-"+rangeLast.getText().toString().trim())){rangeFirst.setText("");rangeLast.setText("");inputFocus.finishEditing();}}));
        input.addView(text("每次最多添加 2000 个编号，自动跳过重复任务。\n新任务使用当前保存位置和格式，下载后可在漫画库转换格式。",11,MUTED));add(input,0,12);

        start=buttonAccent("开始下载",v->startQueue());pause=button("暂停全部",v->send(DownloadService.PAUSE,null));add(new ActionRow(this,start,pause),0,8);
        summary=text("",13,MUTED);add(summary,0,4);global=text("",12,ACCENT);add(global,0,10);
        queue=column();layout.addView(queue);more=button("显示更多任务",v->{limit+=50;render();});layout.addView(more);
        layout.addView(button("清除已结束任务记录",v->new AlertDialog.Builder(this).setTitle("清除已结束任务记录").setMessage("仅移除已完成和已取消的任务记录，保留已保存文件及缓存。移除后无法通过这些记录继续下载。").setNegativeButton("取消",null).setPositiveButton("移除",(d,w)->{clearHistory();}).show()));
        layout.addView(text("可在通知栏查看下载进度或暂停任务。应用被系统关闭后，重新打开即可继续下载。",11,MUTED));
        if(!store.note.isEmpty())toast(store.note);
        if(state!=null&&state.getBundle("library")!=null){libraryScreen=new LibraryScreen(this,store);libraryScreen.show(state.getBundle("library"));}
    }

    private void showLibrary(){if(libraryScreen==null||!libraryScreen.isOpen())libraryScreen=new LibraryScreen(this,store);libraryScreen.show();}
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
        if(queue==null)return;List<Store.Task> tasks=store.snapshot();int completed=0,failed=0,active=0;long speed=0;
        Set<String> visible=new HashSet<>();
        for(int i=0;i<tasks.size();i++){
            Store.Task task=tasks.get(i);if(task.status.equals("done"))completed++;if(task.status.equals("failed"))failed++;if(task.status.equals("running")||task.status.equals("resetting")){active++;speed+=task.speed;}
            if(i>=limit)continue;visible.add(task.key);Row row=rows.get(task.key);if(row==null){row=new Row(task);rows.put(task.key,row);queue.addView(row.card);}
            row.title.setText("JM"+task.id+" · "+task.title);
            row.state.setText(Store.status(task.status)+" · "+(task.settings.format.equals("images")?"图片":task.settings.format.toUpperCase(Locale.ROOT))+" · "+task.progressText()+" · 重连 "+task.resets);
            row.state.setTextColor(task.status.equals("failed")?Color.rgb(180,35,54):task.status.equals("done")?ACCENT:MUTED);
            row.progress.setIndeterminate(task.status.equals("running")&&task.total==0);row.progress.setProgress((int)(DownloadDisplay.percent(task.done,task.total,task.status)*10));
            row.phase.setText(task.phase+"\n"+task.sizeText()+(task.status.equals("running")||task.status.equals("resetting")?"\n"+DownloadDisplay.speed(task.speed)+" · "+task.etaText():""));row.open.setVisibility(task.resultUri.isEmpty()?View.GONE:View.VISIBLE);
            downloadCovers.bind(task,row.cover);
        }
        Iterator<Map.Entry<String,Row>> iterator=rows.entrySet().iterator();while(iterator.hasNext()){Map.Entry<String,Row> entry=iterator.next();if(!visible.contains(entry.getKey())){entry.getValue().cover.remove();queue.removeView(entry.getValue().card);iterator.remove();}}
        summary.setText("共 "+tasks.size()+" 本  ·  完成 "+completed+"  ·  失败 "+failed);
        global.setText(active==0?(store.running?"正在启动…":store.note.isEmpty()?(completed>0&&completed==tasks.size()?"下载完成":"暂无正在下载的任务"):store.note):"同时下载 "+active+" 本 · 总速度 "+DownloadDisplay.speed(speed));
        if(!store.cleanupNotice.isEmpty())global.append("\n最近清理："+store.cleanupNotice);
        start.setEnabled(!store.running);pause.setEnabled(store.running);more.setVisibility(tasks.size()>limit?View.VISIBLE:View.GONE);
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
        LinearLayout card,heading,description;FrameLayout frame;TextView title,state,phase;ProgressBar progress;Button open;DownloadCovers.Target cover;
        Row(Store.Task task){
            card=card();LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2);params.bottomMargin=dp(10);card.setLayoutParams(params);
            heading=horizontal();card.addView(heading);
            frame=new FrameLayout(MainActivity.this);frame.setBackgroundColor(Color.rgb(232,237,241));
            LinearLayout.LayoutParams coverParams=new LinearLayout.LayoutParams(dp(66),dp(88));coverParams.rightMargin=dp(12);heading.addView(frame,coverParams);
            ImageView image=new ImageView(MainActivity.this);image.setScaleType(ImageView.ScaleType.CENTER_CROP);frame.addView(image,new FrameLayout.LayoutParams(-1,-1));
            TextView placeholder=text("暂无\n封面",11,MUTED);placeholder.setGravity(Gravity.CENTER);frame.addView(placeholder,new FrameLayout.LayoutParams(-1,-1));cover=new DownloadCovers.Target(image,placeholder);
            description=column();heading.addView(description,new LinearLayout.LayoutParams(0,-2,1));
            title=text("",15,INK);title.setTypeface(null,Typeface.BOLD);title.setMaxLines(2);description.addView(title);state=text("",12,MUTED);state.setPadding(0,dp(7),0,dp(6));description.addView(state);
            progress=new ProgressBar(MainActivity.this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(1000);card.addView(progress,new LinearLayout.LayoutParams(-1,dp(8)));
            phase=text("",12,MUTED);phase.setPadding(0,dp(7),0,0);card.addView(phase);
            open=button("阅读",v->open(task,false));card.addView(new ActionRow(MainActivity.this,button("详情",v->details(task)),button("重试",v->retry(task)),open));
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
        }catch(Exception error){showError("无法保留目录授权："+error.getMessage());}
    }

    private void settings(){
        LinearLayout form=column();form.setPadding(dp(20),dp(12),dp(20),dp(18));ScrollView scroll=new ScrollView(this);scroll.addView(form);
        String[] names={"每任务图片线程数（1–16）","请求超时（秒，5–120）","请求重试次数（0–5）","慢速阈值（KB/s，0 表示仅检测无进度）","慢速检测时长（秒，15–600）","无进度超时（秒，30–1800）","每任务自动重连上限（0–10）","同时下载任务数（1–4，默认 2）","每任务章节并行数（1–8，默认 4）"};
        int[] values={store.settings.threads,store.settings.timeout,store.settings.retries,store.settings.slowKB,store.settings.window,store.settings.stall,store.settings.maxResets,store.settings.concurrentTasks,store.settings.chapterWorkers};
        EditText[] fields=new EditText[names.length];
        for(int i=0;i<names.length;i++){form.addView(text(names[i],13,MUTED));fields[i]=edit("",true);fields[i].setText(Integer.toString(values[i]));form.addView(fields[i]);}
        CheckBox auto=new CheckBox(this);auto.setText("下载缓慢或无进度时自动重连");auto.setChecked(store.settings.autoReset);form.addView(auto);
        CheckBox allChapters=new CheckBox(this);allChapters.setText("默认下载全部章节（跳过章节选择）");allChapters.setChecked(store.settings.downloadAllChapters);form.addView(allChapters);
        form.addView(text("Cookie（可选，仅本次会话有效）",13,MUTED));EditText cookie=edit("key=value; key2=value2",false);cookie.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);cookie.setText(store.cookie);form.addView(cookie);
        form.addView(text("并行数越高，请求和内存占用越多；超时或限流时可适当调低。\n下载速度按实际接收的图片数据统计，包含重试流量。\n任务数保存后生效；调低时等待当前任务完成。\n其他设置用于新任务和手动重试，已有任务保留原保存位置和格式。",12,MUTED));
        form.addView(button("离线诊断",v->selfTest()));
        form.addView(button("使用说明",v->new AlertDialog.Builder(this).setTitle("使用说明").setMessage("1. 选择保存位置和下载格式，添加编号或连续编号。\n2. 点击“开始下载”，可在通知栏查看进度或暂停。\n3. 下载后在任务详情或漫画库选择“导出漫画”，再选择 PDF、ZIP、命名方式与保存目录。\n4. 多章节 PDF 可统一导出或分章节导出，导出始终保留原始图片。\n5. 下载失败时保留完整缓存，可查看失败原因后点击“重试”。\n6. 应用目录在卸载后会被删除，重要图片请选公共目录或导出备份。\n7. 导出和文件管理前请暂停下载，系统目录授权失效时需重新选择目录。").setPositiveButton("确定",null).show()));
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("下载设置").setView(scroll).setNegativeButton("取消",null).setPositiveButton("保存",null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            try{
                int[] nums=new int[fields.length];for(int i=0;i<fields.length;i++)nums[i]=Integer.parseInt(fields[i].getText().toString().trim());
                Store.Settings options=new Store.Settings(store.settings.json());options.threads=nums[0];options.timeout=nums[1];options.retries=nums[2];options.slowKB=nums[3];options.window=nums[4];options.stall=nums[5];options.maxResets=nums[6];options.concurrentTasks=nums[7];options.chapterWorkers=nums[8];options.autoReset=auto.isChecked();options.keepImages=false;options.numericFilename=false;options.flatZip=false;options.validate();
                options.downloadAllChapters=allChapters.isChecked();
                String secret=cookie.getText().toString().trim();if(secret.contains("\n")||secret.contains("\r")||(!secret.isEmpty()&&!secret.contains("=")))throw new IllegalArgumentException("Cookie 格式应为 key=value; key2=value2，不能包含换行");
                store.settings=options;store.cookie=secret;store.save();toast("设置已保存");dialog.dismiss();
            }catch(Exception error){showError(error instanceof NumberFormatException?"请输入有效的整数，并确认数值在允许范围内。":error.getMessage());}
        }));dialog.show();
    }

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
    private EditText edit(String hint,boolean number){EditText v=new EditText(this);v.setTextSize(15);v.setTextColor(INK);v.setHintTextColor(MUTED);v.setHint(hint);v.setSingleLine(number);if(number)v.setInputType(InputType.TYPE_CLASS_NUMBER);v.setSelectAllOnFocus(false);return v;}
    private Button button(String label,View.OnClickListener click){Button v=new ActionButton(this);v.setText(label);v.setTextSize(13);v.setTextColor(ACCENT);v.setOnClickListener(click);return v;}
    private Button buttonAccent(String label,View.OnClickListener click){Button v=button(label,click);v.setTextColor(Color.WHITE);v.setBackgroundTintList(android.content.res.ColorStateList.valueOf(ACCENT));return v;}
    private void add(View view,int top,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(top);p.bottomMargin=dp(bottom);layout.addView(view,p);}
}
