package app.jmbatch.android;
import java.io.IOException;
import java.util.List;

/** Bounded recovery after all independent page requests have finished. */
public final class SinglePageRecovery {
    public static final class Failure<T> {
        public final T page; public final Exception error; public final String label;
        public Failure(T page,Exception error,String label){this.page=page;this.error=error;this.label=label;}
    }
    public interface Attempt<T>{void run(T page,int round)throws Exception;}
    public interface Check{void run()throws Exception;}
    public interface Notice{void show(String text);}
    public interface Retryable{boolean test(Exception error);}
    public static <T> void recover(List<Failure<T>> failed,Attempt<T> attempt,Check check,Notice notice,Retryable retryable)throws Exception{
        if(failed.isEmpty())return;
        Failure<T> first=failed.get(0);
        if(failed.size()!=1)throw new IOException(failed.size()+" 页下载失败，首个为"+first.label+"："+first.error.getMessage()+"；已保留成功图片，未生成成品",first.error);
        Exception error=first.error;
        for(int round=1;round<=2&&retryable.test(error);round++){
            check.run();notice.show("仅"+first.label+"失败，单独重试 "+round+"/2（其他图片保留）");
            try{attempt.run(first.page,round);return;}catch(Exception e){check.run();error=e;}
        }
        throw new IOException(first.label+"下载失败（单页重试结束）："+error.getMessage()+"；已保留其他图片，未生成成品",error);
    }
}
