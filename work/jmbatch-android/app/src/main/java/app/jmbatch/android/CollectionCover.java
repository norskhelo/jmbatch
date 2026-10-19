package app.jmbatch.android;

import android.content.Context;
import android.graphics.*;
import java.util.List;

/** Bounded four-book local preview; called on the existing cover worker. */
final class CollectionCover {
    static Bitmap load(Context context,List<LibraryStore.Entry> entries){
        Bitmap result=Bitmap.createBitmap(144,192,Bitmap.Config.ARGB_8888);
        Canvas canvas=new Canvas(result);canvas.drawColor(Color.rgb(232,237,241));
        Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
        paint.setColor(Color.rgb(217,230,239));canvas.drawRoundRect(4,4,140,188,10,10,paint);
        paint.setColor(Color.rgb(141,164,181));canvas.drawRect(12,12,68,24,paint);
        for(int i=0;i<Math.min(4,entries.size());i++){
            int x=12+(i%2)*64,y=30+(i/2)*76;paint.setColor(Color.rgb(245,247,250));canvas.drawRect(x,y,x+56,y+70,paint);
            Bitmap image=LibraryCover.load(context,entries.get(i));
            if(image!=null){float scale=Math.min(56f/image.getWidth(),70f/image.getHeight()),w=image.getWidth()*scale,h=image.getHeight()*scale;
                canvas.drawBitmap(image,null,new RectF(x+(56-w)/2,y+(70-h)/2,x+(56+w)/2,y+(70+h)/2),paint);}
        }
        return result;
    }
}
