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
    private static final class CompactInput extends EditText {
        CompactInput(Context context){super(context);}
        @Override protected void onMeasure(int width,int height){
            // A long hint must not expand an empty field; entered text can wrap freely.
            int lines=length()==0?1:Integer.MAX_VALUE;
            if(getMaxLines()!=lines)setMaxLines(lines);
            android.text.TextUtils.TruncateAt ellipsis=length()==0?android.text.TextUtils.TruncateAt.END:null;
            if(getEllipsize()!=ellipsis)setEllipsize(ellipsis);
            compact(this);
            super.onMeasure(width,height);
            if(compact(this))super.onMeasure(width,height);
            // Older Android releases include the full hint in the desired height,
            // even after text is entered. Size from the actual text layout instead.
            int content=getLayout().getHeight()+getPaddingTop()+getPaddingBottom();
            setMeasuredDimension(getMeasuredWidth(),resolveSize(Math.max(controlHeight(this),content),height));
        }
    }
    private static final class Modal extends AlertDialog {
        Runnable cleanup;
        Modal(Activity activity){super(activity);}
        @Override protected void onStart(){
            super.onStart();
            // Dialog.show calls onStart before attaching the window. An OnShowListener
            // runs later and can resize/recenter an already visible first frame.
            Window window=getWindow();
            window.setBackgroundDrawableResource(android.R.color.transparent);window.setDimAmount(.22f);
            int width=Math.min(dp(getContext(),480),getContext().getResources().getDisplayMetrics().widthPixels-dp(getContext(),36));
            window.setLayout(width,WindowManager.LayoutParams.WRAP_CONTENT);
        }
        @Override protected void onStop(){try{super.onStop();}finally{if(cleanup!=null){Runnable action=cleanup;cleanup=null;action.run();}}}
    }
    private static final java.util.WeakHashMap<Activity,Dialog> surfaces=new java.util.WeakHashMap<>();
    static void surface(Activity activity,Dialog dialog){surfaces.put(activity,dialog);dialog.setOnDismissListener(d->surfaces.remove(activity));}
    static void surface(Activity activity,Dialog dialog,Runnable after){surfaces.put(activity,dialog);dialog.setOnDismissListener(d->{surfaces.remove(activity);after.run();});}
    private static ViewGroup decor(Activity activity){Dialog dialog=surfaces.get(activity);return (ViewGroup)(dialog!=null&&dialog.isShowing()?dialog.getWindow():activity.getWindow()).getDecorView();}
    public static final int BG=Color.rgb(245,245,247), INK=Color.rgb(29,31,38), MUTED=Color.rgb(116,119,128),
        LINE=Color.rgb(218,220,225), ACCENT=Color.rgb(115,117,124), BLUE=Color.rgb(51,99,189);
    public static final int ADD_ACTION_TEXT_SIZE=28;
    private Ui(){}
    public static int dp(Context c,int n){return Math.round(c.getResources().getDisplayMetrics().density*n);}
    private static int firstLineHeight(TextView view){return view.getLayout()==null?view.getLineHeight():view.getLayout().getLineBottom(0)-view.getLayout().getLineTop(0);}
    public static int controlHeight(TextView view){return controlHeight(view,2.25f);}
    public static int controlHeight(TextView view,float ratio){return Math.max((int)Math.ceil(view.getTextSize()*ratio),firstLineHeight(view)+2);}
    public static boolean compact(TextView view){
        view.setIncludeFontPadding(false);
        int height=controlHeight(view),extra=height-firstLineHeight(view),top=extra/2,bottom=extra-top;
        if(view.getMinHeight()!=height)view.setMinHeight(height);
        if(view.getMinimumHeight()!=height)view.setMinimumHeight(height);
        if(view.getPaddingTop()!=top||view.getPaddingBottom()!=bottom){view.setPadding(view.getPaddingLeft(),top,view.getPaddingRight(),bottom);return true;}
        return false;
    }
    public static GradientDrawable shape(Context c,int color,int radius,boolean border){
        GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(c,radius));if(border)d.setStroke(dp(c,1),LINE);return d;
    }
    public static GradientDrawable circle(int color){
        GradientDrawable d=new GradientDrawable();d.setShape(GradientDrawable.OVAL);d.setColor(color);return d;
    }
    public static LinearLayout column(Context c){LinearLayout v=new LinearLayout(c);v.setOrientation(LinearLayout.VERTICAL);return v;}
    public static TextView text(Context c,String value,int size){TextView v=new TextView(c);v.setText(value);v.setTextSize(size);v.setTextColor(INK);v.setLineSpacing(dp(c,2),1);return v;}
    public static void setText(TextView view,String value){if(!value.contentEquals(view.getText()))view.setText(value);}
    public static TextView heading(Context c,String value){TextView v=text(c,value,21);v.setTypeface(null,Typeface.BOLD);v.setPadding(0,dp(c,10),0,dp(c,12));return v;}
    public static Button square(Button button){((ActionButton)button).setIconOnly(true);return button;}
    public static void smallIconGlyph(Button button){
        android.text.SpannableString glyph=new android.text.SpannableString(button.getText());
        glyph.setSpan(new android.text.style.RelativeSizeSpan(.8f),0,glyph.length(),android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        button.setText(glyph);
    }
    public static Button button(Context c,String title,Runnable action){Button b=new ActionButton(c);b.setText(title);b.setOnClickListener(v->action.run());if(title.equals("←"))square(b);return b;}
    public static Button iconButton(Context c,String kind,String title,Runnable action){return iconButton(c,kind,title,16,action);}
    public static Button iconButton(Context c,String kind,String title,int textSize,Runnable action){Button b=button(c,title,action);b.setTextSize(textSize);b.setContentDescription(title.isEmpty()?"分享":title);b.setCompoundDrawablePadding(dp(c,6));android.text.SpannableString symbol=new android.text.SpannableString("\ufffc"+(title.isEmpty()?"":"  "+title));Drawable image=icon(c,kind);int size=Math.round(b.getTextSize());image.setBounds(0,0,size,size);symbol.setSpan(new android.text.style.ImageSpan(image,android.text.style.ImageSpan.ALIGN_BASELINE),0,1,android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);b.setText(symbol);if(title.isEmpty())square(b);return b;}
    public static Drawable icon(Context c,String kind){
        Drawable d=new Drawable(){
            final Paint p=new Paint(3);
            public void draw(Canvas original){Canvas canvas=original;canvas.save();canvas.translate(getBounds().left,getBounds().top);canvas.scale(getBounds().width()/24f,getBounds().height()/24f);p.setColor(INK);p.setStrokeWidth(1.6f);p.setStyle(Paint.Style.STROKE);p.setStrokeJoin(Paint.Join.ROUND);p.setStrokeCap(Paint.Cap.ROUND);Path path=new Path();
                if(kind.equals("trash")){path.moveTo(6,8);path.lineTo(7,21);path.lineTo(18,21);path.lineTo(19,8);path.moveTo(4,6);path.lineTo(21,6);path.moveTo(9,6);path.lineTo(9,3);path.lineTo(16,3);path.lineTo(16,6);path.moveTo(10,10);path.lineTo(10,18);path.moveTo(15,10);path.lineTo(15,18);}
                else if(kind.equals("folder")){path.moveTo(3,20);path.lineTo(3,6);path.lineTo(10,6);path.lineTo(12,9);path.lineTo(22,9);path.lineTo(22,20);path.close();path.moveTo(12,11);path.lineTo(12,18);path.moveTo(8.5f,14.5f);path.lineTo(15.5f,14.5f);}
                else{path.moveTo(6,11);path.lineTo(6,21);path.lineTo(19,21);path.lineTo(19,11);path.moveTo(12.5f,16);path.lineTo(12.5f,3);path.moveTo(8,8);path.lineTo(12.5f,3);path.lineTo(17,8);}
                canvas.drawPath(path,p);canvas.restore();
            }
            public void setAlpha(int alpha){p.setAlpha(alpha);}public void setColorFilter(ColorFilter filter){p.setColorFilter(filter);}public int getOpacity(){return PixelFormat.TRANSLUCENT;}
        };d.setBounds(0,0,dp(c,20),dp(c,20));return d;
    }
    public static void primary(Button b){b.setTextColor(Color.WHITE);b.setBackgroundTintList(null);b.setBackground(shape(b.getContext(),ACCENT,9,false));}
    public static EditText input(Context c,String hint,boolean number){EditText e=new CompactInput(c);e.setTextColor(INK);e.setTextSize(14);e.setHintTextColor(MUTED);e.setHint(hint);e.setPadding(dp(c,12),0,dp(c,12),0);e.setBackground(shape(c,BG,8,true));e.setSingleLine(number);if(number)e.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);return e;}
    public static void gap(LinearLayout parent,int height){View gap=new View(parent.getContext());parent.addView(gap,new LinearLayout.LayoutParams(1,dp(parent.getContext(),height)));}
    public static ActionRow pair(Context c,View...views){return new ActionRow(c,views);}
    public static AlertDialog modal(Activity a,View content,boolean blur){
        return modal(a,content,blur,20,20);
    }
    public static AlertDialog modal(Activity a,View content,boolean blur,int topPadding,int bottomPadding){
        LinearLayout panel=column(a);int p=dp(a,20);panel.setPadding(p,dp(a,topPadding),p,dp(a,bottomPadding));panel.setBackground(shape(a,Color.WHITE,16,false));panel.addView(content);
        Modal d=new Modal(a);d.setView(panel);
        if(blur){ViewGroup decor=decor(a);
            if(decor.getWidth()>0&&decor.getHeight()>0){
                Bitmap bitmap=blurred(decor);
                ImageView cover=new ImageView(a);cover.setScaleType(ImageView.ScaleType.FIT_XY);cover.setImageBitmap(bitmap);cover.setColorFilter(Color.argb(20,100,100,110),PorterDuff.Mode.SRC_ATOP);decor.addView(cover,new ViewGroup.LayoutParams(-1,-1));
                d.cleanup=()->{decor.removeView(cover);cover.setImageDrawable(null);bitmap.recycle();};
            }
        }
        return d;
    }
    static Bitmap blurred(View view){
        int w=Math.max(1,view.getWidth()/4),h=Math.max(1,view.getHeight()/4);Bitmap bitmap=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);canvas.drawColor(Color.WHITE);canvas.scale(w/(float)view.getWidth(),h/(float)view.getHeight());view.draw(canvas);
        int[] pixels=new int[w*h],temp=new int[w*h];bitmap.getPixels(pixels,0,w,0,0,w,h);
        for(int pass=0;pass<2;pass++){for(int y=0;y<h;y++)for(int x=0;x<w;x++){int r=0,g=0,b=0;for(int k=-2;k<=2;k++){int at=pass==0?y*w+Math.max(0,Math.min(w-1,x+k)):Math.max(0,Math.min(h-1,y+k))*w+x;int p=pixels[at];r+=(p>>16)&255;g+=(p>>8)&255;b+=p&255;}temp[y*w+x]=0xff000000|((r/5)<<16)|((g/5)<<8)|(b/5);}int[] swap=pixels;pixels=temp;temp=swap;}
        bitmap.setPixels(pixels,0,w,0,0,w,h);return bitmap;
    }
    public static AlertDialog confirm(Activity a,String title,Runnable yes){return confirm(a,title,null,yes);}
    public static AlertDialog confirm(Activity a,String title,View extra,Runnable yes){
        LinearLayout body=column(a);gap(body,12);TextView label=text(a,title,17);label.setGravity(Gravity.CENTER);body.addView(label);gap(body,24);if(extra!=null){body.addView(extra);gap(body,14);}
        AlertDialog dialog=modal(a,body,true);Button accept=button(a,"确认",()->{dialog.dismiss();yes.run();});primary(accept);
        body.addView(pair(a,accept,button(a,"取消",dialog::dismiss)));dialog.show();return dialog;
    }
    public static void skin(AlertDialog dialog){
        if(dialog.getWindow()!=null)dialog.getWindow().setBackgroundDrawable(shape(dialog.getContext(),Color.WHITE,16,true));
        for(int id:new int[]{-1,-2,-3}){Button b=dialog.getButton(id);if(b!=null){b.setTextColor(INK);b.setTextSize(16);b.setAllCaps(false);compact(b);ViewGroup.LayoutParams p=b.getLayoutParams();p.height=-2;b.setLayoutParams(p);}}
    }
    public static void notice(Activity a,String message){
        ViewGroup decor=decor(a);TextView label=text(a,message,14);label.setGravity(Gravity.CENTER);int p=dp(a,14);label.setPadding(p,p,p,p);label.setBackground(shape(a,Color.WHITE,12,true));label.setElevation(dp(a,6));
        FrameLayout.LayoutParams params=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL);params.topMargin=dp(a,32);params.leftMargin=params.rightMargin=dp(a,24);decor.addView(label,params);
        label.setAlpha(0);label.animate().alpha(1).setDuration(160).start();new Handler(Looper.getMainLooper()).postDelayed(()->decor.removeView(label),3000);
    }
    public static void sheet(View view){
        view.animate().cancel();view.setVisibility(View.VISIBLE);
        // Position the measured sheet before its first frame. Posting this work
        // lets the expanded menu flash in place before the slide begins.
        view.getViewTreeObserver().addOnPreDrawListener(new android.view.ViewTreeObserver.OnPreDrawListener(){
            public boolean onPreDraw(){
                view.getViewTreeObserver().removeOnPreDrawListener(this);
                if(view.getVisibility()==View.VISIBLE){view.setTranslationY(view.getHeight());view.animate().translationY(0).setDuration(220).start();}
                return true;
            }
        });
    }
}
