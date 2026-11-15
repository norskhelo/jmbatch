package app.jmbatch.android;

import android.app.*;
import android.os.*;
import android.util.AtomicFile;
import android.view.*;
import android.widget.*;
import java.io.File;
import java.lang.reflect.*;
import java.time.Duration;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowAlertDialog;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

/** Real framework dispatch through both overlapping production pages. */
@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w360dp-h800dp-mdpi",shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
@LooperMode(LooperMode.Mode.PAUSED)
public class PageInputRuntimeTest {
    ActivityController<MainActivity> controller;
    MainActivity activity;
    int rearTouches;

    static Field field(Class<?> type,String name)throws Exception {Field f=type.getDeclaredField(name);f.setAccessible(true);return f;}
    Object get(String name)throws Exception {return field(MainActivity.class,name).get(activity);}
    void settle(){shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1200));}
    void front(boolean library,boolean animate)throws Exception {
        Method m=MainActivity.class.getDeclaredMethod("setFrontPage",boolean.class,boolean.class);m.setAccessible(true);m.invoke(activity,library,animate);settle();
    }
    @Before public void setup()throws Exception {
        new Instrumentation().setInTouchMode(true);
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class})field(type,"instance").set(null,null);
        for(String name:new String[]{"queue.json","library.json"})new AtomicFile(new File(RuntimeEnvironment.getApplication().getFilesDir(),name)).delete();
        RuntimeEnvironment.getApplication().getSharedPreferences("updates",0).edit().putBoolean("automatic",false).commit();
        controller=Robolectric.buildActivity(MainActivity.class);activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();
        ((Handler)get("handler")).removeCallbacksAndMessages(null);settle();
    }
    @After public void close(){
        if(controller!=null){AlertDialog d=ShadowAlertDialog.getLatestAlertDialog();if(d!=null)d.dismiss();controller.pause().stop().destroy();shadowOf(Looper.getMainLooper()).idle();}
    }
    void observe(View view){
        view.setOnTouchListener((v,e)->{rearTouches++;return false;});
        view.setOnGenericMotionListener((v,e)->{rearTouches++;return false;});
        if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++)observe(((ViewGroup)view).getChildAt(i));
    }
    void touch(int action,float x,float y,long down){
        MotionEvent e=MotionEvent.obtain(down,SystemClock.uptimeMillis(),action,x,y,0);activity.dispatchTouchEvent(e);e.recycle();
    }
    float[] point(View view,float x,float y){int[] p=new int[2];view.getLocationOnScreen(p);return new float[]{p[0]+x,p[1]+y};}
    void gesture(float[] p,boolean drag,boolean hold){
        long down=SystemClock.uptimeMillis();touch(MotionEvent.ACTION_DOWN,p[0],p[1],down);
        if(hold)shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(ViewConfiguration.getLongPressTimeout()+100));
        if(drag)touch(MotionEvent.ACTION_MOVE,p[0],p[1]+80,down);
        touch(MotionEvent.ACTION_UP,p[0],p[1]+(drag?80:0),down);shadowOf(Looper.getMainLooper()).idle();
    }
    void blankArea(boolean library,boolean drag,boolean hold)throws Exception {
        front(library,false);View front=(View)get(library?"libraryHost":"downloadPanel"),rear=(View)get(library?"downloadPanel":"libraryHost");observe(rear);
        gesture(point(front,2,40),drag,hold);
        assertEquals("The covered page must receive no part of a foreground gesture",0,rearTouches);
        assertEquals(library,get("libraryVisible"));
    }
    @Test public void downloadBlankTapDoesNotReachLibrary()throws Exception {blankArea(false,false,false);}
    @Test public void downloadBlankLongPressDoesNotReachLibrary()throws Exception {blankArea(false,false,true);}
    @Test public void downloadBlankDragDoesNotReachLibrary()throws Exception {blankArea(false,true,false);}
    @Test public void libraryBlankTapDoesNotReachDownload()throws Exception {blankArea(true,false,false);}
    @Test public void mouseWheelOverBlankDoesNotReachRearPage()throws Exception {
        for(boolean library:new boolean[]{false,true}){
            front(library,false);View front=(View)get(library?"libraryHost":"downloadPanel"),rear=(View)get(library?"downloadPanel":"libraryHost");
            rear.setOnGenericMotionListener((v,e)->{rearTouches++;return true;});
            float[] p=point(front,2,40);MotionEvent e=MotionEvent.obtain(0,SystemClock.uptimeMillis(),MotionEvent.ACTION_SCROLL,p[0],p[1],0);e.setSource(InputDevice.SOURCE_MOUSE);
            activity.dispatchGenericMotionEvent(e);e.recycle();assertEquals(0,rearTouches);rear.setOnGenericMotionListener(null);
        }
    }
    @Test public void hiddenPageCannotTakeKeyboardFocus()throws Exception {
        for(boolean library:new boolean[]{false,true}){
            front(library,false);ViewGroup rear=(ViewGroup)get(library?"downloadPanel":"libraryHost");
            Button b=ClearHistoryRuntimeTest.button(rear,library?"清除下载记录":"排序");
            if(b==null)b=findButton(rear);assertNotNull(b);b.setFocusableInTouchMode(true);
            assertFalse("Covered controls cannot capture keyboard focus",b.requestFocus());
        }
    }
    Button findButton(View view){if(view instanceof Button)return (Button)view;if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){Button b=findButton(((ViewGroup)view).getChildAt(i));if(b!=null)return b;}return null;}
    @Test public void activeButtonsAndHeaderSwitchStillWork()throws Exception {
        for(int i=0;i<2;i++){
            View switcher=(View)get("pageSwitch");gesture(point(switcher,switcher.getWidth()/2f,12),false,false);settle();assertTrue((Boolean)get("libraryVisible"));
            gesture(point(switcher,switcher.getWidth()/2f,12),false,false);settle();assertFalse((Boolean)get("libraryVisible"));
        }
        Button add=ClearHistoryRuntimeTest.button((View)get("downloadPanel"),"添加下载");assertNotNull(add);gesture(point(add,add.getWidth()/2f,add.getHeight()/2f),false,false);settle();
        assertTrue(ShadowAlertDialog.getLatestAlertDialog().isShowing());
    }
    @Test public void downloadRowsStillScrollAndLongPressWithoutTouchingLibrary()throws Exception {
        Store store=Store.get(activity);
        for(int i=0;i<20;i++){Store.Task t=new Store.Task("99"+i,new Store.Settings());t.status="paused";store.tasks.add(t);}
        Method render=MainActivity.class.getDeclaredMethod("render");render.setAccessible(true);render.invoke(activity);settle();
        observe((View)get("libraryHost"));ScrollView scroll=(ScrollView)get("taskScroll");
        float[] p=point(scroll,scroll.getWidth()/2f,scroll.getHeight()*.8f);long down=SystemClock.uptimeMillis();
        touch(MotionEvent.ACTION_DOWN,p[0],p[1],down);
        for(int i=1;i<=4;i++){shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(30));touch(MotionEvent.ACTION_MOVE,p[0],p[1]-i*30,down);}
        touch(MotionEvent.ACTION_UP,p[0],p[1]-120,down);assertTrue("Download list must still scroll",scroll.getScrollY()>0);
        settle();scroll.scrollTo(0,0);settle();View card=((ViewGroup)get("queue")).getChildAt(0);
        gesture(point(card,card.getWidth()/2f,card.getHeight()/2f),false,true);settle();
        assertTrue((Boolean)get("selecting"));assertEquals(View.VISIBLE,((View)get("taskSheet")).getVisibility());assertEquals(0,rearTouches);
    }
}
