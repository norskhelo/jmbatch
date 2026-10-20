package app.jmbatch.android;

import java.util.*;
import org.json.*;

public final class ChapterSelection {
    public static List<ChapterRules.Chapter> catalog(JSONObject album,String albumId)throws JSONException {
        JSONArray series=album.optJSONArray("series");List<JSONObject> chapters=new ArrayList<>();
        if(series!=null)for(int i=0;i<series.length();i++)chapters.add(series.getJSONObject(i));
        if(chapters.isEmpty())chapters.add(new JSONObject().put("id",albumId).put("sort",1));
        chapters.sort(Comparator.comparingInt(item->item.optInt("sort",1)));
        List<ChapterRules.Chapter> result=new ArrayList<>();Set<String> seen=new HashSet<>();
        for(JSONObject chapter:chapters){
            String id=chapter.getString("id");
            if(!seen.add(id))throw new IllegalArgumentException("章节编号重复，请重新获取章节");
            result.add(new ChapterRules.Chapter(id,result.size()+1,chapter.optString("name","第 "+(result.size()+1)+" 章")));
        }
        return result;
    }
    public static List<ChapterRules.Chapter> read(JSONArray array)throws JSONException {
        List<ChapterRules.Chapter> result=new ArrayList<>();
        if(array!=null)for(int i=0;i<array.length();i++){
            JSONObject item=array.getJSONObject(i);
            result.add(new ChapterRules.Chapter(item.getString("id"),item.getInt("number"),item.optString("title")));
        }
        return Collections.unmodifiableList(result);
    }
    public static JSONArray json(List<ChapterRules.Chapter> chapters)throws JSONException {
        JSONArray result=new JSONArray();
        for(ChapterRules.Chapter c:chapters)result.put(new JSONObject().put("id",c.id).put("number",c.number).put("title",c.title));
        return result;
    }
}
