package app.jmbatch.android;

import java.util.*;
import java.util.function.*;

/** Continue after individual failures; cancellation stops before the next item. */
public final class BatchOperations {
    public interface Action<T>{void apply(T item)throws Exception;}
    public static final class Result {
        public int succeeded,failed,unprocessed;
        public final List<String> errors=new ArrayList<>();
        public String summary(){return "成功 "+succeeded+" 项，失败 "+failed+" 项，未处理 "+unprocessed+" 项。";}
    }
    public static <T> Result run(List<T> items,Action<T> action,BooleanSupplier cancelled,Function<T,String> label,BiConsumer<Integer,Integer> progress){
        Result result=new Result();
        for(T item:items){
            if(cancelled.getAsBoolean())break;
            try{action.apply(item);result.succeeded++;}
            catch(Exception error){result.failed++;result.errors.add(label.apply(item)+"："+(error.getMessage()==null?error.getClass().getSimpleName():error.getMessage()));}
            progress.accept(result.succeeded+result.failed,items.size());
        }
        result.unprocessed=items.size()-result.succeeded-result.failed;return result;
    }
}
