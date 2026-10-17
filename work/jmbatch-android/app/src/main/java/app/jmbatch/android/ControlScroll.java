package app.jmbatch.android;

import android.content.Context;
import android.view.View;
import android.widget.ScrollView;

/** Let large-font controls scroll while reserving space for the reader or list. */
public final class ControlScroll extends ScrollView {
    public ControlScroll(Context context,View content) {
        super(context);setFillViewport(false);addView(content);
    }
    @Override protected void onMeasure(int widthSpec,int heightSpec) {
        if(MeasureSpec.getMode(heightSpec)==MeasureSpec.AT_MOST) {
            int limit=Math.round(MeasureSpec.getSize(heightSpec)*0.4f);
            heightSpec=MeasureSpec.makeMeasureSpec(limit,MeasureSpec.AT_MOST);
        }
        super.onMeasure(widthSpec,heightSpec);
    }
}
