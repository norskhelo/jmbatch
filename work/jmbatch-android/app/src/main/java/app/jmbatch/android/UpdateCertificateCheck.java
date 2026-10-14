package app.jmbatch.android;

import java.util.Arrays;
import java.util.HashSet;

/** Certificate preflight only. Android always validates signatures on installation. */
public final class UpdateCertificateCheck {
    public interface Source { String[] read() throws Exception; }
    private static boolean usable(String[] values){
        if(values==null||values.length==0)return false;
        for(String value:values)if(value==null||value.isEmpty())return false;
        return true;
    }
    public static String[] read(Source modern,Source legacy){
        for(Source source:new Source[]{modern,legacy}){
            try{String[] values=source.read();if(usable(values))return values;}
            catch(Exception ignored){/* Some ROMs cannot expose certificates to an app. */}
        }
        return null;
    }
    /** false means unavailable, never a successful certificate comparison. */
    public static boolean matches(String[] installed,String[] candidate){
        if(!usable(installed)||!usable(candidate))return false;
        if(!new HashSet<>(Arrays.asList(installed)).equals(new HashSet<>(Arrays.asList(candidate))))
            throw new SecurityException("APK 签名证书与已安装版本不一致，已阻止安装");
        return true;
    }
}
