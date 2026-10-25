package app.jmbatch.android;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import java.util.ArrayList;
import java.util.List;

/** Equal-width actions, reflowed using the actual font's measured content width. */
public final class ActionRow extends ViewGroup {
    private final List<View> visible=new ArrayList<>();
    private final int gap,maxColumns;
    private boolean singleRow;
    private int columns=1,cellWidth;
    private int[] heights=new int[0];

    public ActionRow(Context context,View... actions) {
        this(context,Integer.MAX_VALUE,actions);
    }
    public ActionRow(Context context,int maxColumns,View... actions) {
        super(context);
        this.maxColumns=Math.max(1,maxColumns);
        gap=Math.round(8*getResources().getDisplayMetrics().density);
        for(View action:actions)addView(action);
    }
    public ActionRow keepSingleRow(){singleRow=true;requestLayout();return this;}

    @Override protected LayoutParams generateDefaultLayoutParams() {
        return new LayoutParams(LayoutParams.WRAP_CONTENT,LayoutParams.WRAP_CONTENT);
    }

    @Override protected void onMeasure(int widthSpec,int heightSpec) {
        visible.clear();int widest=0;
        int free=MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED);
        for(int i=0;i<getChildCount();i++) {
            View child=getChildAt(i);if(child.getVisibility()==GONE)continue;
            visible.add(child);child.measure(free,free);
            widest=Math.max(widest,child.getMeasuredWidth());
        }
        int count=visible.size(),horizontal=getPaddingLeft()+getPaddingRight();
        int desired=horizontal+count*widest+Math.max(0,count-1)*gap;
        int width=MeasureSpec.getMode(widthSpec)==MeasureSpec.UNSPECIFIED
            ?Math.max(getSuggestedMinimumWidth(),desired):MeasureSpec.getSize(widthSpec);
        int available=Math.max(0,width-horizontal);
        columns=Math.max(1,singleRow?count:Math.min(maxColumns,count));
        while(!singleRow&&columns>1&&(available-(columns-1)*gap)/columns<widest)columns--;
        int rows=Math.max(1,(count+columns-1)/columns);
        columns=Math.max(1,(count+rows-1)/rows);
        cellWidth=Math.min(widest,Math.max(0,(available-(columns-1)*gap)/columns));
        heights=new int[(count+columns-1)/columns];
        int exactWidth=MeasureSpec.makeMeasureSpec(cellWidth,MeasureSpec.EXACTLY);
        for(int i=0;i<count;i++) {
            View child=visible.get(i);child.measure(exactWidth,free);
            heights[i/columns]=Math.max(heights[i/columns],child.getMeasuredHeight());
        }
        // Keep peers aligned after wrapping, without clipping taller font metrics.
        for(int i=0;i<count;i++){
            View child=visible.get(i);
            if(child instanceof ActionButton&&((ActionButton)child).isIconOnly())continue;
            child.measure(exactWidth,MeasureSpec.makeMeasureSpec(heights[i/columns],MeasureSpec.EXACTLY));
        }
        int height=getPaddingTop()+getPaddingBottom()+Math.max(0,heights.length-1)*gap;
        for(int rowHeight:heights)height+=rowHeight;
        setMeasuredDimension(resolveSize(width,widthSpec),resolveSize(Math.max(getSuggestedMinimumHeight(),height),heightSpec));
    }

    @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom) {
        boolean rtl=getLayoutDirection()==LAYOUT_DIRECTION_RTL;
        int y=getPaddingTop();
        for(int i=0;i<visible.size();i++) {
            int column=i%columns,row=i/columns;
            if(column==0&&row>0)y+=heights[row-1]+gap;
            int rowCount=Math.min(columns,visible.size()-row*columns);
            int used=rowCount*cellWidth+Math.max(0,rowCount-1)*gap;
            int offset=Math.max(0,(right-left-getPaddingLeft()-getPaddingRight()-used)/2)+column*(cellWidth+gap);
            int x=rtl?right-left-getPaddingRight()-offset-cellWidth:getPaddingLeft()+offset;
            View child=visible.get(i);int dx=(cellWidth-child.getMeasuredWidth())/2,dy=(heights[row]-child.getMeasuredHeight())/2;
            child.layout(x+dx,y+dy,x+dx+child.getMeasuredWidth(),y+dy+child.getMeasuredHeight());
        }
    }
}
