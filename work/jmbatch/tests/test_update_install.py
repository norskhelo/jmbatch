import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15
import update_install as updater
TEST_TEMP = Path(__file__).resolve().parent / "_tmp"
TEST_TEMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEST_TEMP)

class InstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=RSA.generate(2048)
        cls.public=base64.b64encode(cls.key.public_key().export_key(format="DER")).decode()

    def manifest(self, **changes):
        package=dict(version="0.1.7",name="JMBatch-0.1.7-Windows-x64.zip",size=5,sha256=hashlib.sha256(b"hello").hexdigest())
        package.update(changes)
        raw=json.dumps(dict(schema=1,repository="owner/app",tag="v1",packages={"windows":package})).encode()
        return raw,pkcs1_15.new(self.key).sign(SHA256.new(raw))

    def verify(self,raw,sig,**changes):
        args=dict(repo="owner/app",tag="v1",name="JMBatch-0.1.7-Windows-x64.zip",expected_version="0.1.7",current="0.1.6")
        args.update(changes)
        with patch.object(updater,"PUBLIC_KEY",self.public):return updater.verify_manifest(raw,sig,**args)

    def test_signed_manifest_and_tampering(self):
        raw,sig=self.manifest()
        self.assertEqual(self.verify(raw,sig)["size"],5)
        for data,signature in ((raw+b" ",sig),(raw,sig[:-1]),(raw,b"")):
            with self.assertRaises(ValueError):self.verify(data,signature)

    def test_manifest_identity_and_downgrade(self):
        raw,sig=self.manifest()
        for changes in (dict(repo="evil/app"),dict(tag="other"),dict(name="other.zip"),dict(current="0.1.7"),dict(current="0.1.8")):
            with self.assertRaises(ValueError):self.verify(raw,sig,**changes)
        for changes in (dict(size=-1),dict(size=True),dict(size=updater.MAX_PACKAGE+1),dict(sha256="bad")):
            with self.assertRaises(ValueError):self.verify(*self.manifest(**changes))

    def test_size_and_hash(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"package";path.write_bytes(b"hello")
            package=self.verify(*self.manifest());updater.verify_file(path,package)
            path.write_bytes(b"Hello")
            with self.assertRaises(ValueError):updater.verify_file(path,package)
            path.write_bytes(b"hell")
            with self.assertRaises(ValueError):updater.verify_file(path,package)

    def test_redirect_allowlist(self):
        self.assertTrue(updater.allowed_url("https://release-assets.githubusercontent.com/example?token=a"))
        for url in ("http://github.com/x","https://github.com.evil.test/x","https://user@github.com/x","https://github.com:8080/x"):
            self.assertFalse(updater.allowed_url(url))

    def test_zip_path_attacks_and_symlinks(self):
        for name in ("../outside","JMBatch/../outside","JMBatch/_internal/../../outside","JMBatch/_internal/C:foo","JMBatch/_internal/CON.txt","JMBatch/_internal/file.","JMBatch/_internal/a\\b","JMBatch/unknown.txt"):
            with tempfile.TemporaryDirectory() as t:
                archive=Path(t)/"p.zip"
                with zipfile.ZipFile(archive,"w") as z:z.writestr(name,b"bad")
                with self.assertRaises(ValueError):updater.extract_package(archive,Path(t)/"stage")
                self.assertFalse((Path(t)/"stage").exists())
        with tempfile.TemporaryDirectory() as t:
            archive=Path(t)/"p.zip";info=zipfile.ZipInfo("JMBatch/_internal/link");info.create_system=3;info.external_attr=0o120777<<16
            with zipfile.ZipFile(archive,"w") as z:z.writestr(info,"../../outside")
            with self.assertRaises(ValueError):updater.extract_package(archive,Path(t)/"stage")

    def test_zip_case_collision(self):
        with tempfile.TemporaryDirectory() as t:
            archive=Path(t)/"p.zip"
            with zipfile.ZipFile(archive,"w") as z:
                z.writestr("JMBatch/JMBatch.exe",b"exe");z.writestr("JMBatch/_internal/a",b"a");z.writestr("JMBatch/_internal/A",b"b")
            with self.assertRaises(ValueError):updater.extract_package(archive,Path(t)/"stage")

    def test_successful_install_preserves_user_files_and_backup(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);stage=root/"stage";target=root/"installed"
            for directory,data in ((stage,b"new"),(target,b"old")):
                (directory/"_internal").mkdir(parents=True);(directory/"JMBatch.exe").write_bytes(data);(directory/"_internal/runtime").write_bytes(data)
            (target/"my-comics.zip").write_bytes(b"user")
            backup=updater.replace_install(stage,target)
            self.assertEqual((target/"JMBatch.exe").read_bytes(),b"new")
            self.assertEqual((target/"my-comics.zip").read_bytes(),b"user")
            self.assertEqual((backup/"JMBatch.exe").read_bytes(),b"old")

    def test_failed_install_rolls_back(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);stage=root/"stage";target=root/"installed"
            for directory,data in ((stage,b"new"),(target,b"old")):
                (directory/"_internal").mkdir(parents=True);(directory/"JMBatch.exe").write_bytes(data);(directory/"_internal/runtime").write_bytes(data)
            with patch.object(updater.shutil,"copytree",side_effect=OSError("disk full")):
                with self.assertRaises(OSError):updater.replace_install(stage,target)
            self.assertEqual((target/"JMBatch.exe").read_bytes(),b"old")
            self.assertEqual((target/"_internal/runtime").read_bytes(),b"old")

    def test_cancel_cleans_partial_download(self):
        import threading
        raw,sig=self.manifest()
        def transfer(url,out,limit,cancel,progress=lambda n:None):
            if url.endswith(".json"):out.write(raw)
            elif url.endswith(".sig"):out.write(sig)
            else:out.write(b"he");raise InterruptedError("cancel")
        with tempfile.TemporaryDirectory() as t,patch.object(updater,"PUBLIC_KEY",self.public),patch.object(updater,"transfer",side_effect=transfer):
            release=dict(url="https://github.com/owner/app/releases/download/v1/JMBatch-0.1.7-Windows-x64.zip",repository="owner/app",name="JMBatch-0.1.7-Windows-x64.zip",version="0.1.7")
            with self.assertRaises(InterruptedError):updater.prepare(Path(t),release,"0.1.6",threading.Event(),lambda s:None)
            self.assertEqual(list((Path(t)/"updates").iterdir()),[])

if __name__=="__main__":unittest.main()
