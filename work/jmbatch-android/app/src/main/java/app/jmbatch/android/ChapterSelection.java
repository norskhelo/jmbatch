package app.jmbatch.android;

import java.util.*;
import org.json.*;

public final class ChapterSelection {
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
