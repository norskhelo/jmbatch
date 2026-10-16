package app.jmbatch.android;

import java.util.*;

/** Pure selection/dispatch policy; only matching system components are automatic. */
public final class DirectoryTargets {
    // Older Huawei/Honor builds do not advertise Android's APP_FILES category.
    public static final List<String> LEGACY_MANAGERS=Collections.unmodifiableList(Arrays.asList(
        "com.huawei.hidisk", "com.hihonor.filemanager", "com.honor.filemanager"));
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
        return open(targets,launcher,false);
    }
    /** The default path must never silently return to the document picker. */
    public static boolean openManagers(List<Target> targets, Launcher launcher) {
        return open(targets,launcher,true);
    }
    private static boolean open(List<Target> targets, Launcher launcher,boolean managersOnly) {
        List<Target> ordered=new ArrayList<>();
        for(Target target:targets)if(target.system&&target.enabled&&target.exported&&target.supported&&(!managersOnly||!target.documents))ordered.add(target);
        ordered.sort((a,b)->a.documents!=b.documents?(a.documents?-1:1):a.component.compareTo(b.component));
        Set<String> attempted=new HashSet<>();
        for(Target target:ordered)if(attempted.add(target.component)) {
            try { launcher.open(target.component); return true; }
            catch(Exception unavailable) { /* A restricted OEM component must not block alternatives. */ }
        }
        return false;
    }
    private DirectoryTargets() {}
}
