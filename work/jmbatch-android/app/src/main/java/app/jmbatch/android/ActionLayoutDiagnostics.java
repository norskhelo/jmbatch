package app.jmbatch.android;

import android.content.Context;
import android.content.res.Configuration;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.view.ContextThemeWrapper;
import android.view.View;
import android.widget.LinearLayout;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;

/** Actual Android text measurement, invoked by the existing on-device self-test. */
final class ActionLayoutDiagnostics {
    static int run(Context context) throws Exception {
        if(Looper.myLooper()==Looper.getMainLooper())return checkFonts(context);
        FutureTask<Integer> task=new FutureTask<>(()->checkFonts(context));
        new Handler(Looper.getMainLooper()).post(task);
        return task.get(30,TimeUnit.SECONDS);
    }

    private static int checkFonts(Context base) {
        int scenarios=0;
        for(float scale:new float[]{1,1.3f,1.5f,2}) {
            Configuration config=new Configuration(base.getResources().getConfiguration());config.fontScale=scale;
            Context context=new ContextThemeWrapper(base.createConfigurationContext(config),R.style.AppTheme);
            float density=context.getResources().getDisplayMetrics().density;
            for(Typeface font:new Typeface[]{null,Typeface.SERIF,Typeface.MONOSPACE,Typeface.DEFAULT_BOLD})
            for(int widthDp:new int[]{240,320,360,640}) {
                String[] labels={"返回","第 151 章","★ 已收藏","模式：左右"};
                ActionButton[] buttons=new ActionButton[labels.length];int[] clicks={0};
                for(int i=0;i<labels.length;i++) {
                    ActionButton b=buttons[i]=new ActionButton(context);b.setText(labels[i]);b.setTextSize(12);
                    if(font!=null)b.setTypeface(font);
                    b.setOnClickListener(v->clicks[0]++);
                }
                ActionRow row=new ActionRow(context,buttons);int width=Math.round(widthDp*density);
                verify(row,width);
                buttons[1].setText("第 123456 章 · 长章节操作文字");verify(row,width);
                buttons[2].setVisibility(View.GONE);verify(row,width);
                buttons[2].setVisibility(View.VISIBLE);row.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);verify(row,width);
                for(ActionButton button:buttons)button.performClick();require(clicks[0]==buttons.length,"按钮回调");
                // Use real LinearLayout weight measurement to catch a zero-sized content area.
                LinearLayout body=new LinearLayout(context);body.setOrientation(LinearLayout.VERTICAL);
                body.addView(new ControlScroll(context,row));
                View content=new View(context);body.addView(content,new LinearLayout.LayoutParams(-1,0,1));
                body.addView(new ControlScroll(context,new ActionRow(context,new ActionButton(context))));
                int height=Math.round(240*density);
                body.measure(exact(width),exact(height));body.layout(0,0,width,height);
                require(content.getHeight()>height/3,"大字号保留内容区域");
                scenarios++;
            }
        }
        return scenarios;
    }

    private static int exact(int size){return View.MeasureSpec.makeMeasureSpec(size,View.MeasureSpec.EXACTLY);}
    private static void verify(ActionRow row,int width) {
        row.measure(exact(width),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));
        row.layout(0,0,width,row.getMeasuredHeight());
        for(int i=0;i<row.getChildCount();i++) {
            ActionButton b=(ActionButton)row.getChildAt(i);if(b.getVisibility()==View.GONE)continue;
            require(b.getLeft()>=0&&b.getRight()<=width&&b.getBottom()<=row.getHeight(),"按钮边界");
            android.text.Layout text=b.getLayout();require(text!=null,"文字布局");
            require(text.getHeight()+b.getCompoundPaddingTop()+b.getCompoundPaddingBottom()<=b.getHeight(),"字体高度完整");
            for(int line=0;line<text.getLineCount();line++) {
                require(text.getEllipsisCount(line)==0,"按钮标签不省略");
                require(text.getLineWidth(line)<=text.getWidth()+1,"按钮文字宽度完整");
            }
            for(int j=0;j<i;j++) {
                View a=row.getChildAt(j);if(a.getVisibility()==View.GONE)continue;
                require(a.getBottom()<=b.getTop()||b.getBottom()<=a.getTop()||a.getRight()<=b.getLeft()||b.getRight()<=a.getLeft(),"按钮互不遮挡");
                if(a.getTop()==b.getTop())require(a.getHeight()==b.getHeight(),"同排按钮等高");
            }
        }
    }
    private static void require(boolean condition,String name) {
        if(!condition)throw new IllegalStateException("字体布局自检失败："+name);
    }
}
