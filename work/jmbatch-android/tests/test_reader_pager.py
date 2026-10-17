"""Exercise production pager/queue with deterministic Android surface stubs.
Checks gesture state and callback ordering; does not measure device frames.
"""
from pathlib import Path
import subprocess
import sys

source = Path(__file__).resolve().parents[1] / 'app/src/main/java/app/jmbatch/android'
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
stubs = {
'android/content/Context.java': 'package android.content; public class Context {}',
'android/graphics/Bitmap.java': 'package android.graphics; public class Bitmap { public int page; public Bitmap(int p){page=p;} }',
'android/view/View.java': '''package android.view;import android.content.Context;
public class View {public static final int VISIBLE=0,INVISIBLE=4;public float x;public int visibility;public int width=800;
public View(Context c){} public void setLayoutParams(Object p){}public void setTranslationX(float v){x=v;}public void setVisibility(int v){visibility=v;}
public int getWidth(){return width;}public void setClickable(boolean v){}public boolean performClick(){return true;}
public boolean onTouchEvent(MotionEvent e){return false;}protected void onSizeChanged(int w,int h,int ow,int oh){}public void post(Runnable r){r.run();}}''',
'android/widget/ImageView.java': '''package android.widget;import android.content.Context;import android.view.View;import android.graphics.Bitmap;
public class ImageView extends View {public Bitmap bitmap;public enum ScaleType{FIT_CENTER}public ImageView(Context c){super(c);}public void setScaleType(ScaleType s){}
public void setImageBitmap(Bitmap b){bitmap=b;}public void setImageDrawable(Object d){bitmap=null;}}''',
'android/widget/FrameLayout.java': '''package android.widget;import android.view.*;import android.content.Context;import java.util.*;
public class FrameLayout extends View {public List<View> children=new ArrayList<>();public FrameLayout(Context c){super(c);}public void addView(View v){children.add(v);}
public void setClipChildren(boolean v){}public static class LayoutParams{public LayoutParams(int w,int h){}}}''',
'android/view/ViewConfiguration.java': '''package android.view;import android.content.Context;
public class ViewConfiguration {public static ViewConfiguration get(Context c){return new ViewConfiguration();}public int getScaledTouchSlop(){return 8;}public int getScaledMinimumFlingVelocity(){return 50;}}''',
'android/view/MotionEvent.java': '''package android.view;public class MotionEvent {
public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,ACTION_POINTER_DOWN=5,ACTION_POINTER_UP=6;
int action;float x,y;public MotionEvent(int a,float x,float y){action=a;this.x=x;this.y=y;}public int getActionMasked(){return action;}
public int getPointerId(int i){return 0;}public int findPointerIndex(int p){return p==0?0:-1;}public float getX(){return x;}public float getY(){return y;}
public float getX(int i){return x;}public float getY(int i){return y;}}''',
'android/view/VelocityTracker.java': '''package android.view;public class VelocityTracker {
public static float speed;public static VelocityTracker obtain(){return new VelocityTracker();}public void addMovement(MotionEvent e){}
public void computeCurrentVelocity(int n){}public float getXVelocity(int p){return speed;}public void recycle(){}}''',
'android/view/animation/DecelerateInterpolator.java': 'package android.view.animation;public class DecelerateInterpolator {}',
'android/animation/Animator.java': '''package android.animation;import java.util.*;public class Animator {
protected List<AnimatorListenerAdapter> listeners=new ArrayList<>();public void removeAllListeners(){listeners.clear();}public void addListener(AnimatorListenerAdapter l){listeners.add(l);}}''',
'android/animation/AnimatorListenerAdapter.java': 'package android.animation;public class AnimatorListenerAdapter {public void onAnimationEnd(Animator a){}}',
'android/animation/ValueAnimator.java': '''package android.animation;import java.util.*;public class ValueAnimator extends Animator {
public interface Update{void value(ValueAnimator a);}static List<ValueAnimator> running=new ArrayList<>();public static boolean enabled=true;
float start,end,value;long duration;Update update;public static ValueAnimator ofFloat(float a,float b){ValueAnimator v=new ValueAnimator();v.start=a;v.end=b;return v;}
public static boolean areAnimatorsEnabled(){return enabled;}public void setDuration(long d){duration=d;}public void setInterpolator(Object o){}public void addUpdateListener(Update u){update=u;}
public Float getAnimatedValue(){return value;}public void start(){running.add(this);tick(0);if(duration==0)finish();}public void cancel(){running.remove(this);}
void tick(float f){value=start+(end-start)*f;update.value(this);}void finish(){running.remove(this);tick(1);for(AnimatorListenerAdapter l:new ArrayList<>(listeners))l.onAnimationEnd(this);}
public static void half(){for(ValueAnimator a:new ArrayList<>(running))a.tick(.5f);}public static void finishAll(){int guard=0;while(!running.isEmpty()){if(++guard>20)throw new AssertionError("animation loop");running.get(0).finish();}}}''',
'ReaderPagerTest.java': '''import app.jmbatch.android.*;import android.content.Context;import android.graphics.Bitmap;import android.view.*;import android.widget.*;import android.animation.ValueAnimator;import java.util.*;
public class ReaderPagerTest {
static int checks;static void check(boolean b,String s){if(!b)throw new AssertionError(s);checks++;}
static class Fixture implements ReaderPager.Listener {
Map<Integer,Bitmap> images=new HashMap<>();List<Integer> commits=new ArrayList<>();int requests;ReaderPager p;
Fixture(){images.put(0,new Bitmap(0));images.put(1,new Bitmap(1));p=new ReaderPager(new Context(),5,0,this);p.go(0);}
public Bitmap lookup(int i){return images.get(i);}public void committed(int i){commits.add(i);}public void requested(){requests++;}
void touch(int a,int x,int y){p.onTouchEvent(new MotionEvent(a,x,y));}
boolean has(int page){for(View v:p.children){ImageView image=(ImageView)v;if(image.bitmap!=null&&image.bitmap.page==page&&image.visibility==View.VISIBLE)return true;}return false;}
}
public static void main(String[] args){
Fixture f=new Fixture();check(f.p.displayed()==0,"first page");f.p.go(2);check(f.has(0)&&f.p.displayed()==0,"cold request keeps old picture and position");
f.p.go(3);f.images.put(2,new Bitmap(2));f.p.ready();check(f.p.displayed()==0,"stale result ignored");f.images.put(3,new Bitmap(3));f.p.ready();check(f.p.displayed()==0,"commit waits for animation");
ValueAnimator.half();check(f.p.children.get(0).x!=0,"native animation moves layer");ValueAnimator.finishAll();check(f.p.displayed()==3&&f.has(3),"latest target commits");check(!f.commits.contains(2),"obsolete target not persisted");f.p.dispose();
f=new Fixture();f.p.go(1);ValueAnimator.half();f.p.go(0);ValueAnimator.finishAll();check(f.p.displayed()==0&&f.has(0),"reverse cancels previous settle");
f.touch(0,600,300);f.touch(2,300,300);check(f.p.children.get(0).x==-300,"finger movement immediate");check(f.p.displayed()==0,"drag does not commit position");f.touch(1,300,300);ValueAnimator.finishAll();check(f.p.displayed()==1,"drag settles to neighbor");
f.touch(0,400,300);f.touch(2,430,300);f.touch(1,430,300);ValueAnimator.finishAll();check(f.p.displayed()==1,"short slow drag bounces");
f.touch(0,400,300);f.touch(2,100,300);f.touch(3,100,300);ValueAnimator.finishAll();check(f.p.displayed()==1&&f.has(1),"cancel bounces");
f.touch(0,400,300);f.touch(2,100,300);f.touch(5,100,300);ValueAnimator.finishAll();check(f.p.displayed()==1,"multitouch cancels");
f.touch(0,400,300);f.touch(2,410,600);f.touch(1,410,600);ValueAnimator.finishAll();check(f.p.displayed()==1,"vertical gesture ignored");
f.p.dispose();f=new Fixture();f.images.remove(1);f.touch(0,600,300);f.touch(2,50,300);check(Math.abs(f.p.children.get(0).x)<=96,"cold neighbor resists");
f.touch(1,50,300);ValueAnimator.finishAll();check(f.p.displayed()==0&&f.has(0),"cold swipe keeps current after bounce");f.images.put(1,new Bitmap(1));f.p.ready();ValueAnimator.finishAll();check(f.p.displayed()==1,"cold destination commits when ready");
f.p.dispose();f=new Fixture();f.p.go(-1);check(f.p.displayed()==0,"first boundary");ValueAnimator.enabled=false;f.p.go(1);check(f.p.displayed()==1,"system animations disabled");ValueAnimator.enabled=true;
for(int x:new int[]{20,400,780}){f.touch(0,x,300);f.touch(1,x,300);check(f.p.displayed()==1&&f.p.target()==1,"tap must not turn the page");}
f.p.go(0);f.p.dispose();ValueAnimator.finishAll();check(f.commits.size()==2,"destroy cancels callbacks");
ReaderRequests q=new ReaderRequests();ReaderRequests.Job a=new ReaderRequests.Job(1,0,800,1000),b=new ReaderRequests.Job(1,1,800,1000);
q.offer(a);check(q.take()==a,"take current");q.replace(Arrays.asList(b));q.replace(Arrays.asList(a,b,a));check(q.waiting()==1,"inflight dedup survives A B A");check(q.take()==null,"one active decoder");
q.complete(b);check(q.take()==null,"wrong completion cannot release active");q.complete(a);check(q.take()==b,"next scheduled");q.clear();check(q.take()==null,"clear keeps active reservation");q.complete(b);
for(int i=0;i<100;i++)q.offer(new ReaderRequests.Job(1,i,800,1000));check(q.waiting()==8,"bounded queue");
q.replace(Arrays.asList(new ReaderRequests.Job(2,0,600,800)));check(q.take().generation==2,"layout invalidation changes key");
System.out.println("ReaderPagerTest: "+checks+" checks passed");
}}
'''
}
paths=[]
for name, text in stubs.items():
    path=out/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding='utf-8'); paths.append(path)
jdk=Path(sys.argv[1])/'bin'
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-d',str(out),*[str(p) for p in paths],
                *[str(source/name) for name in ('ReaderRules.java','ReaderRequests.java','ReaderPager.java')]],check=True)
subprocess.run([str(jdk/'java.exe'),'-cp',str(out),'ReaderPagerTest'],check=True)
