package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.*;
import android.os.*;
import android.view.*;
import android.widget.*;

/** Shared visual vocabulary for the October 2026 redesign. */
public final class Ui {
    private static final class Modal extends AlertDialog {
        Runnable cleanup;
        Modal(Activity activity){super(activity);}
        @Override protected void onStop(){try{super.onStop();}finally{if(cleanup!=null){Runnable action=cleanup;cleanup=null;action.run();}}}
    }
    private static final java.util.WeakHashMap<Activity,Dialog> surfaces=new java.util.WeakHashMap<>();
    static void surface(Activity activity,Dialog dialog){surfaces.put(activity,dialog);dialog.setOnDismissListener(d->surfaces.remove(activity));}
    private static ViewGroup decor(Activity activity){Dialog dialog=surfaces.get(activity);return (ViewGroup)(dialog!=null&&dialog.isShowing()?dialog.getWindow():activity.getWindow()).getDecorView();}
    public static final int BG=Color.rgb(245,245,247), INK=Color.rgb(29,31,38), MUTED=Color.rgb(116,119,128),
        LINE=Color.rgb(218,220,225), ACCENT=Color.rgb(115,117,124), BLUE=Color.rgb(51,99,189);
    private Ui(){}
    public static int dp(Context c,int n){return Math.round(c.getResources().getDisplayMetrics().density*n);}
    public static GradientDrawable shape(Context c,int color,int radius,boolean border){
        GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(c,radius));if(border)d.setStroke(dp(c,1),LINE);return d;
    }
    public static LinearLayout column(Context c){LinearLayout v=new LinearLayout(c);v.setOrientation(LinearLayout.VERTICAL);return v;}
    public static TextView text(Context c,String value,int size){TextView v=new TextView(c);v.setText(value);v.setTextSize(size);v.setTextColor(INK);v.setLineSpacing(dp(c,2),1);return v;}
    public static TextView heading(Context c,String value){TextView v=text(c,value,21);v.setTypeface(null,Typeface.BOLD);v.setPadding(0,dp(c,10),0,dp(c,12));return v;}
    public static Button button(Context c,String title,Runnable action){Button b=new ActionButton(c);b.setText(title);b.setTextSize(14);b.setOnClickListener(v->action.run());return b;}
    public static void primary(Button b){b.setTextColor(Color.WHITE);b.setBackgroundTintList(null);b.setBackground(shape(b.getContext(),ACCENT,9,false));}
    public static EditText input(Context c,String hint,boolean number){EditText e=new EditText(c);e.setTextColor(INK);e.setTextSize(14);e.setHintTextColor(MUTED);e.setHint(hint);e.setPadding(dp(c,12),dp(c,12),dp(c,12),dp(c,12));e.setBackground(shape(c,BG,8,true));e.setSingleLine(number);if(number)e.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);return e;}
    public static void gap(LinearLayout parent,int height){View gap=new View(parent.getContext());parent.addView(gap,new LinearLayout.LayoutParams(1,dp(parent.getContext(),height)));}
    public static LinearLayout pair(Context c,View...views){LinearLayout row=new LinearLayout(c);row.setGravity(Gravity.CENTER_VERTICAL);for(View v:views){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1);if(row.getChildCount()>0)p.leftMargin=dp(c,8);row.addView(v,p);}return row;}
    public static AlertDialog modal(Activity a,View content,boolean blur){
        LinearLayout panel=column(a);int p=dp(a,20);panel.setPadding(p,p,p,p);panel.setBackground(shape(a,Color.WHITE,16,false));panel.addView(content);
        Modal d=new Modal(a);d.setView(panel);d.setOnShowListener(x->{
            d.getWindow().setBackgroundDrawableResource(android.R.color.transparent);
            int width=Math.min(dp(a,480),a.getResources().getDisplayMetrics().widthPixels-dp(a,36));d.getWindow().setLayout(width,-2);
        });
        if(blur){ViewGroup decor=decor(a);
            if(decor.getWidth()>0&&decor.getHeight()>0){
                Bitmap bitmap=Bitmap.createBitmap(Math.max(1,decor.getWidth()/14),Math.max(1,decor.getHeight()/14),Bitmap.Config.ARGB_8888);
                Canvas canvas=new Canvas(bitmap);canvas.scale(bitmap.getWidth()/(float)decor.getWidth(),bitmap.getHeight()/(float)decor.getHeight());decor.draw(canvas);
                ImageView cover=new ImageView(a);cover.setScaleType(ImageView.ScaleType.FIT_XY);cover.setImageBitmap(bitmap);cover.setColorFilter(Color.argb(65,100,100,110),PorterDuff.Mode.SRC_ATOP);decor.addView(cover,new ViewGroup.LayoutParams(-1,-1));
                d.cleanup=()->{decor.removeView(cover);cover.setImageDrawable(null);bitmap.recycle();};
            }
        }
        return d;
    }
    public static AlertDialog confirm(Activity a,String title,Runnable yes){return confirm(a,title,null,yes);}
    public static AlertDialog confirm(Activity a,String title,View extra,Runnable yes){
        LinearLayout body=column(a);TextView label=text(a,title,17);label.setGravity(Gravity.CENTER);body.addView(label);gap(body,18);if(extra!=null){body.addView(extra);gap(body,14);}
        AlertDialog dialog=modal(a,body,true);Button accept=button(a,"确认",()->{dialog.dismiss();yes.run();});primary(accept);
        body.addView(pair(a,accept,button(a,"取消",dialog::dismiss)));dialog.show();return dialog;
    }
    public static void skin(AlertDialog dialog){
        if(dialog.getWindow()!=null)dialog.getWindow().setBackgroundDrawable(shape(dialog.getContext(),Color.WHITE,16,true));
        for(int id:new int[]{-1,-2,-3}){Button b=dialog.getButton(id);if(b!=null){b.setTextColor(INK);b.setAllCaps(false);}}
    }
    public static void notice(Activity a,String message){
        ViewGroup decor=decor(a);TextView label=text(a,message,14);label.setGravity(Gravity.CENTER);int p=dp(a,14);label.setPadding(p,p,p,p);label.setBackground(shape(a,Color.WHITE,12,true));label.setElevation(dp(a,6));
        FrameLayout.LayoutParams params=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL);params.topMargin=dp(a,32);params.leftMargin=params.rightMargin=dp(a,24);decor.addView(label,params);
        label.setAlpha(0);label.animate().alpha(1).setDuration(160).start();new Handler(Looper.getMainLooper()).postDelayed(()->decor.removeView(label),3000);
    }
    public static void sheet(View view){view.setVisibility(View.VISIBLE);view.post(()->{view.setTranslationY(view.getHeight());view.animate().translationY(0).setDuration(220).start();});}
}
