package app.jmbatch.android;

/** A short, single-pointer tap; once moved or cancelled it cannot become a tap. */
public final class ReaderTap {
    private final float slop;
    private final long timeout;
    private float x,y;
    private long started;
    private boolean active;
    public ReaderTap(float slop,long timeout){this.slop=slop;this.timeout=timeout;}
    public void down(float x,float y,long time){this.x=x;this.y=y;started=time;active=true;}
    public void move(float x,float y){if(Math.max(Math.abs(x-this.x),Math.abs(y-this.y))>slop)active=false;}
    public boolean up(float x,float y,long time){move(x,y);boolean tap=active&&time-started<timeout;active=false;return tap;}
    public void cancel(){active=false;}
}
