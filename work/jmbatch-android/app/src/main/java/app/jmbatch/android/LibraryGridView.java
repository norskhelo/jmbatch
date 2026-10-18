package app.jmbatch.android;

import android.content.Context;
import android.view.View;
import android.widget.GridView;

/** Restore an adapter anchor without GridView's unsafe inherited ListView path. */
public final class LibraryGridView extends GridView {
    private int restorePosition=-1,restoreTop;
    public LibraryGridView(Context context){super(context);}
    public void restorePosition(int position,int top){
        restorePosition=position;restoreTop=top;
        // GridView.setSelection reconciles the resurrect position in touch mode.
        setSelection(position);
    }
    @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom){
        super.onLayout(changed,left,top,right,bottom);
        if(restorePosition<0)return;
        View anchor=getChildAt(restorePosition-getFirstVisiblePosition());
        restorePosition=-1;
        if(anchor!=null)scrollListBy(anchor.getTop()-restoreTop);
    }
}
