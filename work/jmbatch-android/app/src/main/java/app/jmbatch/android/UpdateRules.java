package app.jmbatch.android;

import java.net.URI;
import java.util.regex.*;

/** Pure-Java rules shared by the updater and offline tests. */
public final class UpdateRules {
    public static final String DEFAULT_REPOSITORY = "norskhelo/jmbatch";
    private UpdateRules() {}
    public static String initialRepository(String saved, boolean initialized) {
        String repo = repository(saved);
        return !initialized && repo.isEmpty() ? DEFAULT_REPOSITORY : repo;
    }
    public static String repository(String value) {
        String repo = value.trim();
        if (repo.isEmpty()) return "";
        if (repo.startsWith("https://github.com/")) repo = repo.substring(19).replaceAll("/+$", "");
        if (repo.endsWith(".git")) repo = repo.substring(0, repo.length()-4);
        if (!repo.matches("[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}") || repo.endsWith("/.") || repo.endsWith("/.."))
            throw new IllegalArgumentException("请填写公开 GitHub 仓库：用户名/仓库名，或对应的 https://github.com/ 链接");
        return repo;
    }
    public static int compare(String first, String second) {
        if (!first.matches("[0-9]{1,6}\\.[0-9]{1,6}\\.[0-9]{1,6}") || !second.matches("[0-9]{1,6}\\.[0-9]{1,6}\\.[0-9]{1,6}")) throw new IllegalArgumentException("版本号无效");
        String[] a=first.split("\\."), b=second.split("\\.");
        for(int i=0;i<3;i++){int result=Integer.compare(Integer.parseInt(a[i]),Integer.parseInt(b[i]));if(result!=0)return result;}
        return 0;
    }
    public static String assetVersion(String name) {
        Matcher match=Pattern.compile("JMBatch-([0-9]{1,6}\\.[0-9]{1,6}\\.[0-9]{1,6})-Android\\.apk").matcher(name);
        return match.matches()?match.group(1):null;
    }
    public static String announcement(String savedRepo,String repo,String savedVersion,String current,String notes,String local){
        try{
            if(savedRepo.equals(repo)&&compare(savedVersion,current)>=0&&notes!=null&&!notes.trim().isEmpty()&&!notes.equals("发布者未填写更新日志。"))
                return (compare(savedVersion,current)>0?"旧缓存仅包含最新版日志；请检查更新以获取完整升级日志。\n\n":"")+
                    "版本 "+savedVersion+" 更新公告\n\n"+notes;
        }catch(IllegalArgumentException ignored){}
        return local;
    }
    public static boolean validUrl(String value, String repo, String name) {
        try {
            URI uri = new URI(value);
            String path=uri.getPath(), prefix="/"+repo+"/releases/download/";
            if (!"https".equals(uri.getScheme()) || !"github.com".equals(uri.getRawAuthority()) || uri.getQuery()!=null || uri.getFragment()!=null || path==null || !path.regionMatches(true,0,prefix,0,prefix.length()) || !path.endsWith("/"+name)) return false;
            for(String part:path.split("/")) if(part.equals(".")||part.equals(".."))return false;
            return true;
        }catch(Exception error){return false;}
    }
}
