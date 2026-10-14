package app.jmbatch.android;

import java.util.*;

/** Pure selection/dispatch policy; only matching system components are automatic. */
public final class DirectoryTargets {
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
        List<Target> ordered=new ArrayList<>();
        for(Target target:targets)if(target.system&&target.enabled&&target.exported&&target.supported)ordered.add(target);
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
