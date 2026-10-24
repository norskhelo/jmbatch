package app.jmbatch.android;

import android.content.Context;
import android.view.Gravity;
import android.widget.Button;

/** Content-sized buttons that keep the user's font and SP scaling. */
public final class ActionButton extends Button {
    private boolean iconOnly;
    public void setIconOnly(boolean value){iconOnly=value;requestLayout();}
    public boolean isIconOnly(){return iconOnly;}
    public ActionButton(Context context) {
        super(context);
        float density=getResources().getDisplayMetrics().density;
        int padding=Math.round(6*density);
        // TextView and View maintain separate minimum dimensions.
        setMinWidth(0);setMinimumWidth(0);
        setLayoutParams(new android.view.ViewGroup.LayoutParams(-2,-2));
        setMinHeight(0);setMinimumHeight(0);
        setSingleLine(false);setMaxLines(Integer.MAX_VALUE);setEllipsize(null);
        setHorizontallyScrolling(false);setAllCaps(false);setIncludeFontPadding(false);
        setGravity(Gravity.CENTER);setPadding(padding,0,padding,0);
        setTextColor(Ui.INK);setTextSize(16);setBackgroundTintList(null);
        setStateListAnimator(null);setElevation(0);
        setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x18777777),Ui.shape(context,0xfffafafb,9,true),null));
    }
    @Override protected void onMeasure(int width,int height){
        Ui.compact(this);
        super.onMeasure(width,height);
        if(Ui.compact(this))super.onMeasure(width,height);
        if(iconOnly){
            int side=Math.max(Ui.controlHeight(this),getMeasuredHeight());
            side=Math.min(resolveSize(side,width),resolveSize(side,height));
            int exact=MeasureSpec.makeMeasureSpec(side,MeasureSpec.EXACTLY);
            super.onMeasure(exact,exact);
        }
    }
}
