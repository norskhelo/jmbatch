import app.jmbatch.android.UpdateCertificateCheck;
import java.io.IOException;
import java.util.Arrays;
public class CertificateTest {
    private static int checks;
    private static void check(boolean result){checks++;if(!result)throw new AssertionError("check "+checks);}
    public static void main(String[] args){
        String[] a={"cert-a"},b={"cert-b"};
        check(Arrays.equals(UpdateCertificateCheck.read(()->null,()->a),a));
        check(Arrays.equals(UpdateCertificateCheck.read(()->new String[0],()->a),a));
        check(Arrays.equals(UpdateCertificateCheck.read(()->{throw new IOException("OEM failure");},()->a),a));
        check(Arrays.equals(UpdateCertificateCheck.read(()->a,()->{throw new AssertionError("legacy must not override modern");}),a));
        check(UpdateCertificateCheck.read(()->null,()->null)==null);
        check(UpdateCertificateCheck.read(()->{throw new IOException();},()->{throw new IOException();})==null);
        check(UpdateCertificateCheck.matches(a,a));
        check(!UpdateCertificateCheck.matches(null,a));
        check(!UpdateCertificateCheck.matches(a,null));
        check(!UpdateCertificateCheck.matches(null,null));
        check(!UpdateCertificateCheck.matches(new String[0],a));
        check(!UpdateCertificateCheck.matches(new String[]{null},a));
        try{UpdateCertificateCheck.matches(a,b);throw new AssertionError("Mismatch accepted");}catch(SecurityException expected){check(true);}
        check(UpdateCertificateCheck.matches(new String[]{"a","b"},new String[]{"b","a"}));
        try{UpdateCertificateCheck.matches(new String[]{"a","b"},new String[]{"a"});throw new AssertionError("Partial mismatch accepted");}catch(SecurityException expected){check(true);}
        System.out.println("Certificate compatibility: "+checks+" checks passed");
    }
}
