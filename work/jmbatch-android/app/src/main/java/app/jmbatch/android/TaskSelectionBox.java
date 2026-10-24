package app.jmbatch.android;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Checkable;

/** A task selection square: reveal the outline, then fill it when selected. */
public final class TaskSelectionBox extends View implements Checkable {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF box=new RectF();
    private boolean checked;
    private float fill;
    private ValueAnimator filling;

    public TaskSelectionBox(Context context){super(context);setVisibility(GONE);setFocusable(true);}

    public void bind(boolean selecting,boolean value){
        bind(selecting,value,true);
    }

    public void bind(boolean selecting,boolean value,boolean animate){
        if(!selecting){
            cancelAnimation();checked=false;fill=0;setSelected(false);setAlpha(1);setVisibility(GONE);return;
        }
        boolean entering=getVisibility()!=VISIBLE;
        if(animate&&!entering&&checked==value)return; // Progress refreshes must not restart the effect.
        cancelAnimation();checked=value;setSelected(value);setVisibility(VISIBLE);
        float target=value?1:0;
        if(!animate||!isAttachedToWindow()||!ValueAnimator.areAnimatorsEnabled()){fill=target;setAlpha(1);invalidate();return;}
        if(entering){fill=0;setAlpha(0);animate().alpha(1).setDuration(100).start();}
        else setAlpha(1);
        if(fill!=target){
            filling=ValueAnimator.ofFloat(fill,target);filling.setStartDelay(entering?100:0);filling.setDuration(160);
            filling.addUpdateListener(animation->{fill=(float)animation.getAnimatedValue();invalidate();});filling.start();
        }
        invalidate();
    }

    private void cancelAnimation(){animate().cancel();if(filling!=null){filling.cancel();filling=null;}}
    @Override protected void onDraw(Canvas canvas){
        super.onDraw(canvas);float density=getResources().getDisplayMetrics().density,side=20*density,radius=2*density;
        box.set((getWidth()-side)/2,(getHeight()-side)/2,(getWidth()+side)/2,(getHeight()+side)/2);
        paint.setColor(Ui.ACCENT);paint.setStyle(Paint.Style.FILL);
        if(fill>0){int saved=canvas.save();canvas.clipRect(box.left,box.bottom-side*fill,box.right,box.bottom);canvas.drawRoundRect(box,radius,radius,paint);canvas.restoreToCount(saved);}
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(1.5f*density);canvas.drawRoundRect(box,radius,radius,paint);
    }
    @Override public boolean isChecked(){return checked;}
    @Override public void setChecked(boolean value){bind(getVisibility()==VISIBLE,value);}
    @Override public void toggle(){setChecked(!checked);}
    @Override public void onInitializeAccessibilityNodeInfo(AccessibilityNodeInfo info){super.onInitializeAccessibilityNodeInfo(info);info.setClassName("android.widget.CheckBox");info.setCheckable(true);info.setChecked(checked);}
    @Override protected void onDetachedFromWindow(){cancelAnimation();super.onDetachedFromWindow();}
}
