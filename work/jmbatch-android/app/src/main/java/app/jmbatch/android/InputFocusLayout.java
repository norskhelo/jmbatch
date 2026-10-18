package app.jmbatch.android;

import android.content.Context;
import android.os.IBinder;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.FrameLayout;

/** Non-scrolling focus destination for the main screen between editing sessions. */
public final class InputFocusLayout extends FrameLayout {
    private boolean resetOnWindowFocus;

    public InputFocusLayout(Context context) {
        super(context);
        setFocusableInTouchMode(true);
        setDescendantFocusability(FOCUS_BEFORE_DESCENDANTS);
    }

    public void prepareForResume() {
        // onResume can precede attachment/window focus. Retry once when ready,
        // without posting a delayed hide that could interrupt the next user tap.
        resetOnWindowFocus=true;
        finishEditing();
    }

    public void finishEditing() {
        View focused=findFocus();
        if(focused!=null && focused.onCheckIsTextEditor())requestFocus();
        // Moving focus alone does not close an already visible IME.
        IBinder token=getWindowToken();
        InputMethodManager input=(InputMethodManager)getContext().getSystemService(Context.INPUT_METHOD_SERVICE);
        if(token!=null && input!=null)input.hideSoftInputFromWindow(token,0);
    }

    @Override public void onWindowFocusChanged(boolean hasWindowFocus) {
        super.onWindowFocusChanged(hasWindowFocus);
        if(hasWindowFocus && resetOnWindowFocus) {
            resetOnWindowFocus=false;
            finishEditing();
        }
    }
}
