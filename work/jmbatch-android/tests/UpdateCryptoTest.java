import app.jmbatch.android.UpdateCrypto;
import java.nio.file.*;
public class UpdateCryptoTest {
    public static void main(String[] args)throws Exception{
        Path root=Paths.get(args[0]);byte[] data=Files.readAllBytes(root.resolve("manifest.bin")),sig=Files.readAllBytes(root.resolve("manifest.sig"));
        UpdateCrypto.verify(data,sig);
        data[0]^=1;boolean failed=false;try{UpdateCrypto.verify(data,sig);}catch(Exception e){failed=true;}if(!failed)throw new AssertionError("tampered manifest accepted");
        data[0]^=1;sig[0]^=1;failed=false;try{UpdateCrypto.verify(data,sig);}catch(Exception e){failed=true;}if(!failed)throw new AssertionError("tampered signature accepted");
        Path file=Files.createTempFile("update-hash-test",".bin");try{
            Files.write(file,"hello".getBytes("UTF-8"));UpdateCrypto.verifyFile(file.toFile(),5,"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");
            failed=false;try{UpdateCrypto.verifyFile(file.toFile(),4,"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");}catch(Exception e){failed=true;}if(!failed)throw new AssertionError("size mismatch accepted");
            Files.write(file,"Hello".getBytes("UTF-8"));failed=false;try{UpdateCrypto.verifyFile(file.toFile(),5,"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");}catch(Exception e){failed=true;}if(!failed)throw new AssertionError("hash mismatch accepted");
        }finally{Files.deleteIfExists(file);}
        System.out.println("Update crypto: 6 checks passed");
    }
}
