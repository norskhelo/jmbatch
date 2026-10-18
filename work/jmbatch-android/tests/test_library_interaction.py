"""Run the exact production library event handlers with host widget doubles.

Android owns long-press recognition and scroll cancellation; device gesture timing
is not simulated or claimed here. These checks cover handler state and wiring.
"""
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
source = (root/'app/src/main/java/app/jmbatch/android/LibraryScreen.java').read_text(encoding='utf-8')
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)

def method(name):
    match = re.search(r'    private [^\n{]+\b'+name+r'\([^\n{]*\)\{', source)
    assert match, name
    start = match.start(); end = match.end(); depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

methods = '\n'.join(method(name) for name in ('read', 'itemClick', 'itemLongClick', 'setBatchMode', 'counts', 'select', 'selection', 'acceptEntries'))
program = '''import java.util.*;
public class LibraryInteractionTest {
static class View {static final int VISIBLE=0,GONE=8;int visibility;boolean enabled=true;
void setVisibility(int v){visibility=v;}void setEnabled(boolean v){enabled=v;}boolean isEnabled(){return enabled;}}
static class TextView extends View {String text="";void setText(String s){text=s;}}
static class Button extends TextView {}
static class ListView extends View {static final int CHOICE_MODE_NONE=0,CHOICE_MODE_MULTIPLE=2;int mode;
Set<Integer> checked=new HashSet<>();void setChoiceMode(int n){mode=n;}void clearChoices(){checked.clear();}
void setItemChecked(int n,boolean v){if(mode==0)return;if(v)checked.add(n);else checked.remove(n);}}
static class Adapter {int changes;void notifyDataSetChanged(){changes++;}}
static class Dialog {boolean dismissed;void dismiss(){dismissed=true;}}
static class LibraryStore {static class Entry {String uri;Entry(String s){uri=s;}}}
static class ReaderActivity {static List<String> opened=new ArrayList<>();static void open(Object a,LibraryStore.Entry e){opened.add(e.uri);}}
Object activity=new Object();boolean busy,loading,batchMode;String report="";
Set<String> selected=new HashSet<>();List<LibraryStore.Entry> entries=new ArrayList<>();
ListView list=new ListView();Dialog dialog=new Dialog();Adapter adapter=new Adapter();
Button modeButton=new Button();TextView hint=new TextView(),status=new TextView();
View selectionControls=new View(),batchActions=new View();
List<Button> singleButtons=Arrays.asList(new Button()),batchButtons=Arrays.asList(new Button());
'''+methods+'''
static int checks;static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
LibraryInteractionTest(){entries.add(new LibraryStore.Entry("a"));entries.add(new LibraryStore.Entry("b"));entries.add(new LibraryStore.Entry("c"));setBatchMode(false);}
// ListView toggles its checked position before invoking OnItemClick in MULTIPLE mode.
void tap(int p){if(list.mode==2)list.setItemChecked(p,!list.checked.contains(p));itemClick(p);}
public static void main(String[] args){
LibraryInteractionTest f=new LibraryInteractionTest();
check(!f.batchMode&&f.list.mode==0,"normal browsing");
check(f.batchActions.visibility==8&&f.selectionControls.visibility==8,"normal tools hidden");
check(!f.status.text.contains("已选"),"no selection status in browsing");
f.tap(0);check(ReaderActivity.opened.equals(Arrays.asList("a"))&&f.dialog.dismissed,"tap opens reader");
check(f.selected.isEmpty()&&f.list.checked.isEmpty(),"tap does not select");
ReaderActivity.opened.clear();f=new LibraryInteractionTest();
check(f.itemLongClick(1),"long click consumed by list (no click on release)");
check(f.batchMode&&f.list.mode==2&&f.selected.equals(new HashSet<>(Arrays.asList("b"))),"long click enters and selects held book");
check(f.list.checked.equals(new HashSet<>(Arrays.asList(1))),"held row visibly checked");
check(f.batchActions.visibility==0&&f.selectionControls.visibility==0&&f.modeButton.text.equals("完成"),"batch tools visible");
check(f.singleButtons.get(0).enabled&&f.batchButtons.get(0).enabled,"single and batch actions enabled");
check(ReaderActivity.opened.isEmpty(),"hold never reads");
f.tap(0);check(f.selected.size()==2&&f.list.checked.size()==2,"tap toggles selection once after native toggle");
check(!f.singleButtons.get(0).enabled&&f.batchButtons.get(0).enabled,"multi select disables single actions");
f.tap(1);check(f.selected.equals(new HashSet<>(Arrays.asList("a")))&&f.list.checked.size()==1,"tap deselects");
f.itemLongClick(0);check(f.selected.size()==1,"repeated hold retains selection");
f.itemLongClick(2);check(f.selected.size()==2,"hold another adds without clearing");
f.select(0);check(f.selection().size()==3,"select all");f.select(1);check(f.selection().isEmpty(),"invert all");
check(!f.singleButtons.get(0).enabled&&!f.batchButtons.get(0).enabled,"empty batch disables actions");
f.select(0);f.acceptEntries(Arrays.asList(new LibraryStore.Entry("c"),new LibraryStore.Entry("a")));
check(f.selected.size()==2&&f.selection().size()==2&&f.list.checked.size()==2,"refresh removes deleted selection and remaps reordered rows");
f.select(2);check(f.selected.isEmpty()&&f.list.checked.isEmpty(),"clear selection");
f.itemLongClick(0);f.busy=true;f.itemClick(1);f.itemLongClick(1);f.select(0);f.setBatchMode(false);
check(f.batchMode&&f.selected.equals(new HashSet<>(Arrays.asList("c"))),"busy prevents reading, selection and exit");
f.busy=false;f.list.setEnabled(false);f.itemClick(1);f.itemLongClick(1);
check(f.selected.size()==1,"loading list ignores input");f.list.setEnabled(true);
f.loading=true;f.counts();f.select(0);f.setBatchMode(false);
check(f.batchMode&&f.selected.size()==1&&!f.batchButtons.get(0).enabled,"loading blocks batch buttons and selection");
f.acceptEntries(f.entries);check(!f.loading&&f.batchButtons.get(0).enabled,"load completion restores actions");
f.setBatchMode(false);check(f.selected.isEmpty()&&f.list.checked.isEmpty()&&f.list.mode==0,"done/back clears choices");
check(f.batchActions.visibility==8&&f.modeButton.text.equals("批量处理"),"done returns to browsing tools");
f.itemClick(-1);f.itemLongClick(99);check(ReaderActivity.opened.isEmpty(),"invalid/stale row ignored");
f.tap(1);check(ReaderActivity.opened.equals(Arrays.asList("a")),"tap reads again after exit");
f=new LibraryInteractionTest();f.setBatchMode(true);check(f.batchMode&&f.selected.isEmpty(),"accessible batch button starts empty");
f.acceptEntries(new ArrayList<>());f.select(0);f.itemLongClick(0);check(f.selected.isEmpty(),"empty library safe");
System.out.println("LibraryInteractionTest: "+checks+" checks passed (production handlers, host widgets)");
}}
'''
program_path=out/'LibraryInteractionTest.java';program_path.write_text(program,encoding='utf-8')
jdk=Path(sys.argv[1])/'bin'
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-d',str(out),str(program_path)],check=True)
subprocess.run([str(jdk/'java.exe'),'-cp',str(out),'LibraryInteractionTest'],check=True)
assert 'setOnItemClickListener((p,v,position,id)->itemClick(position))' in source
assert 'setOnItemLongClickListener((p,v,position,id)->itemLongClick(position))' in source
assert 'KeyEvent.KEYCODE_BACK&&batchMode&&!busy' in source
assert 'KeyEvent.ACTION_UP)setBatchMode(false)' in source
assert 'if(!filter.equals(nextFilter)){selected.clear();filter=nextFilter;}' in source
assert 'resetCovers();acceptEntries(result);' in source
assert 'else row.text.setCheckMarkDrawable(null)' in source
print('Library interaction listener, back, filter, refresh and recycled-row wiring verified')
