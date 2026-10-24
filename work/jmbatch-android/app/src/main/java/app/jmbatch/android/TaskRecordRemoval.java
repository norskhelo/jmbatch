package app.jmbatch.android;

import java.io.IOException;
import java.util.*;

/** Persist deletion intent before the service touches any task-owned files. */
public final class TaskRecordRemoval {
    public static final class Result {
        public int completed,cleaning,remaining;
    }
    public static Result prepare(Store store,Set<String> selected)throws Exception {
        synchronized(store){
            if(store.libraryBusy)throw new IOException("正在管理漫画文件，请稍后再删除任务");
            List<Store.Task> before=new ArrayList<>(store.tasks),targets=new ArrayList<>();
            for(Store.Task task:before){
                boolean busy=store.activeKeys.contains(task.key)||Arrays.asList("running","resetting","cancelling").contains(task.status);
                if(selected!=null){
                    if(!selected.contains(task.key))continue;
                    if(busy)throw new IOException("请先暂停选中的下载任务，或等待文件清理完成");
                }else if(busy||!Arrays.asList("done","paused","failed","cancelled","cancel_failed").contains(task.status))continue;
                targets.add(task);
            }
            Result result=new Result();result.remaining=before.size()-targets.size();
            if(targets.isEmpty())return result;
            // Completed downloads remain in the library after their queue entries disappear.
            LibraryStore.get(store.context).sync(targets);
            List<State> states=new ArrayList<>();
            for(Store.Task task:targets){
                if(task.status.equals("done")){store.tasks.remove(task);result.completed++;}
                else{
                    states.add(new State(task));task.discardRequested=true;task.status="cancelling";
                    task.phase="正在删除任务文件…";task.error="";task.speed=0;result.cleaning++;
                }
            }
            try{store.save();}catch(Exception error){
                store.tasks.clear();store.tasks.addAll(before);for(State state:states)state.restore();throw error;
            }
            return result;
        }
    }
    private static final class State {
        final Store.Task task;final String status,phase,error;final boolean requested;final long speed;
        State(Store.Task task){this.task=task;status=task.status;phase=task.phase;error=task.error;requested=task.discardRequested;speed=task.speed;}
        void restore(){task.status=status;task.phase=phase;task.error=error;task.discardRequested=requested;task.speed=speed;}
    }
    private TaskRecordRemoval(){}
}
