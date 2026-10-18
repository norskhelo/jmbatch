"""Exercise production focus lifecycle on host doubles; not an Android IME test."""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
stubs = {
    'android/os/IBinder.java': 'package android.os;public interface IBinder {}',
    'android/content/Context.java': '''package android.content;
public class Context {public static final String INPUT_METHOD_SERVICE="input";
public android.view.inputmethod.InputMethodManager ime=new android.view.inputmethod.InputMethodManager();
public Object getSystemService(String name){return ime;}}''',
    'android/view/View.java': '''package android.view;
import android.content.Context;import android.os.IBinder;
public class View {protected final Context context;public View parent,focused;public IBinder token;
public boolean touchFocusable,editor;public String text="";public int selection;
public View(Context c){context=c;}public Context getContext(){return context;}
public View root(){return parent==null?this:parent.root();}
public View findFocus(){return root().focused;}public boolean requestFocus(){root().focused=this;return true;}
public IBinder getWindowToken(){return root().token;}public boolean onCheckIsTextEditor(){return editor;}
public void setFocusableInTouchMode(boolean value){touchFocusable=value;}
public void onWindowFocusChanged(boolean focused){}}''',
    'android/widget/FrameLayout.java': '''package android.widget;
import android.view.View;import android.content.Context;
public class FrameLayout extends View {public static final int FOCUS_BEFORE_DESCENDANTS=131072;
public int order;public FrameLayout(Context c){super(c);}public void addView(View v){v.parent=this;}
public void setDescendantFocusability(int value){order=value;}}''',
    'android/view/inputmethod/InputMethodManager.java': '''package android.view.inputmethod;
import android.os.IBinder;public class InputMethodManager {public int hides;public boolean visible;
public IBinder activeToken,lastToken;public int flags=-1;
public void show(IBinder token){activeToken=token;visible=true;}
public boolean hideSoftInputFromWindow(IBinder token,int flags){hides++;lastToken=token;this.flags=flags;
if(token==activeToken){visible=false;return true;}return false;}}''',
    'InputFocusTest.java': '''import app.jmbatch.android.InputFocusLayout;
import android.content.Context;import android.os.IBinder;import android.view.View;
import android.widget.FrameLayout;import android.view.inputmethod.InputMethodManager;
public class InputFocusTest {
static int checks;static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
public static void main(String[] args){
Context c=new Context();InputMethodManager ime=c.ime;InputFocusLayout page=new InputFocusLayout(c);
View editor=new View(c);editor.editor=true;editor.text="123456 123460-123465";editor.selection=7;page.addView(editor);
check(page.touchFocusable&&page.order==FrameLayout.FOCUS_BEFORE_DESCENDANTS,"non-editor focus destination");
page.requestFocus();check(page.findFocus()==page,"initial root focus");
IBinder token=new IBinder(){};page.token=token;editor.requestFocus();ime.show(token);
// The old activity did not perform any lifecycle reset: a foreground return kept the editor.
page.onWindowFocusChanged(false);page.onWindowFocusChanged(true);
check(page.findFocus()==editor&&ime.visible,"ordinary focus changes leave active editing alone");
page.finishEditing();check(page.findFocus()==page,"pause transfers editor focus");
check(!ime.visible&&ime.lastToken==token&&ime.flags==0,"pause hides only main-window keyboard");
check(editor.text.equals("123456 123460-123465")&&editor.selection==7,"draft and selection not rewritten");
page.prepareForResume();editor.requestFocus();ime.show(token);page.onWindowFocusChanged(false);
check(page.findFocus()==editor&&ime.visible,"no consumption on window focus loss");
page.onWindowFocusChanged(true);check(page.findFocus()==page&&!ime.visible,"restored editor cleared once on return");
editor.requestFocus();ime.show(token);int hides=ime.hides;
page.onWindowFocusChanged(true);check(page.findFocus()==editor&&ime.visible&&ime.hides==hides,"new user input not dismissed by duplicate callback");
page.onWindowFocusChanged(false);page.onWindowFocusChanged(true);
check(page.findFocus()==editor&&ime.visible&&ime.hides==hides,"transient focus round trip does not reset user input");
for(int i=0;i<3;i++){
 editor.requestFocus();ime.show(token);page.finishEditing();page.prepareForResume();page.onWindowFocusChanged(true);
 check(page.findFocus()==page&&!ime.visible,"repeat background return "+i);
 editor.requestFocus();ime.show(token);check(page.findFocus()==editor&&ime.visible,"user can edit again "+i);
}
// The first resume can precede attachment. No null token is sent, then retry with a valid token.
page.token=null;hides=ime.hides;page.prepareForResume();
check(ime.hides==hides&&page.findFocus()==page,"unattached lifecycle safe");
page.token=token;ime.show(token);page.onWindowFocusChanged(true);
check(!ime.visible&&ime.hides==hides+1,"retry once after attachment and focus");
View button=new View(c);page.addView(button);button.requestFocus();page.finishEditing();
check(page.findFocus()==button,"non-editor keyboard focus preserved");
IBinder dialogToken=new IBinder(){};ime.show(dialogToken);editor.requestFocus();page.finishEditing();
check(ime.visible&&ime.activeToken==dialogToken&&ime.lastToken==token,"does not target dialog keyboard");
c.ime=null;editor.requestFocus();page.prepareForResume();page.onWindowFocusChanged(true);
check(page.findFocus()==page,"missing IME service safe");
check(editor.text.equals("123456 123460-123465")&&editor.selection==7,"draft survives all lifecycle cycles");
System.out.println("InputFocusTest: "+checks+" checks passed (host lifecycle doubles, not device IME)");
}}''',
}
for name, text in stubs.items():
    path = out/name; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
jdk = Path(sys.argv[1])/'bin'
classes = out/'classes'; classes.mkdir(exist_ok=True)
subprocess.run([str(jdk/'javac.exe'), '-encoding', 'UTF-8', '-d', str(classes),
                *[str(out/name) for name in stubs],
                str(root/'app/src/main/java/app/jmbatch/android/InputFocusLayout.java')], check=True)
subprocess.run([str(jdk/'java.exe'), '-cp', str(classes), 'InputFocusTest'], check=True)
# Check the actual integration points alongside behavior tests above.
ns = '{http://schemas.android.com/apk/res/android}'
manifest = ET.parse(root/'app/src/main/AndroidManifest.xml')
activity = next(a for a in manifest.findall('application/activity') if a.get(ns+'name')=='.MainActivity')
assert set(activity.get(ns+'windowSoftInputMode').split('|')) == {'stateAlwaysHidden','adjustResize'}
source = (root/'app/src/main/java/app/jmbatch/android/MainActivity.java').read_text(encoding='utf-8')
assert 'setContentView(inputFocus);inputFocus.requestFocus();' in source
assert 'inputFocus.prepareForResume()' in next(line for line in source.splitlines() if 'protected void onResume()' in line)
assert 'inputFocus.finishEditing()' in next(line for line in source.splitlines() if 'protected void onPause()' in line)
assert 'ids.setText("");inputFocus.finishEditing();' in source
assert 'rangeLast.setText("");inputFocus.finishEditing();' in source
print('Input focus integration: manifest, root, resume/pause and both submit actions verified')
