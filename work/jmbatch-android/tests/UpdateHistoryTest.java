import app.jmbatch.android.UpdateHistory;
import app.jmbatch.android.UpdateRules;
import java.io.IOException;
import java.util.*;

public class UpdateHistoryTest {
    static int checks;
    static final String REPO="owner/app";
    static void check(boolean value,String label){if(!value)throw new AssertionError(label);checks++;}
    static UpdateHistory.Entry entry(String version,String notes,String date){
        String name="JMBatch-"+version+"-Android.apk";
        return UpdateHistory.candidate(REPO,name,"https://github.com/"+REPO+"/releases/download/v"+version+"/"+name,
            "uploaded",100,false,false,notes,date);
    }
    static String render(UpdateHistory.Selection selection,String current){
        return UpdateHistory.announcement(REPO,REPO,selection.fromVersion,selection.latest.version,current,selection.history,"local");
    }
    public static void main(String[] args)throws Exception{
        String longNotes=new String(new char[9001]).replace('\0','长')+"完整结尾";
        List<UpdateHistory.Entry> entries=Arrays.asList(entry("0.3.11",longNotes,"2"),entry("0.3.8","current","1"),
            entry("0.3.10","ten","1"),entry("0.3.9","nine","1"),entry("0.3.7","old","1"));
        UpdateHistory.Selection selected=UpdateHistory.select(entries,"0.3.8");
        check(selected.latest.version.equals("0.3.11"),"numeric latest");
        check(selected.history.size()==3,"exclude installed and older versions");
        check(selected.history.get(0).version.equals("0.3.9")&&selected.history.get(1).version.equals("0.3.10"),"ascending versions");
        String text=render(selected,"0.3.8");
        check(text.contains(longNotes)&&text.endsWith("完整结尾"),"untruncated long notes");
        check(text.indexOf("nine")<text.indexOf("ten")&&text.indexOf("ten")<text.indexOf(longNotes),"rendered order");
        check(!text.contains("current")&&!text.contains("old"),"no installed release body");
        check(!render(selected,"0.3.9").contains("nine")&&render(selected,"0.3.9").contains("ten"),"rebase offline cache after upgrade");
        check(render(selected,"0.3.11").equals("版本 0.3.11 更新公告\n\n"+longNotes),"same version full bulletin");
        check(render(selected,"0.3.12").equals("local"),"newer local fallback");
        check(render(selected,"0.3.7").equals("local"),"cache does not cover older install");
        check(UpdateHistory.announcement(REPO,"other/app","0.3.8","0.3.11","0.3.8",selected.history,"local").equals("local"),"repository isolation");
        List<List<UpdateHistory.Entry>> invalid=Arrays.asList(Collections.emptyList(),
            Arrays.asList(entries.get(0),entries.get(2)),Collections.singletonList(entries.get(2)));
        for(List<UpdateHistory.Entry> history:invalid)
            check(UpdateHistory.announcement(REPO,REPO,"0.3.8","0.3.11","0.3.8",history,"local").equals("local"),"invalid or incomplete cache");
        for(List<UpdateHistory.Entry> duplicate:Arrays.asList(
                Arrays.asList(entry("0.3.9","new","2"),entry("0.3.9","old","1")),
                Arrays.asList(entry("0.3.9","old","1"),entry("0.3.9","new","2"))))
            check(UpdateHistory.select(duplicate,"0.3.8").history.get(0).notes.equals("new"),"deduplicate by publication date");
        check(render(UpdateHistory.select(Collections.singletonList(entry("0.3.9",null,"1")),"0.3.8"),"0.3.8").contains(UpdateHistory.MISSING),"missing notes visible");
        check(render(UpdateHistory.select(Collections.singletonList(entry("0.3.8"," ","1")),"0.3.8"),"0.3.8").equals("local"),"missing same-version body uses local");
        check(UpdateHistory.select(entries,"0.4.0")==null,"no downgrade");
        String name="JMBatch-0.3.9-Android.apk",url="https://github.com/owner/app/releases/download/v/"+name;
        check(UpdateHistory.candidate(REPO,name,url,"uploaded",10,true,false,"x","")==null,"draft excluded");
        check(UpdateHistory.candidate(REPO,name,url,"uploaded",10,false,true,"x","")==null,"prerelease excluded");
        check(UpdateHistory.candidate(REPO,name,url,"new",10,false,false,"x","")==null,"unfinished asset excluded");
        check(UpdateHistory.candidate(REPO,name,url,"uploaded",0,false,false,"x","")==null,"empty asset excluded");
        check(UpdateHistory.candidate(REPO,"JMBatch-0.3.9-Windows-x64.zip",url,"uploaded",10,false,false,"x","")==null,"other platform excluded");
        check(UpdateHistory.candidate(REPO,name,url.replace("owner/app","foreign/app"),"uploaded",10,false,false,"x","")==null,"foreign URL excluded");
        List<UpdateHistory.Entry> many=new ArrayList<>();
        for(int i=1;i<=30;i++)many.add(entry("0.3."+i,"notes "+i,"1"));
        check(UpdateHistory.select(many,"0.3.0").history.size()==30,"no twenty-release cutoff");
        int[] pages={0};
        UpdateHistory.Selection paged=UpdateHistory.load(page->{
            pages[0]++;
            return page==1?new UpdateHistory.Page(100,Arrays.asList(entry("0.3.11","eleven","1"),entry("0.3.1","old","1"))):
                page==2?new UpdateHistory.Page(100,Arrays.asList(entry("0.3.10","ten","1"),entry("0.3.9","nine","1"))):
                new UpdateHistory.Page(0,Collections.emptyList());
        },"0.3.8");
        check(pages[0]==3&&paged.history.size()==3,"read all pages despite earlier old release");
        check(paged.history.get(0).version.equals("0.3.9"),"intermediate release on later page");
        try{
            UpdateHistory.load(page->{if(page==2)throw new IOException("offline");return new UpdateHistory.Page(100,entries);},"0.3.8");
            throw new AssertionError("partial history returned");
        }catch(IOException expected){check(expected.getMessage().equals("offline"),"later page failure propagated");}
        pages[0]=0;
        try{
            UpdateHistory.load(page->{pages[0]++;return new UpdateHistory.Page(100,entries);},"0.3.8");
            throw new AssertionError("page cap returned partial history");
        }catch(IOException expected){check(pages[0]==UpdateHistory.MAX_PAGES,"bounded pagination fails closed");}
        check(UpdateRules.announcement(REPO,REPO,"0.3.11","0.3.8",longNotes,"local").contains("旧缓存仅包含最新版"),"legacy cache marked incomplete");
        check(UpdateRules.announcement(REPO,REPO,"0.3.11","0.3.8",longNotes,"local").endsWith(longNotes),"legacy notes untruncated");
        check(UpdateHistory.baseline("","","","0.3.8","0.3.11",REPO).equals("0.3.8"),"migrate old seen marker");
        check(UpdateHistory.baseline(REPO,"0.3.11","0.3.8","0.3.11","0.3.11",REPO).equals("0.3.8"),"restart retains baseline");
        check(UpdateHistory.baseline(REPO,"0.3.11","0.3.8","0.3.11","0.3.12",REPO).equals("0.3.11"),"next upgrade starts at previous installed version");
        check(UpdateHistory.baseline(REPO,"0.3.11","0.3.8","0.3.11","0.3.10",REPO).equals("0.3.10"),"downgrade resets baseline");
        check(UpdateHistory.baseline(REPO,"0.3.11","0.3.8","0.3.11","0.3.11","other/app").equals("0.3.11"),"repo switch resets baseline");
        check(UpdateHistory.baseline("","","","","0.3.11",REPO).equals("0.3.11"),"fresh install has no invented upgrade");
        for(String invalidFrom:new String[]{"bad","9.0.0",null})
            check(UpdateHistory.baseline(REPO,"0.3.11",invalidFrom,"0.3.11","0.3.11",REPO).equals("0.3.11"),"invalid state fallback");
        String completed=UpdateHistory.announcement(REPO,REPO,"0.3.8","0.3.11","0.3.11",selected.history,"local","0.3.8");
        check(completed.contains("本次升级：0.3.8 → 0.3.11"),"completed upgrade title");
        check(completed.contains("nine")&&completed.contains("ten")&&completed.endsWith(longNotes),"all upgrade notes retained at latest");
        String mixed=UpdateHistory.announcement(REPO,REPO,"0.3.8","0.3.11","0.3.10",selected.history,"local","0.3.8");
        check(mixed.contains("可用更新：")&&mixed.indexOf("ten")<mixed.indexOf("可用更新：")&&mixed.indexOf(longNotes)>mixed.indexOf("可用更新："),"completed and future ranges separated");
        check(UpdateHistory.announcement(REPO,"other/app","0.3.8","0.3.11","0.3.11",selected.history,"local","0.3.8").contains("完整日志尚未获取"),"foreign cache not full upgrade");
        check(UpdateHistory.announcement(REPO,REPO,"0.3.10","0.3.11","0.3.11",Collections.singletonList(selected.latest),"local","0.3.8").contains("完整日志尚未获取"),"latest-only cache not full upgrade");
        List<UpdateHistory.Entry> missingCurrent=Arrays.asList(selected.history.get(0),selected.latest);
        check(UpdateHistory.announcement(REPO,REPO,"0.3.8","0.3.11","0.3.10",missingCurrent,"local","0.3.8").contains("完整日志尚未获取"),"missing current release detected");
        check(UpdateHistory.pendingAnnouncement("0.3.11","0.3.8","local").endsWith("local"),"local notes visible while pending");
        System.out.println("UpdateHistoryTest: "+checks+" checks passed");
    }
}
