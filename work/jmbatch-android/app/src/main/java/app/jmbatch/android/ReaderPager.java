package app.jmbatch.android;

import android.animation.*;
import android.content.Context;
import android.graphics.Bitmap;
import android.view.*;
import android.widget.*;

/** Two persistent native image layers, with an explicit requested/displayed page. */
public final class ReaderPager extends FrameLayout {
    public interface Listener {
        Bitmap lookup(int page);
        void requested();
        void committed(int page);
    }
    private final Listener listener;
    private ImageView front,back;
    private Bitmap shown,incoming;
    private ValueAnimator animator;
    private VelocityTracker velocity;
    private final int total,slop,minVelocity;
    private int page=-1,target,direction=1,pointer=-1;
    private int first=0,end;
    private float downX,downY,offset;
    private boolean dragging,vertical,closed;

    public ReaderPager(Context context,int total,int initial,Listener listener){
        super(context);this.total=total;end=total;target=initial;this.listener=listener;
        ViewConfiguration config=ViewConfiguration.get(context);
        slop=config.getScaledTouchSlop();minVelocity=config.getScaledMinimumFlingVelocity()*4;
        front=image(context);back=image(context);addView(front);addView(back);back.setVisibility(INVISIBLE);
        setClipChildren(true);setClickable(true);
    }
    private ImageView image(Context context){
        ImageView image=new ImageView(context);image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setLayoutParams(new FrameLayout.LayoutParams(-1,-1));return image;
    }
    public int target(){return target;}
    public void setRange(int first,int end){this.first=first;this.end=end;}
    private int clamp(int index){return Math.max(first,Math.min(end-1,index));}
    public int displayed(){return page;}
    public int direction(){return direction;}
    public boolean busy(){return animator!=null||dragging||target!=page;}
    public void go(int requested){
        if(closed)return;
        cancelAnimation();releaseTouch();
        int next=clamp(requested);
        if(next!=target)direction=next>target?1:-1;
        target=next;ready();listener.requested();
    }
    public void ready(){
        if(closed||animator!=null||pointer!=-1)return;
        Bitmap bitmap=listener.lookup(target);if(bitmap==null)return;
        if(shown==bitmap&&page==target)return;
        if(shown==null||page==target){
            shown=bitmap;page=target;front.setImageBitmap(bitmap);place(0,0);listener.committed(page);
        }else{
            incoming=bitmap;back.setImageBitmap(bitmap);back.setVisibility(VISIBLE);
            settle(target>page?1:-1,true);
        }
    }
    private void place(float x,int dir){offset=x;front.setTranslationX(x);back.setTranslationX(x+dir*getWidth());}
    private void cancelAnimation(){
        if(animator!=null){ValueAnimator old=animator;animator=null;old.removeAllListeners();old.cancel();}
        incoming=null;back.setImageDrawable(null);back.setVisibility(INVISIBLE);place(0,0);
    }
    private void settle(int dir,boolean commit){
        final int destination=target;
        float end=commit?-dir*getWidth():0;
        long duration=Math.max(60,Math.round(200*Math.abs(end-offset)/Math.max(1,getWidth())));
        ValueAnimator running=ValueAnimator.ofFloat(offset,end);animator=running;
        running.setDuration(ValueAnimator.areAnimatorsEnabled()?duration:0);
        running.setInterpolator(new android.view.animation.DecelerateInterpolator());
        running.addUpdateListener(a->place((Float)a.getAnimatedValue(),dir));
        running.addListener(new AnimatorListenerAdapter(){
            @Override public void onAnimationEnd(Animator animation){
                if(animator!=running||closed)return;
                animator=null;
                if(commit){ImageView old=front;front=back;back=old;shown=incoming;page=destination;}
                incoming=null;back.setImageDrawable(null);back.setVisibility(INVISIBLE);place(0,0);
                if(commit)listener.committed(page);
                ready();listener.requested();
            }
        });running.start();
    }
    @Override public boolean onTouchEvent(MotionEvent event){
        if(closed)return false;
        int action=event.getActionMasked();
        if(action==MotionEvent.ACTION_DOWN){
            cancelAnimation();releaseTouch();
            if(page<0)return true;
            target=page;pointer=event.getPointerId(0);downX=event.getX();downY=event.getY();
            velocity=VelocityTracker.obtain();velocity.addMovement(event);listener.requested();return true;
        }
        if(pointer==-1)return true;
        if(velocity!=null)velocity.addMovement(event);
        if(action==MotionEvent.ACTION_CANCEL||action==MotionEvent.ACTION_POINTER_DOWN||action==MotionEvent.ACTION_POINTER_UP){
            target=page;releaseTouch();settle(direction,false);listener.requested();return true;
        }
        int index=event.findPointerIndex(pointer);if(index<0){releaseTouch();cancelAnimation();return true;}
        float dx=event.getX(index)-downX,dy=event.getY(index)-downY;
        if(action==MotionEvent.ACTION_MOVE){
            if(!dragging&&!vertical&&Math.max(Math.abs(dx),Math.abs(dy))>slop){
                dragging=Math.abs(dx)>Math.abs(dy);vertical=!dragging;
            }
            if(dragging){
                direction=dx<0?1:-1;int neighbor=page+direction;incoming=neighbor>=first&&neighbor<end?listener.lookup(neighbor):null;
                back.setImageBitmap(incoming);back.setVisibility(incoming==null?INVISIBLE:VISIBLE);
                float x=incoming==null?Math.max(-getWidth()*.12f,Math.min(getWidth()*.12f,dx*.22f)):Math.max(-getWidth(),Math.min(getWidth(),dx));
                place(x,direction);
            }
            return true;
        }
        if(action==MotionEvent.ACTION_UP){
            if(dragging){
                velocity.computeCurrentVelocity(1000);float speed=velocity.getXVelocity(pointer);
                int dir=dx<0?1:-1;
                boolean commit=Math.abs(dx)>getWidth()*.22f||(Math.abs(dx)>slop*2&&Math.abs(speed)>minVelocity&&speed*dx>0);
                target=commit?clamp(page+dir):page;direction=dir;
                releaseTouch();settle(dir,commit&&target!=page&&incoming!=null);listener.requested();
            }else{
                releaseTouch(); // ReaderViewport handles taps; all positions toggle controls.
                ready();
            }
            return true;
        }
        return true;
    }
    @Override public boolean performClick(){super.performClick();return true;}
    private void releaseTouch(){pointer=-1;dragging=vertical=false;if(velocity!=null){velocity.recycle();velocity=null;}}
    public void dispose(){closed=true;releaseTouch();cancelAnimation();front.setImageDrawable(null);shown=null;}
    @Override protected void onSizeChanged(int w,int h,int oldw,int oldh){
        super.onSizeChanged(w,h,oldw,oldh);cancelAnimation();releaseTouch();
        if(page>=0)target=page;
        post(()->{if(!closed){ready();listener.requested();}});
    }
}
