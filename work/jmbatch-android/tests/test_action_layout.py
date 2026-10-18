"""Run production button measurement with synthetic font metrics, not device rendering."""
from pathlib import Path
import subprocess
import sys

source = Path(__file__).resolve().parents[1] / 'app/src/main/java/app/jmbatch/android'
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
stubs = {
'android/util/DisplayMetrics.java': '''package android.util;public class DisplayMetrics {public float density=1,scaledDensity=1;}''',
'android/content/res/Resources.java': '''package android.content.res;public class Resources {
public final Configuration config=new Configuration();public Configuration getConfiguration(){return config;}
public final android.util.DisplayMetrics metrics=new android.util.DisplayMetrics();public android.util.DisplayMetrics getDisplayMetrics(){return metrics;}}''',
'android/content/res/Configuration.java': 'package android.content.res;public class Configuration {public float fontScale=1;}',
'android/content/Context.java': '''package android.content;public class Context {public final android.content.res.Resources resources=new android.content.res.Resources();public android.content.res.Resources getResources(){return resources;}}''',
'android/view/Gravity.java': 'package android.view;public final class Gravity {public static final int CENTER=17;}',
'android/view/View.java': '''package android.view;import android.content.Context;import android.content.res.Resources;
public class View {
 public static final int GONE=8,VISIBLE=0,INVISIBLE=4,LAYOUT_DIRECTION_RTL=1;
 private final Context context;private int mw,mh,l,t,r,b,pl,pt,pr,pb,visibility,direction,minW,minH;private Runnable click;
 public View(Context c){context=c;}public Resources getResources(){return context.getResources();}
 public static class MeasureSpec {public static final int EXACTLY=0x40000000,AT_MOST=0x80000000,UNSPECIFIED=0;
 public static int makeMeasureSpec(int n,int mode){return n|mode;}public static int getSize(int spec){return spec&0x3fffffff;}public static int getMode(int spec){return spec&0xc0000000;}}
 public static int resolveSize(int size,int spec){int mode=MeasureSpec.getMode(spec),n=MeasureSpec.getSize(spec);return mode==MeasureSpec.EXACTLY?n:mode==MeasureSpec.AT_MOST?Math.min(size,n):size;}
 public void requestLayout(){}
 public void measure(int w,int h){onMeasure(w,h);}protected void onMeasure(int w,int h){setMeasuredDimension(resolveSize(minW,w),resolveSize(minH,h));}
 protected void setMeasuredDimension(int w,int h){mw=w;mh=h;}public int getMeasuredWidth(){return mw;}public int getMeasuredHeight(){return mh;}
 public void layout(int a,int z,int c,int d){l=a;t=z;r=c;b=d;onLayout(true,a,z,c,d);}protected void onLayout(boolean c,int l,int t,int r,int b){}
 public int getLeft(){return l;}public int getRight(){return r;}public int getTop(){return t;}public int getBottom(){return b;}
 public void setPadding(int a,int z,int c,int d){pl=a;pt=z;pr=c;pb=d;}public int getPaddingLeft(){return pl;}public int getPaddingRight(){return pr;}public int getPaddingTop(){return pt;}public int getPaddingBottom(){return pb;}
 public void setMinimumWidth(int v){minW=v;}public void setMinimumHeight(int v){minH=v;}public int getSuggestedMinimumWidth(){return minW;}public int getSuggestedMinimumHeight(){return minH;}
 public int getVisibility(){return visibility;}public void setVisibility(int v){visibility=v;}public int getLayoutDirection(){return direction;}public void setLayoutDirection(int v){direction=v;}
 public void setOnClickListener(Runnable r){click=r;}public boolean performClick(){if(click!=null)click.run();return click!=null;}
}''',
'android/view/ViewGroup.java': '''package android.view;import android.content.Context;import java.util.*;
public abstract class ViewGroup extends View {private final List<View> children=new ArrayList<>();public ViewGroup(Context c){super(c);}
public void addView(View v){children.add(v);}public int getChildCount(){return children.size();}public View getChildAt(int i){return children.get(i);}
public static class LayoutParams {public static final int WRAP_CONTENT=-2;public LayoutParams(int w,int h){}}
protected abstract LayoutParams generateDefaultLayoutParams();}''',
'android/widget/Button.java': '''package android.widget;import android.content.Context;import android.view.View;
public class Button extends View {
public boolean single=true,horizontal=true,caps=true,fontPadding=false;public int maxLines=1,minW=88,minH=48;
public Object ellipsis=new Object();public int chars=4;public float fontWidth=1,fontHeight=1,textSp=12;
public Button(Context c){super(c);setMinimumWidth(88);setMinimumHeight(48);}
public void setMinWidth(int v){minW=v;}public void setMinHeight(int v){minH=v;}public void setSingleLine(boolean v){single=v;}
public void setMaxLines(int v){maxLines=v;}public void setEllipsize(Object v){ellipsis=v;}public void setHorizontallyScrolling(boolean v){horizontal=v;}
public void setAllCaps(boolean v){caps=v;}public void setIncludeFontPadding(boolean v){fontPadding=v;}public void setGravity(int v){}
public int requiredHeight(int width){float px=textSp*getResources().getDisplayMetrics().scaledDensity;
int lines=single?1:Math.max(1,(int)Math.ceil(chars*px*fontWidth/Math.max(1,width-getPaddingLeft()-getPaddingRight())));
return (int)Math.ceil(Math.min(lines,maxLines)*px*fontHeight)+getPaddingTop()+getPaddingBottom();}
protected void onMeasure(int w,int h){int natural=(int)Math.ceil(chars*textSp*getResources().getDisplayMetrics().scaledDensity*fontWidth)+getPaddingLeft()+getPaddingRight();
int width=resolveSize(Math.max(natural,Math.max(minW,getSuggestedMinimumWidth())),w);
setMeasuredDimension(width,resolveSize(Math.max(requiredHeight(width),Math.max(minH,getSuggestedMinimumHeight())),h));}}
''',
'android/widget/ScrollView.java': '''package android.widget;import android.content.Context;import android.view.*;
public class ScrollView extends ViewGroup {public ScrollView(Context c){super(c);}public void setFillViewport(boolean v){}
protected LayoutParams generateDefaultLayoutParams(){return new LayoutParams(-2,-2);}
protected void onMeasure(int w,int h){View child=getChildAt(0);child.measure(w,MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED));setMeasuredDimension(resolveSize(child.getMeasuredWidth(),w),resolveSize(child.getMeasuredHeight(),h));}}''',
}
# Compile the real column policy without Android preference widgets.
mode_source=(source/'DisplayMode.java').read_text(encoding='utf-8')
start=mode_source.index('    public static int columns(')
end=mode_source.index('\n    }',start)+6
stubs['app/jmbatch/android/DisplayMode.java']='package app.jmbatch.android;public class DisplayMode {\n'+mode_source[start:end]+'\n}'
for name, text in stubs.items():
    file = out/name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text(text, encoding='utf-8')
harness = out/'ActionLayoutTest.java'
harness.write_text('''import app.jmbatch.android.*;import android.content.Context;import android.view.View;import android.widget.Button;
public final class ActionLayoutTest {
 static int scenarios,checks;static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
 static int exact(int n){return View.MeasureSpec.makeMeasureSpec(n,View.MeasureSpec.EXACTLY);}
 static void measure(View view,int width){view.measure(exact(width),0);view.layout(0,0,view.getMeasuredWidth(),view.getMeasuredHeight());}
 static void verify(ActionRow row,int width){measure(row,width);int active=0;
  for(int i=0;i<row.getChildCount();i++){Button b=(Button)row.getChildAt(i);if(b.getVisibility()==View.GONE)continue;active++;
   check(b.getLeft()>=row.getPaddingLeft()&&b.getRight()<=width-row.getPaddingRight(),"horizontal clipping");
   check(b.getTop()>=row.getPaddingTop()&&b.getBottom()<=row.getMeasuredHeight()-row.getPaddingBottom(),"vertical clipping");
   check(b.getMeasuredHeight()>=b.requiredHeight(b.getMeasuredWidth()),"font metrics clipped");
   check(b.getMeasuredHeight()>=Math.round(48*b.getResources().getDisplayMetrics().density),"small touch target");
   for(int j=0;j<i;j++){View a=row.getChildAt(j);if(a.getVisibility()==View.GONE)continue;
    check(a.getBottom()<=b.getTop()||b.getBottom()<=a.getTop()||a.getRight()<=b.getLeft()||b.getRight()<=a.getLeft(),"overlap");
    if(a.getTop()==b.getTop())check(a.getMeasuredHeight()==b.getMeasuredHeight(),"unaligned peers");}
  }check(active>0,"no actions");
 }
 public static void main(String[] args){
  for(float density:new float[]{1,2.75f})for(float scale:new float[]{1,1.3f,1.5f,2})
  for(float[] font:new float[][]{{1,1.2f},{1.3f,1.7f},{0.7f,2.1f}})for(int width:new int[]{240,320,360,640}){
   Context c=new Context();c.resources.metrics.density=density;c.resources.metrics.scaledDensity=density*scale;
   ActionButton[] buttons=new ActionButton[4];int[] clicks={0};for(int i=0;i<4;i++){
    ActionButton b=buttons[i]=new ActionButton(c);b.chars=i+2;b.fontWidth=font[0];b.fontHeight=font[1];b.setOnClickListener(()->clicks[0]++);
    check(!b.single&&!b.horizontal&&!b.caps&&b.fontPadding&&b.maxLines==Integer.MAX_VALUE&&b.ellipsis==null,"theme constrained label");
    check(b.minW==0&&b.getSuggestedMinimumWidth()==0,"theme width retained");}
   ActionRow row=new ActionRow(c,buttons);row.setPadding(7,3,9,5);int pixels=Math.round(width*density);
   verify(row,pixels);int oldHeight=row.getMeasuredHeight();buttons[1].chars=18;verify(row,pixels);
   check(row.getMeasuredHeight()>=oldHeight,"long label failed to reflow");
   buttons[2].setVisibility(View.GONE);verify(row,pixels);buttons[2].setVisibility(View.VISIBLE);verify(row,pixels);
   row.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);verify(row,pixels);
   for(ActionButton b:buttons)b.performClick();check(clicks[0]==4,"actions lost after reflow");
   ControlScroll scroll=new ControlScroll(c,row);scroll.measure(exact(pixels),View.MeasureSpec.makeMeasureSpec(240,View.MeasureSpec.AT_MOST));
   check(scroll.getMeasuredHeight()<=96,"controls consume content viewport");
   check(row.getMeasuredHeight()>scroll.getMeasuredHeight(),"oversized controls not scrollable");scenarios++;
  }
  Context c=new Context();ActionButton first=new ActionButton(c),second=new ActionButton(c);first.chars=second.chars=2;
  ActionRow row=new ActionRow(c,first,second);measure(row,320);check(first.getTop()==second.getTop(),"small labels unnecessarily stacked");
  first.setVisibility(View.GONE);measure(row,320);check(second.getMeasuredWidth()==320,"gone button leaves empty column");
  second.setVisibility(View.GONE);measure(row,320);check(row.getMeasuredHeight()==0,"empty row reserves height");
  ControlScroll exactScroll=new ControlScroll(c,row);exactScroll.measure(exact(320),exact(120));
  check(exactScroll.getMeasuredHeight()==120,"explicit parent height ignored");
  ActionButton legacy=new ActionButton(c);legacy.chars=5;legacy.fontHeight=1.7f;c.resources.metrics.scaledDensity=2;
  legacy.measure(exact(80),exact(46));check(legacy.requiredHeight(80)>46,"old fixed-height regression not reproduced");
  for(int width:new int[]{240,360,760})for(float scale:new float[]{1f,1.8f}){
   c.resources.config.fontScale=scale;ComicLayout comics=new ComicLayout(c);
   for(int i=0;i<7;i++){ActionButton item=new ActionButton(c);item.chars=10+i*5;comics.addView(item);}
   View retained=comics.getChildAt(3);
   for(boolean tiles:new boolean[]{false,true,false}){
    comics.setTiles(tiles);measure(comics,width);
    int columns=DisplayMode.columns(width,Math.round(168*scale),10,tiles);
    check(comics.getChildAt(3)==retained,"mode switch must retain cards and click targets");
    for(int i=0;i<comics.getChildCount();i++){
     View item=comics.getChildAt(i);check(item.getLeft()>=0&&item.getRight()<=width,"comic fits width");
     check(item.getBottom()<=comics.getMeasuredHeight(),"comic fits scroll extent");
     if(i>=columns)check(item.getTop()>=comics.getChildAt(i-columns).getBottom(),"rows cannot overlap");
     if(i%columns>0)check(item.getLeft()>=comics.getChildAt(i-1).getRight(),"columns cannot overlap");
     if(!tiles)check(item.getLeft()==0&&item.getRight()==width,"list uses full width");
    }
   }
  }
  System.out.println("Action layout: "+scenarios+" synthetic font/scale/width scenarios, "+checks+" checks passed (not Android rendering)");
 }
}''', encoding='utf-8')
jdk = Path(sys.argv[1])/'bin'
classes=out/'classes'; classes.mkdir(exist_ok=True)
subprocess.run([str(jdk/'javac.exe'), '-encoding', 'UTF-8', '-d', str(classes),
                *[str(out/name) for name in stubs],
                *[str(source/name) for name in ('ActionButton.java','ActionRow.java','ControlScroll.java','ComicLayout.java')], str(harness)], check=True)
subprocess.run([str(jdk/'java.exe'), '-cp', str(classes), 'ActionLayoutTest'], check=True)
