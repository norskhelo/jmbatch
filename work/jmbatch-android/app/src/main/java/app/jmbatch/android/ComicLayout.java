package app.jmbatch.android;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;

/** Reflows the existing bounded queue cards, retaining their actions and covers. */
public final class ComicLayout extends ViewGroup {
    private boolean tiles;
    private int columns=1,cellWidth;
    private int[] heights=new int[0];
    public ComicLayout(Context context){super(context);}
    public void setTiles(boolean value){tiles=value;requestLayout();}
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    @Override protected LayoutParams generateDefaultLayoutParams(){return new LayoutParams(-1,-2);}
    @Override protected void onMeasure(int widthSpec,int heightSpec){
        int width=MeasureSpec.getSize(widthSpec),gap=dp(10);
        int minimum=Math.round(dp(168)*Math.max(1f,getResources().getConfiguration().fontScale));
        columns=DisplayMode.columns(width,minimum,gap,tiles);
        cellWidth=Math.max(0,(width-(columns-1)*gap)/columns);
        heights=new int[(getChildCount()+columns-1)/columns];
        int exact=MeasureSpec.makeMeasureSpec(cellWidth,MeasureSpec.EXACTLY);
        int free=MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED);
        for(int i=0;i<getChildCount();i++){
            View child=getChildAt(i);child.measure(exact,free);
            heights[i/columns]=Math.max(heights[i/columns],child.getMeasuredHeight());
        }
        int height=0;for(int h:heights)height+=h+gap;
        setMeasuredDimension(resolveSize(width,widthSpec),resolveSize(height,heightSpec));
    }
    @Override protected void onLayout(boolean changed,int left,int top,int right,int bottom){
        int y=0,gap=dp(10);boolean rtl=getLayoutDirection()==LAYOUT_DIRECTION_RTL;
        for(int i=0;i<getChildCount();i++){
            int row=i/columns,col=i%columns;if(col==0&&row>0)y+=heights[row-1]+gap;
            int x=rtl?right-left-(col+1)*cellWidth-col*gap:col*(cellWidth+gap);
            getChildAt(i).layout(x,y,x+cellWidth,y+heights[row]);
        }
    }
}
