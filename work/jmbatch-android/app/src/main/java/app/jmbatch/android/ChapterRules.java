package app.jmbatch.android;

import java.util.*;

/** Choices keep original chapter numbers so existing cached pages remain valid. */
public final class ChapterRules {
    public static final class Chapter {
        public final String id,title;
        public final int number;
        public Chapter(String id,int number,String title){
            if(!id.matches("[0-9]{1,10}")||number<1)throw new IllegalArgumentException("章节编号无效");
            this.id=id;this.number=number;this.title=title;
        }
    }
    public static final class ChoiceRequired extends Exception {
        public final List<Chapter> chapters;
        ChoiceRequired(List<Chapter> chapters){this.chapters=chapters;}
    }
    public static List<Chapter> resolve(List<Chapter> catalog,List<Chapter> saved,boolean all)throws ChoiceRequired {
        if(catalog.isEmpty())throw new IllegalArgumentException("没有可下载的章节");
        Set<String> available=new HashSet<>();
        for(Chapter c:catalog)if(!available.add(c.id))throw new IllegalArgumentException("章节编号重复，请重新获取章节");
        if(!saved.isEmpty()){
            for(Chapter c:saved)if(!available.contains(c.id))throw new IllegalArgumentException("已选章节已从服务端移除，未改为下载其他章节");
            return saved;
        }
        if(catalog.size()>1&&!all)throw new ChoiceRequired(catalog);
        return catalog;
    }
    public static List<Chapter> select(List<Chapter> catalog,Set<String> ids){
        List<Chapter> result=new ArrayList<>();
        for(Chapter c:catalog)if(ids.contains(c.id))result.add(c);
        if(result.isEmpty()||result.size()!=ids.size())throw new IllegalArgumentException("请至少选择一个有效章节");
        return Collections.unmodifiableList(result);
    }
}
