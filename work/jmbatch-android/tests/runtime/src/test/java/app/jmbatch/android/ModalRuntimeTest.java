package app.jmbatch.android;

import android.app.*;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.lang.reflect.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.*;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

/** Window geometry must be final before attachment, not in the queued show callback. */
@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w360dp-h800dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
public class ModalRuntimeTest {
    ActivityController<MainActivity> controller;
    MainActivity activity;
    AlertDialog dialog;

    static Object field(Object target,String name)throws Exception {
        Field f=target.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(target);
    }
    @Before public void setup()throws Exception {
        new Instrumentation().setInTouchMode(true);
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){
            Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);
        }
        RuntimeEnvironment.getApplication().getSharedPreferences("updates",0).edit().putBoolean("automatic",false).commit();
        controller=Robolectric.buildActivity(MainActivity.class);activity=controller.get();
        activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();
        ((Handler)field(activity,"handler")).removeCallbacksAndMessages(null);
        shadowOf(Looper.getMainLooper()).idle();
    }
    @After public void close(){
        if(dialog!=null)dialog.dismiss();
        if(controller!=null)controller.pause().stop().destroy();
        shadowOf(Looper.getMainLooper()).idle();
    }
    void openDownload()throws Exception {
        Method m=MainActivity.class.getDeclaredMethod("addDownload");m.setAccessible(true);m.invoke(activity);
        dialog=(AlertDialog)field(activity,"addDialog");
    }
    void assertReady(){
        Window window=dialog.getWindow();WindowManager.LayoutParams params=window.getAttributes();
        int expected=Math.min(Ui.dp(activity,480),activity.getResources().getDisplayMetrics().widthPixels-Ui.dp(activity,36));
        assertEquals("Final width must be set before show returns",expected,params.width);
        assertEquals(WindowManager.LayoutParams.WRAP_CONTENT,params.height);
        assertEquals(Gravity.CENTER_VERTICAL,params.gravity&Gravity.VERTICAL_GRAVITY_MASK);
        assertEquals(0,params.y);assertEquals(.22f,params.dimAmount,.001f);
        assertTrue(window.getDecorView().getBackground() instanceof ColorDrawable);
        assertEquals(Color.TRANSPARENT,((ColorDrawable)window.getDecorView().getBackground()).getColor());
    }
    void assertStableAfterCallbacks(){
        assertReady();
        WindowManager.LayoutParams before=new WindowManager.LayoutParams();before.copyFrom(dialog.getWindow().getAttributes());
        shadowOf(Looper.getMainLooper()).idle();assertReady();
        assertEquals("Queued callbacks must not reposition or resize the visible dialog",0,before.copyFrom(dialog.getWindow().getAttributes()));
    }
    @Test public void downloadIsPositionedBeforeQueuedShowCallback()throws Exception {
        openDownload();assertStableAfterCallbacks();
        EditText ids=(EditText)field(activity,"ids");View panel=(View)ids.getParent().getParent();
        assertEquals(Ui.dp(activity,40),panel.getPaddingTop());assertEquals(Ui.dp(activity,10),panel.getPaddingBottom());
        assertTrue(ids.isFocusable());
        ids.setText("123456\n234567\n345678");shadowOf(Looper.getMainLooper()).idle();
        assertEquals("123456\n234567\n345678",ids.getText().toString());
        assertEquals(WindowManager.LayoutParams.WRAP_CONTENT,dialog.getWindow().getAttributes().height);
        dialog.dismiss();openDownload();assertStableAfterCallbacks();
    }
    @Test @Config(qualifiers="w720dp-h1000dp-mdpi")
    public void wideDownloadUsesCappedWidthImmediately()throws Exception {openDownload();assertStableAfterCallbacks();assertEquals(480,dialog.getWindow().getAttributes().width);}
    @Test @Config(qualifiers="w320dp-h600dp-mdpi")
    public void narrowDownloadUsesAvailableWidthImmediately()throws Exception {openDownload();assertStableAfterCallbacks();assertEquals(284,dialog.getWindow().getAttributes().width);}
    @Test public void callerShowListenerCannotReplaceWindowSetup(){
        LinearLayout body=Ui.column(activity);body.addView(Ui.text(activity,"确认",17));
        dialog=Ui.modal(activity,body,false);final int[] calls={0};
        dialog.setOnShowListener(ignored->{assertReady();calls[0]++;});
        dialog.show();assertStableAfterCallbacks();assertEquals(1,calls[0]);
        dialog.dismiss();shadowOf(Looper.getMainLooper()).idle();dialog.show();assertStableAfterCallbacks();assertEquals(2,calls[0]);
    }
}
