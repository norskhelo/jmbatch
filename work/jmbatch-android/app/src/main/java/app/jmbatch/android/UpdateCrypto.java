package app.jmbatch.android;

import java.security.*;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.io.*;

/** Pure Java verification, shared by the app and host-side tests. */
public final class UpdateCrypto {
    public static void verify(byte[] data, byte[] signature) throws Exception {
        Signature verifier=Signature.getInstance("SHA256withRSA");
        verifier.initVerify(KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(Base64.getDecoder().decode(UpdateTrust.PUBLIC_KEY))));
        verifier.update(data);
        if(!verifier.verify(signature))throw new SecurityException("更新清单数字签名无效，已阻止安装");
    }
    public static void verifyFile(File file,long size,String hash)throws Exception{
        if(size<=0||size>512L*1024*1024||file.length()!=size||!hash.matches("[0-9a-f]{64}"))throw new SecurityException("安装包大小或摘要无效");
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream in=new FileInputStream(file)){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1)digest.update(buffer,0,n);}
        StringBuilder actual=new StringBuilder();for(byte b:digest.digest())actual.append(String.format("%02x",b&255));
        if(!actual.toString().equals(hash))throw new SecurityException("安装包 SHA-256 校验失败，已阻止安装");
    }
}
