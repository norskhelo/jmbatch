"""Exercise production CoverRow/CoverAdapter with stateful host widget doubles.

The drawable double tracks unfinished checked-state transitions, not rendered
frames. Device gesture timing and vendor checkbox appearance are not simulated.
An optional source path lets the same regression run against the pre-fix code.
"""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
source_path = Path(sys.argv[3]) if len(sys.argv) > 3 else root / 'app/src/main/java/app/jmbatch/android/LibraryScreen.java'
source = source_path.read_text(encoding='utf-8')
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)


def nested_class(name):
    start = source.index('    private final class ' + name + ' ')
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


program = r'''import java.util.*;
import java.util.concurrent.RejectedExecutionException;
public class LibraryRowsTest {
static class View {static final int VISIBLE=0,GONE=8;int visibility;void setVisibility(int v){visibility=v;}}
static class ViewGroup extends View {}
static class LinearLayout extends ViewGroup {
    static final int VERTICAL=1,HORIZONTAL=0;void setOrientation(int n){}
    LinearLayout(Activity a){}void setGravity(int v){}void setPadding(int a,int b,int c,int d){}
    void addView(View v,Object params){}static class LayoutParams {LayoutParams(int a,int b){}LayoutParams(int a,int b,int c){}}
}
static class FrameLayout extends LinearLayout {FrameLayout(Activity a){super(a);}void setBackgroundColor(int v){}}
static class Gravity {static final int CENTER_VERTICAL=1,CENTER=2;}
static class Color {static int rgb(int a,int b,int c){return 0;}}
static class TextUtils {static class TruncateAt {static final int END=1;}}
static class Bitmap {}
static class ImageView extends View {
    static class ScaleType {static final int FIT_CENTER=1;}Bitmap bitmap;
    ImageView(Activity a){}void setScaleType(int v){}void setImageBitmap(Bitmap b){bitmap=b;}
    void setContentDescription(String s){}
}
static class TextView extends View {
    String value="";TextView(Activity a){}void setText(String s){value=s;}void setTextSize(int n){}
    void setGravity(int n){}void setTextColor(int n){}void setMaxLines(int n){}void setMinLines(int n){}
    void setEllipsize(int n){}void setPadding(int a,int b,int c,int d){}
}
static class Drawable {
    boolean target,shown,running;
    void setState(boolean v){if(target!=v){target=v;running=true;}}
    void jump(){shown=target;running=false;}
}
static class CheckedTextView extends TextView {
    boolean checked;Drawable drawable;int replacements;
    CheckedTextView(Activity a){super(a);}boolean isChecked(){return checked;}
    void setChecked(boolean v){if(checked!=v){checked=v;if(drawable!=null)drawable.setState(v);}}
    Drawable getCheckMarkDrawable(){return drawable;}
    void setCheckMarkDrawable(Drawable d){
        replacements++;drawable=d;
        // CheckedTextView measures the checked drawable before applying its current state.
        if(d!=null){d.setState(true);d.setState(checked);}
    }
    void jumpDrawablesToCurrentState(){if(drawable!=null)drawable.jump();}
}
interface Checkable {boolean isChecked();void setChecked(boolean b);void toggle();}
static class android {static class R {static class attr {static final int listChoiceIndicatorMultiple=1;}}}
static class TypedArray {Drawable getDrawable(int n){return new Drawable();}void recycle(){}}
static class Activity {
    int drawableLoads;TypedArray obtainStyledAttributes(int[] ids){drawableLoads++;return new TypedArray();}
    Activity getApplicationContext(){return this;}
}
static class BaseAdapter {int changes;void notifyDataSetChanged(){changes++;}}
static class LibraryStore {static class Entry {
    String uri,format="zip",label="test";boolean favorite;Entry(String s){uri=s;}boolean isCollection(){return format.equals("collection");}
}}
static class LibraryCover {static Bitmap load(Activity a,LibraryStore.Entry e){return new Bitmap();}}
static class CollectionCover {static int calls;static Bitmap load(Activity a,List<LibraryStore.Entry> e){calls++;return new Bitmap();}}
static class Cover {final Bitmap bitmap;Cover(Bitmap b){bitmap=b;}}
static class Worker {
    List<Runnable> queue=new ArrayList<>();boolean isShutdown(){return false;}
    void execute(Runnable r){queue.add(r);}void complete(){queue.remove(0).run();}
}
static class Handler {void post(Runnable r){r.run();}}
final Activity activity=new Activity();boolean batchMode,tiles;int coverGeneration;
final Set<String> selected=new HashSet<>(),coverPending=new HashSet<>();
final Map<String,Cover> coverCache=new HashMap<>();final Worker coverWorker=new Worker();
final Map<String,List<LibraryStore.Entry>> collectionPreviews=new HashMap<>();
final Handler main=new Handler();final List<LibraryStore.Entry> entries=new ArrayList<>();
final BaseAdapter adapter=new CoverAdapter();int dp(int n){return n;}
String title(LibraryStore.Entry e){return e.uri;}boolean visible(){return true;}
''' + nested_class('CoverRow') + '\n' + nested_class('CoverAdapter') + r'''
static int checks;
static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
LibraryRowsTest(){
    for(String uri:Arrays.asList("a","b","c")){
        entries.add(new LibraryStore.Entry(uri));coverCache.put(uri,new Cover(new Bitmap()));
    }
}
CoverRow bind(int position,CoverRow row){return (CoverRow)((CoverAdapter)adapter).getView(position,row,null);}
static void settled(CoverRow row,boolean checked,String why){
    check(row.isChecked()==checked&&row.text.drawable!=null
        &&row.text.drawable.shown==checked&&!row.text.drawable.running,why);
}
public static void main(String[] args){
    LibraryRowsTest f=new LibraryRowsTest();
    CoverRow row=f.bind(0,null);
    check(row.text.drawable==null&&!row.isChecked(),"browsing has no check mark");
    f.batchMode=true;row=f.bind(0,row);
    settled(row,false,"entering batch must not replay a check/uncheck animation");
    Drawable original=row.text.drawable;int loads=f.activity.drawableLoads;
    for(int i=0;i<30;i++)row=f.bind(0,row);
    settled(row,false,"idle and cover refreshes keep unchecked row settled");
    check(row.text.drawable==original&&f.activity.drawableLoads==loads,"refresh reuses native check mark");
    f.selected.add("a");row=f.bind(0,row);
    settled(row,true,"initial selected binding is already checked");
    row=f.bind(1,row);settled(row,false,"recycled selected row becomes unchecked without animation");
    row=f.bind(0,row);settled(row,true,"recycled unchecked row becomes checked without animation");
    CoverRow other=f.bind(1,null);
    check(other.text.drawable!=row.text.drawable,"rows do not share mutable drawable state");
    Set<String> choices=new HashSet<>(f.selected);int replacements=row.text.replacements;
    boolean allSettled=true;
    for(int i=0;i<120;i++){
        int p=(i%6<3)?i%3:2-i%3;row=f.bind(p,row);
        allSettled&=row.isChecked()==choices.contains(f.entries.get(p).uri)
            &&!row.text.drawable.running&&row.text.drawable.shown==row.isChecked();
    }
    check(allSettled,"repeated forward/backward row recycling never animates choice changes");
    check(f.selected.equals(choices),"scroll and refresh never change chosen comics");
    check(row.text.replacements==replacements,"scroll never replaces the check mark");
    row=f.bind(1,row);row.setChecked(true);
    check(row.isChecked()&&row.text.drawable.running,"direct user selection retains the native transition");
    row.text.jumpDrawablesToCurrentState();row.toggle();
    check(!row.isChecked()&&row.text.drawable.running,"direct deselection still transitions");
    f.selected.add("b");row=f.bind(1,row);settled(row,true,"refresh shows latest selection immediately");
    f.coverCache.remove("b");row=f.bind(1,row);
    check(row.placeholder.visibility==View.VISIBLE&&f.coverPending.contains("b"),"cold cover queued independently of selection");
    choices=new HashSet<>(f.selected);int changes=f.adapter.changes;
    f.coverWorker.complete();
    check(f.adapter.changes==changes+1&&f.coverPending.isEmpty(),"real cover completion requests row refresh");
    row=f.bind(1,row);settled(row,true,"cover completion never replays the checkbox animation");
    check(row.image.bitmap!=null&&row.placeholder.visibility==View.GONE&&f.selected.equals(choices),"cover refresh preserves selection and updates image");
    f.selected.clear();row=f.bind(1,row);settled(row,false,"cleared choices render unchecked");
    for(LibraryStore.Entry entry:f.entries)f.selected.add(entry.uri);
    row=f.bind(2,row);settled(row,true,"select-all state renders checked");
    f.batchMode=false;row=f.bind(2,row);
    check(row.text.drawable==null&&!row.isChecked(),"exit batch removes check mark and recycled check state");
    f.selected.clear();f.batchMode=true;row=f.bind(2,row);
    settled(row,false,"reenter batch has no stale choice or transition");
    f.selected.add("b");CoverRow previous=row;f.tiles=true;row=f.bind(1,row);
    check(row!=previous&&row.tile,"switching to tiles replaces layout, not model");
    settled(row,true,"tile checked binding settled");
    check(row.image.bitmap!=null&&f.selected.contains("b"),"tile reuses cached cover and selection");
    previous=row;row=f.bind(2,row);check(row==previous,"same-mode tile recycling reused");
    settled(row,false,"recycled tile maps current comic selection");
    f.tiles=false;row=f.bind(1,row);check(!row.tile&&row!=previous,"switching back restores list row");
    settled(row,true,"switching back retains selection without animation");
    LibraryStore.Entry folder=new LibraryStore.Entry("collection:one");folder.format="collection";folder.label="2 本漫画";f.entries.add(folder);
    row=f.bind(3,row);check(row.text.drawable==null&&row.text.value.contains("收藏夹"),"folder card labelled and excluded from comic choices");
    f.coverWorker.complete();check(CollectionCover.calls==1,"folder preview uses folder loader");
    row=f.bind(3,row);check(row.image.bitmap!=null&&row.placeholder.visibility==View.GONE,"folder preview replaces placeholder");
    System.out.println("LibraryRowsTest: "+checks+" checks passed (production rows/adapter, host drawable states)");
}
}
'''
program_path = out / 'LibraryRowsTest.java'
program_path.write_text(program, encoding='utf-8')
jdk = Path(sys.argv[1]) / 'bin'
subprocess.run([str(jdk/'javac.exe'), '-encoding', 'UTF-8', '-d', str(out), str(program_path)], check=True)
subprocess.run([str(jdk/'java.exe'), '-cp', str(out), 'LibraryRowsTest'], check=True)
