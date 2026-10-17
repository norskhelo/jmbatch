package app.jmbatch.android;

import android.content.Context;
import android.view.*;
import android.widget.FrameLayout;

/** Observe taps without intercepting the list's scroll or the pager's drag. */
public final class ReaderViewport extends FrameLayout {
    private final ReaderTap tap;
    public ReaderViewport(Context context){
        super(context);tap=new ReaderTap(ViewConfiguration.get(context).getScaledTouchSlop(),ViewConfiguration.getLongPressTimeout());
        setClickable(true);
    }
    @Override public boolean dispatchTouchEvent(MotionEvent event){
        boolean clicked=false;
        switch(event.getActionMasked()){
            case MotionEvent.ACTION_DOWN:tap.down(event.getRawX(),event.getRawY(),event.getEventTime());break;
            case MotionEvent.ACTION_MOVE:tap.move(event.getRawX(),event.getRawY());break;
            case MotionEvent.ACTION_UP:clicked=tap.up(event.getRawX(),event.getRawY(),event.getEventTime());break;
            default:tap.cancel();break;
        }
        boolean handled=super.dispatchTouchEvent(event);
        if(clicked)performClick();
        return handled;
    }
    // Blank space is still a tap target; dispatchTouchEvent owns its one click.
    @Override public boolean onTouchEvent(MotionEvent event){return true;}
    @Override public boolean performClick(){super.performClick();return true;}
}
