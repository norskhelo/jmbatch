package app.jmbatch.android;

public final class RealtimeSpeedTest {
    public static void main(String[] args) {
        RealtimeSpeed rate=new RealtimeSpeed();rate.reset(1000,100000);
        if(rate.sample(2000,104096)!=4096||rate.sample(3000,104096)!=0||rate.sample(5000,108192)!=2048)throw new AssertionError("latest interval only");
        rate.reset(6000,108192);if(rate.sample(7000,108192)!=0)throw new AssertionError("cached bytes must not spike");
        System.out.println("RealtimeSpeedTest: completed-byte speed and cache baseline passed");
    }
}
