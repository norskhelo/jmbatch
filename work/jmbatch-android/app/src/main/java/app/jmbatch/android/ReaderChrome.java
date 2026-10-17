package app.jmbatch.android;

import android.animation.*;
import android.content.Context;
import android.view.*;

/** Clip and fade controls while expanding the viewport, without changing its width. */
public final class ReaderChrome extends ViewGroup {
    private final View top,bottom,viewport;
    private final Runnable settled;
    private ValueAnimator animator;
    private float fraction=1;
    private boolean visible=true,closed;
    public ReaderChrome(Context context,View top,View bottom,View viewport,Runnable settled){
        super(context);this.top=top;this.bottom=bottom;this.viewport=viewport;this.settled=settled;
        addView(viewport);addView(top);addView(bottom);setClipChildren(true);
    }
    public boolean controlsVisible(){return visible;}
    @Override protected LayoutParams generateDefaultLayoutParams(){return new LayoutParams(-1,-1);}
    public boolean animating(){return animator!=null;}
    public void toggle(){show(!visible);}
    public void show(boolean show){
        if(closed||(visible==show&&animator==null))return;
        if(animator!=null){animator.removeAllListeners();animator.cancel();}
        visible=show;top.setVisibility(VISIBLE);bottom.setVisibility(VISIBLE);
        ValueAnimator running=ValueAnimator.ofFloat(fraction,show?1f:0f);animator=running;
        running.setDuration(ValueAnimator.areAnimatorsEnabled()?220:0);
        running.setInterpolator(new android.view.animation.DecelerateInterpolator());
        running.addUpdateListener(a->{fraction=(Float)a.getAnimatedValue();top.setAlpha(fraction);bottom.setAlpha(fraction);requestLayout();});
        running.addListener(new AnimatorListenerAdapter(){
            @Override public void onAnimationEnd(Animator animation){
                if(closed||animator!=running)return;
                animator=null;
                top.setVisibility(visible?VISIBLE:INVISIBLE);bottom.setVisibility(visible?VISIBLE:INVISIBLE);
                requestLayout();post(()->{if(!closed)settled.run();});
            }
        });running.start();
    }
    @Override protected void onMeasure(int widthSpec,int heightSpec){
        int width=MeasureSpec.getSize(widthSpec),height=MeasureSpec.getSize(heightSpec);
        int ws=MeasureSpec.makeMeasureSpec(width,MeasureSpec.EXACTLY),hs=MeasureSpec.makeMeasureSpec(height,MeasureSpec.AT_MOST);
        top.measure(ws,hs);bottom.measure(ws,hs);
        int remaining=Math.max(1,height-Math.round((top.getMeasuredHeight()+bottom.getMeasuredHeight())*fraction));
        viewport.measure(ws,MeasureSpec.makeMeasureSpec(remaining,MeasureSpec.EXACTLY));
        setMeasuredDimension(width,height);
    }
    @Override protected void onLayout(boolean changed,int l,int t,int r,int b){
        int width=r-l,height=b-t,th=top.getMeasuredHeight(),bh=bottom.getMeasuredHeight();
        int ts=Math.round(th*fraction),bs=Math.round(bh*fraction);
        viewport.layout(0,ts,width,height-bs);
        top.layout(0,ts-th,width,ts);bottom.layout(0,height-bs,width,height-bs+bh);
    }
    public void dispose(){closed=true;if(animator!=null){animator.removeAllListeners();animator.cancel();animator=null;}}
}
