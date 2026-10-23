package app.jmbatch.android;

import android.content.Context;
import android.view.Gravity;
import android.widget.Button;

/** Content-sized buttons that keep the user's font and SP scaling. */
public final class ActionButton extends Button {
    public ActionButton(Context context) {
        super(context);
        float density=getResources().getDisplayMetrics().density;
        int padding=Math.round(8*density),minimum=Math.round(48*density);
        // TextView and View maintain separate minimum dimensions.
        setMinWidth(0);setMinimumWidth(0);
        setMinHeight(minimum);setMinimumHeight(minimum);
        setSingleLine(false);setMaxLines(Integer.MAX_VALUE);setEllipsize(null);
        setHorizontallyScrolling(false);setAllCaps(false);setIncludeFontPadding(true);
        setGravity(Gravity.CENTER);setPadding(padding,padding,padding,padding);
        setTextColor(Ui.INK);setTextSize(14);setBackgroundTintList(null);
        setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x18777777),Ui.shape(context,0xfffafafb,9,true),null));
    }
}
