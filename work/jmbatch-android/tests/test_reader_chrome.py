"""Production tap dispatch and animation geometry on deterministic host surfaces."""
import ast
from pathlib import Path
import subprocess
import sys

tests = Path(__file__).resolve().parent
source = tests.parent / 'app/src/main/java/app/jmbatch/android'
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)


def fixture(name):
    tree = ast.parse((tests/name).read_text(encoding='utf-8'))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'stubs' for t in n.targets))


stubs = fixture('test_action_layout.py')
pager = fixture('test_reader_pager.py')
for name, text in pager.items():
    if name.startswith('android/animation/') or name.startswith('android/view/animation/'):
        stubs[name] = text
view = stubs['android/view/View.java']
view = view.replace(' public View(Context c)', ''' public float alpha=1;public int dispatches;
 public void setAlpha(float f){alpha=f;}public void post(Runnable r){r.run();}
 public void setClickable(boolean v){}public boolean onTouchEvent(MotionEvent e){return true;}
 public boolean dispatchTouchEvent(MotionEvent e){dispatches++;return onTouchEvent(e);}
 public View(Context c)''')
stubs['android/view/View.java'] = view
stubs['android/view/ViewGroup.java'] = stubs['android/view/ViewGroup.java'].replace(
    'public void addView(View v)', 'public void setClipChildren(boolean v){}public void addView(View v)')
stubs['android/widget/FrameLayout.java'] = '''package android.widget;import android.view.*;import android.content.Context;
public class FrameLayout extends ViewGroup {public FrameLayout(Context c){super(c);}
protected LayoutParams generateDefaultLayoutParams(){return new LayoutParams(-1,-1);}
public boolean dispatchTouchEvent(MotionEvent e){return getChildCount()>0?getChildAt(0).dispatchTouchEvent(e):super.dispatchTouchEvent(e);}}'''
stubs['android/view/ViewConfiguration.java'] = '''package android.view;import android.content.Context;
public class ViewConfiguration {public static ViewConfiguration get(Context c){return new ViewConfiguration();}
public int getScaledTouchSlop(){return 8;}public static int getLongPressTimeout(){return 500;}}'''
stubs['android/view/MotionEvent.java'] = '''package android.view;public class MotionEvent {
public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,ACTION_POINTER_DOWN=5,ACTION_POINTER_UP=6;
int action;float x,y;long time;public MotionEvent(int a,float x,float y,long t){action=a;this.x=x;this.y=y;time=t;}
public int getActionMasked(){return action;}public float getRawX(){return x;}public float getRawY(){return y;}public long getEventTime(){return time;}}'''
stubs['ReaderChromeTest.java'] = '''import app.jmbatch.android.*;import android.content.Context;import android.view.*;
import android.animation.ValueAnimator;
public class ReaderChromeTest {
static int checks;static void check(boolean b,String s){checks++;if(!b)throw new AssertionError(s);}
static void send(ReaderViewport v,int action,float x,float y,long time){check(v.dispatchTouchEvent(new MotionEvent(action,x,y,time)),"event delivered");}
static int exact(int n){return View.MeasureSpec.makeMeasureSpec(n,View.MeasureSpec.EXACTLY);}
static void layout(ReaderChrome c,int w,int h){c.measure(exact(w),exact(h));c.layout(0,0,w,h);}
public static void main(String[] args){
Context context=new Context();ReaderViewport v=new ReaderViewport(context);int[] clicks={0};v.setOnClickListener(()->clicks[0]++);
send(v,0,20,20,0);send(v,1,20,20,100);check(clicks[0]==1,"blank area clicks exactly once");
View list=new View(context);v.addView(list);
for(int x:new int[]{20,200,380}){send(v,0,x,20,0);send(v,2,x+2,22,50);send(v,1,x+2,22,100);}
check(clicks[0]==4&&list.dispatches==9,"all zones toggle once; children retain events");
send(v,0,20,20,0);send(v,2,20,100,50);send(v,1,20,20,100);check(clicks[0]==4,"scroll back to origin is not tap");
send(v,0,20,20,0);send(v,2,100,20,50);send(v,1,20,20,100);check(clicks[0]==4,"swipe back to origin is not tap");
send(v,0,20,20,0);send(v,1,20,20,600);check(clicks[0]==4,"long press ignored");
send(v,0,20,20,0);send(v,5,20,20,50);send(v,1,20,20,100);check(clicks[0]==4,"multi pointer ignored");
send(v,0,20,20,0);send(v,3,20,20,50);send(v,1,20,20,100);check(clicks[0]==4,"cancel ignored");
v.performClick();check(clicks[0]==5,"accessibility click supported");
for(int[] size:new int[][]{{320,640},{640,320},{1080,1920},{240,240}}){
 View tc=new View(context),bc=new View(context);tc.setMinimumHeight(600);bc.setMinimumHeight(500);
 ControlScroll top=new ControlScroll(context,tc),bottom=new ControlScroll(context,bc);View page=new View(context);int[] done={0};
 ReaderChrome chrome=new ReaderChrome(context,top,bottom,page,()->done[0]++);int w=size[0],h=size[1];layout(chrome,w,h);
 int initial=page.getMeasuredHeight();check(initial>=h*.19f,"large fonts retain viewport");check(top.getBottom()==page.getTop()&&bottom.getTop()==page.getBottom(),"shown controls do not cover comic");
 chrome.toggle();ValueAnimator.half();layout(chrome,w,h);int middle=page.getMeasuredHeight();
 check(middle>initial&&middle<h&&top.alpha>0&&top.alpha<1,"intermediate expansion and fading");check(page.getMeasuredWidth()==w,"width stable during animation");
 chrome.toggle();ValueAnimator.finishAll();layout(chrome,w,h);
 check(chrome.controlsVisible()&&!chrome.animating()&&page.getMeasuredHeight()==initial,"rapid reverse restores layout");check(done[0]==1,"obsolete animation cannot settle");
 chrome.toggle();ValueAnimator.finishAll();layout(chrome,w,h);
 check(!chrome.controlsVisible()&&page.getTop()==0&&page.getBottom()==h,"hidden comic fills viewport");
 check(top.getVisibility()==View.INVISIBLE&&bottom.getVisibility()==View.INVISIBLE,"hidden controls cannot receive touches");
 ValueAnimator.enabled=false;chrome.show(true);layout(chrome,w,h);
 check(!chrome.animating()&&chrome.controlsVisible()&&page.getMeasuredHeight()==initial,"disabled system animations restore immediately");ValueAnimator.enabled=true;
 chrome.toggle();chrome.dispose();ValueAnimator.finishAll();check(done[0]==3,"close cancels completion");
}
System.out.println("ReaderChromeTest: "+checks+" checks passed");
}}
'''
paths = []
for name, text in stubs.items():
    path = out/name; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8'); paths.append(path)
jdk = Path(sys.argv[1])/'bin'
subprocess.run([str(jdk/'javac.exe'), '-encoding', 'UTF-8', '-d', str(out), *map(str, paths),
                *[str(source/name) for name in ('ReaderTap.java', 'ReaderViewport.java', 'ReaderChrome.java', 'ControlScroll.java')]], check=True)
subprocess.run([str(jdk/'java.exe'), '-cp', str(out), 'ReaderChromeTest'], check=True)
