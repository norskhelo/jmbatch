package app.jmbatch.android;

import android.content.Context;
import android.view.View;
import android.widget.*;

/** Separate UI preferences; never copied into a running download's settings. */
public final class DisplayMode {
    private DisplayMode(){}
    public interface Changed {void changed(boolean tiles);}
    public static boolean tiles(Context context,String key){
        return context.getSharedPreferences("display",Context.MODE_PRIVATE).getBoolean(key,false);
    }
    public static RadioGroup selector(Context context,String key,Changed changed){
        RadioGroup group=new RadioGroup(context);group.setOrientation(LinearLayout.HORIZONTAL);
        for(boolean tile:new boolean[]{false,true}){
            RadioButton button=new RadioButton(context);button.setId(View.generateViewId());
            button.setText(tile?"平铺":"列表");button.setTag(tile);group.addView(button);
            if(tile==tiles(context,key))group.check(button.getId());
        }
        group.setContentDescription("显示方式");
        group.setOnCheckedChangeListener((g,id)->{
            boolean tile=(Boolean)g.findViewById(id).getTag();
            context.getSharedPreferences("display",Context.MODE_PRIVATE).edit().putBoolean(key,tile).apply();
            changed.changed(tile);
        });
        return group;
    }
    public static int columns(int width,int minimum,int gap,boolean tiles){
        return tiles?Math.max(1,(Math.max(0,width)+gap)/(Math.max(1,minimum)+gap)):1;
    }
}
