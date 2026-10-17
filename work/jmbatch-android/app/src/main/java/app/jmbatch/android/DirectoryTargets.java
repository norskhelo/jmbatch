package app.jmbatch.android;

import java.util.*;

/** Pure selection/dispatch policy; only matching system components are automatic. */
public final class DirectoryTargets {
    // This package opens Huawei Cloud on the reported device, not local storage.
    public static boolean excluded(String component) {
        return component.split("/",2)[0].equals("com.huawei.hidisk");
    }
    public static boolean documentsUi(String packageName,String activityName) {
        return (packageName+"/"+activityName).toLowerCase(Locale.ROOT).contains("documentsui");
    }
    public static final class Target {
        public final String component;
        final boolean system, enabled, exported, supported, documents;
        public Target(String component, boolean system, boolean enabled, boolean exported, boolean supported, boolean documents) {
            this.component=component; this.system=system; this.enabled=enabled;
            this.exported=exported; this.supported=supported; this.documents=documents;
        }
    }
    public interface Launcher { void open(String component) throws Exception; }
    public static boolean open(List<Target> targets, Launcher launcher) {
        return dispatch(ordered(targets,true,true,null),launcher);
    }
    /** Unclassified document viewers remain a manual fallback. */
    public static boolean openManagers(List<Target> targets, Launcher launcher) {
        List<Target> managers=new ArrayList<>();
        for(Target target:targets)if(!target.documents)managers.add(target);
        return dispatch(ordered(managers,true,false,null),launcher);
    }
    public static boolean openNative(List<Target> targets,String preferred,Launcher launcher) {
        return dispatch(ordered(targets,true,false,preferred),launcher);
    }
    public static List<Target> ordered(List<Target> targets,boolean systemOnly,boolean documentsFirst,String preferred) {
        List<Target> ordered=new ArrayList<>();
        for(Target target:targets)if((!systemOnly||target.system)&&target.enabled&&target.exported&&target.supported&&!excluded(target.component))ordered.add(target);
        ordered.sort((a,b)->{
            if(a.component.equals(preferred)!=b.component.equals(preferred))return a.component.equals(preferred)?-1:1;
            return a.documents!=b.documents?(a.documents==documentsFirst?-1:1):a.component.compareTo(b.component);
        });
        return ordered;
    }
    private static boolean dispatch(Iterable<Target> ordered, Launcher launcher) {
        Set<String> attempted=new HashSet<>();
        for(Target target:ordered)if(attempted.add(target.component)) {
            try { launcher.open(target.component); return true; }
            catch(Exception unavailable) { /* A restricted OEM component must not block alternatives. */ }
        }
        return false;
    }
    private DirectoryTargets() {}
}
