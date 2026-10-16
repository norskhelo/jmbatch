package app.jmbatch.android;

import java.io.IOException;
import java.util.*;

/** Platform-specific, complete release history; independent of Android UI/JSON. */
public final class UpdateHistory {
    public static final int PAGE_SIZE=100, MAX_PAGES=10, MAX_BYTES=8*1024*1024;
    public static final String MISSING="发布者未填写更新日志。";
    private UpdateHistory() {}

    public static String baseline(String savedRepo,String installed,String from,String seen,String current,String repo){
        try{
            if(repo.equals(savedRepo)&&current.equals(installed)&&UpdateRules.compare(from,current)<=0)return from;
        }catch(IllegalArgumentException|NullPointerException ignored){}
        try{if(UpdateRules.compare(seen,current)>0)return current;}
        catch(IllegalArgumentException|NullPointerException ignored){}
        String previous=null;
        for(String candidate:new String[]{seen,repo.equals(savedRepo)?installed:null}){
            try{
                if(UpdateRules.compare(candidate,current)<0&&(previous==null||UpdateRules.compare(candidate,previous)>0))previous=candidate;
            }catch(IllegalArgumentException|NullPointerException ignored){}
        }
        return previous==null?current:previous;
    }

    public static String pendingAnnouncement(String current,String from,String local){
        try{
            if(UpdateRules.compare(from,current)<0)return "本次升级 "+from+" → "+current+
                " 的完整日志尚未获取，联网检查后补齐。\n\n本版更新日志\n\n"+local;
        }catch(IllegalArgumentException|NullPointerException ignored){}
        return local;
    }

    public static final class Entry {
        public final String version, url, name, notes, published;
        public Entry(String version,String url,String name,String notes,String published){
            this.version=version;this.url=url;this.name=name;this.notes=notes;this.published=published;
        }
    }
    public static Entry candidate(String repo,String name,String url,String state,long size,
                                  boolean draft,boolean prerelease,String notes,String published){
        String version=UpdateRules.assetVersion(name);
        if(draft||prerelease||version==null||!"uploaded".equals(state)||size<=0||!UpdateRules.validUrl(url,repo,name))return null;
        return new Entry(version,url,name,notes==null||notes.trim().isEmpty()?MISSING:notes,published==null?"":published);
    }
    public static final class Selection {
        public final String fromVersion;
        public final Entry latest;
        public final List<Entry> history;
        Selection(String fromVersion,Entry latest,List<Entry> history){
            this.fromVersion=fromVersion;this.latest=latest;this.history=history;
        }
    }
    public static Selection select(List<Entry> entries,String current){
        UpdateRules.compare(current,current);
        TreeMap<String,Entry> versions=new TreeMap<>(UpdateRules::compare);
        for(Entry entry:entries){
            if(entry==null||UpdateRules.compare(entry.version,current)<0)continue;
            Entry old=versions.get(entry.version);
            if(old==null||entry.published.compareTo(old.published)>0)versions.put(entry.version,entry);
        }
        if(versions.isEmpty())return null;
        Entry latest=versions.lastEntry().getValue();
        List<Entry> history=new ArrayList<>();
        for(Entry entry:versions.values())
            if(UpdateRules.compare(entry.version,current)>0||entry==latest)history.add(entry);
        return new Selection(current,latest,history);
    }
    public static final class Page {
        public final int releaseCount;
        public final List<Entry> entries;
        public Page(int releaseCount,List<Entry> entries){this.releaseCount=releaseCount;this.entries=entries;}
    }
    public interface PageSource { Page read(int page) throws Exception; }
    public static Selection load(PageSource source,String current)throws Exception{
        List<Entry> entries=new ArrayList<>();
        for(int page=1;page<=MAX_PAGES;page++){
            Page next=source.read(page);
            if(next.releaseCount<0||next.releaseCount>PAGE_SIZE)throw new IOException("无效的 GitHub 响应");
            entries.addAll(next.entries);
            if(next.releaseCount<PAGE_SIZE)return select(entries,current);
        }
        throw new IOException("完整更新日志超过读取页数上限");
    }
    public static String announcement(String savedRepo,String repo,String fromVersion,String latestVersion,
                                      String current,List<Entry> history,String local){
        try{
            if(!savedRepo.equals(repo)||UpdateRules.compare(latestVersion,current)<0||
               UpdateRules.compare(fromVersion,current)>0||history==null||history.isEmpty())return local;
            String previous=null;
            for(Entry entry:history){
                if(entry.notes==null||UpdateRules.compare(entry.version,fromVersion)<0||
                   UpdateRules.compare(entry.version,latestVersion)>0||
                   (previous!=null&&UpdateRules.compare(entry.version,previous)<=0))return local;
                previous=entry.version;
            }
            if(UpdateRules.compare(previous,latestVersion)!=0)return local;
            if(UpdateRules.compare(latestVersion,current)==0){
                String notes=history.get(history.size()-1).notes;
                return MISSING.equals(notes)?local:"版本 "+latestVersion+" 更新公告\n\n"+notes;
            }
            StringBuilder text=new StringBuilder("从当前版本 "+current+" → 最新版本 "+latestVersion+
                " 的全部更新（不含当前版，按版本升序）\n\n");
            boolean first=true;
            for(Entry entry:history)if(UpdateRules.compare(entry.version,current)>0){
                if(!first)text.append("\n\n────────\n\n");
                first=false;text.append("版本 ").append(entry.version).append("\n\n").append(entry.notes);
            }
            return text.toString();
        }catch(IllegalArgumentException|NullPointerException error){return local;}
    }

    public static String announcement(String savedRepo,String repo,String fromVersion,String latestVersion,
                                      String current,List<Entry> history,String local,String upgradeFrom){
        String fallback=pendingAnnouncement(current,upgradeFrom,local);
        if(fallback.equals(local))return announcement(savedRepo,repo,fromVersion,latestVersion,current,history,local);
        // Validate the complete cached range against the version installed before this upgrade.
        if(announcement(savedRepo,repo,fromVersion,latestVersion,upgradeFrom,history,null)==null)return fallback;
        List<Entry> completed=new ArrayList<>(),pending=new ArrayList<>();
        for(Entry entry:history){
            if(UpdateRules.compare(entry.version,current)>0)pending.add(entry);
            else if(UpdateRules.compare(entry.version,upgradeFrom)>0)completed.add(entry);
        }
        if(completed.isEmpty()||UpdateRules.compare(completed.get(completed.size()-1).version,current)!=0)return fallback;
        String text="本次升级："+upgradeFrom+" → "+current+" 的全部更新（按版本升序）\n\n"+sections(completed);
        if(!pending.isEmpty())text+="\n\n════════\n\n可用更新：当前版本 "+current+" → 最新版本 "+latestVersion+"\n\n"+sections(pending);
        return text;
    }
    private static String sections(List<Entry> entries){
        StringBuilder text=new StringBuilder();
        for(Entry entry:entries){
            if(text.length()>0)text.append("\n\n────────\n\n");
            text.append("版本 ").append(entry.version).append("\n\n").append(entry.notes);
        }
        return text.toString();
    }
}
