package app.jmbatch.android;

import android.app.*;
import android.graphics.Color;
import android.view.*;
import android.widget.*;
import java.util.function.Supplier;

/** One continuous settings document with a scroll-linked table of contents. */
final class SettingsScreen {
    private final Activity a;private final Store store;private final GithubUpdates updates;private final Runnable choose,save;private final Supplier<TextView> output;
    SettingsScreen(Activity a,Store store,GithubUpdates updates,Runnable choose,Supplier<TextView> output,Runnable save){this.a=a;this.store=store;this.updates=updates;this.choose=choose;this.output=output;this.save=save;}
    void show(){
        Dialog dialog=new Dialog(a);dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout root=new LinearLayout(a);root.setBackgroundColor(Color.WHITE);LinearLayout nav=Ui.column(a),body=Ui.column(a);nav.setPadding(Ui.dp(a,12),Ui.dp(a,16),Ui.dp(a,8),0);nav.setBackgroundColor(Ui.BG);body.setPadding(Ui.dp(a,16),Ui.dp(a,12),Ui.dp(a,16),Ui.dp(a,24));
        root.addView(nav,new LinearLayout.LayoutParams(Ui.dp(a,100),-1));ScrollView scroll=new ScrollView(a);scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(0,-1,1));nav.addView(Ui.heading(a,"设置"));
        String[] titles={"下载","阅读","更新","软件说明"};TextView[] anchors=new TextView[4];Button[] links=new Button[4];
        for(int i=0;i<4;i++){final int index=i;links[i]=Ui.button(a,titles[i],()->scroll.smoothScrollTo(0,anchors[index].getTop()));nav.addView(links[i]);Ui.gap(nav,8);}
        anchors[0]=Ui.heading(a,"下载");body.addView(anchors[0]);
        EditText timeout=number(body,"任务超时时间（秒，5–120）",store.settings.timeout),concurrent=number(body,"同时下载任务数（1–4）",store.settings.concurrentTasks),limit=number(body,"下载限速（KB/s，0 为不限速）",store.settings.downloadLimitKB);
        CheckBox all=new CheckBox(a);all.setText("默认下载全部章节");all.setTextColor(Ui.INK);all.setChecked(store.settings.downloadAllChapters);body.addView(all);Ui.gap(body,12);
        body.addView(Ui.text(a,"保存目录",14));TextView path=output.get();if(path.getParent()!=null)((ViewGroup)path.getParent()).removeView(path);path.setTextColor(Ui.BLUE);body.addView(path);body.addView(Ui.button(a,"选择目录",choose));body.addView(Ui.button(a,"清除缓存",()->CleanupScreen.show(a,store,null)));Ui.gap(body,20);
        anchors[1]=Ui.heading(a,"阅读");body.addView(anchors[1]);body.addView(Ui.text(a,"阅读模式",14));RadioGroup modes=choices(body,new String[]{"左右翻页","上下翻页","上下滚动"},store.settings.readingMode.equals("paged")?0:store.settings.readingMode.equals("vertical")?1:2);final boolean[] modeChanged={false};modes.setOnCheckedChangeListener((g,id)->modeChanged[0]=true);
        body.addView(Ui.text(a,"多章节观看模式",14));RadioGroup chapters=choices(body,new String[]{"多章节合一","分章节观看"},store.settings.chapterViewMode-1);Ui.gap(body,20);
        anchors[2]=Ui.heading(a,"更新");body.addView(anchors[2]);body.addView(Ui.button(a,"检查更新",updates::manualCheck));body.addView(Ui.button(a,"更新日志",updates::showNotes));Ui.gap(body,20);
        anchors[3]=Ui.heading(a,"软件说明");body.addView(anchors[3]);body.addView(Ui.text(a,"本软件主要为作者自用，维护与开发均由 AI 进行",14));body.addView(Ui.text(a,"详情请见",14));TextView repo=Ui.text(a,"github.com/norskhelo/jmbatch",14);repo.setTextColor(Ui.BLUE);repo.setOnClickListener(v->a.startActivity(new android.content.Intent(android.content.Intent.ACTION_VIEW,android.net.Uri.parse("https://github.com/norskhelo/jmbatch"))));body.addView(repo);Ui.gap(body,20);
        LinearLayout advanced=Ui.column(a);advanced.setVisibility(View.GONE);body.addView(Ui.button(a,"高级下载设置",()->advanced.setVisibility(advanced.getVisibility()==View.GONE?View.VISIBLE:View.GONE)));body.addView(advanced);
        String[] names={"图片线程（1–16）","请求重试（0–5）","慢速阈值（KB/s）","慢速检测（秒）","无进度超时（秒）","自动重连上限","章节并行（1–8）"};int[] values={store.settings.threads,store.settings.retries,store.settings.slowKB,store.settings.window,store.settings.stall,store.settings.maxResets,store.settings.chapterWorkers};EditText[] fields=new EditText[values.length];for(int i=0;i<values.length;i++)fields[i]=number(advanced,names[i],values[i]);
        CheckBox auto=new CheckBox(a);auto.setText("缓慢或无进度时自动重连");auto.setChecked(store.settings.autoReset);advanced.addView(auto);EditText cookie=Ui.input(a,"Cookie（仅本次会话）",false);cookie.setInputType(129);cookie.setText(store.cookie);advanced.addView(cookie);
        Ui.gap(body,20);Button apply=Ui.button(a,"保存并返回",()->{try{Store.Settings options=new Store.Settings(store.settings.json());options.timeout=integer(timeout);options.concurrentTasks=integer(concurrent);options.downloadLimitKB=integer(limit);options.downloadAllChapters=all.isChecked();options.chapterViewMode=selected(chapters)+1;if(modeChanged[0])options.readingMode=new String[]{"paged","vertical","scroll"}[selected(modes)];options.threads=integer(fields[0]);options.retries=integer(fields[1]);options.slowKB=integer(fields[2]);options.window=integer(fields[3]);options.stall=integer(fields[4]);options.maxResets=integer(fields[5]);options.chapterWorkers=integer(fields[6]);options.autoReset=auto.isChecked();options.validate();String secret=cookie.getText().toString().trim();if(secret.contains("\n")||secret.contains("\r")||(!secret.isEmpty()&&!secret.contains("=")))throw new IllegalArgumentException("Cookie 格式应为 key=value");store.settings=options;store.cookie=secret;store.save();dialog.dismiss();Ui.notice(a,"设置已保存");}catch(Exception e){Ui.confirm(a,e instanceof NumberFormatException?"请输入有效整数":e.getMessage(),()->{});}});Ui.primary(apply);body.addView(apply);
        Runnable highlight=()->{int index=0;for(int i=0;i<4;i++)if(anchors[i].getTop()<=scroll.getScrollY()+Ui.dp(a,28))index=i;if(scroll.getChildAt(0).getHeight()>scroll.getHeight()+Ui.dp(a,8)&&scroll.getChildAt(0).getHeight()-scroll.getHeight()-scroll.getScrollY()<Ui.dp(a,8))index=3;for(int i=0;i<4;i++){links[i].setTextColor(i==index?Ui.BLUE:Ui.INK);links[i].setBackground(Ui.shape(a,i==index?0xffe5e7ec:Ui.BG,8,false));}};
        scroll.setOnScrollChangeListener((v,x,y,ox,oy)->highlight.run());dialog.setContentView(root);dialog.show();Ui.surface(a,dialog);dialog.getWindow().setBackgroundDrawableResource(android.R.color.transparent);dialog.getWindow().setLayout(-1,(int)(a.getResources().getDisplayMetrics().heightPixels*.92));scroll.post(highlight);
    }
    private EditText number(LinearLayout body,String label,int value){body.addView(Ui.text(a,label,13));EditText input=Ui.input(a,"",true);input.setText(Integer.toString(value));body.addView(input);Ui.gap(body,10);return input;}
    private int integer(EditText input){return Integer.parseInt(input.getText().toString().trim());}
    private RadioGroup choices(LinearLayout parent,String[] names,int chosen){RadioGroup group=new RadioGroup(a);for(int i=0;i<names.length;i++){RadioButton b=new RadioButton(a);b.setId(View.generateViewId());b.setText(names[i]);b.setTextSize(14);b.setTextColor(Ui.INK);group.addView(b);if(i==chosen)group.check(b.getId());}parent.addView(group);return group;}
    private int selected(RadioGroup group){return group.indexOfChild(group.findViewById(group.getCheckedRadioButtonId()));}
}
