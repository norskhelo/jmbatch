"""Signed release downloads and a rollback-capable Windows update helper."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from update_trust import PUBLIC_KEY
from update_download import HOSTS, SafeRedirect, allowed_url, transfer

MAX_PACKAGE = 512 * 1024 * 1024
ROOT_ITEMS = {"JMBatch.exe", "_internal", "README.txt", "THIRD_PARTY_LICENSES", "CHANGELOG.md"}


def verify_manifest(raw, signature, repo, tag, name, expected_version, current):
    from updates import version
    try:
        pkcs1_15.new(RSA.import_key(base64.b64decode(PUBLIC_KEY))).verify(SHA256.new(raw), signature)
    except (ValueError, TypeError) as error:
        raise ValueError("更新清单数字签名无效，已阻止安装") from error
    manifest = json.loads(raw)
    if manifest.get("schema") != 1 or manifest.get("repository") != repo or manifest.get("tag") != tag:
        raise ValueError("更新清单与仓库或发布版本不匹配")
    package = manifest["packages"]["windows"]
    if package.get("name") != name or package.get("version") != expected_version or version(expected_version) <= version(current):
        raise ValueError("更新包版本不匹配或不是新版")
    if not re.fullmatch(r"[0-9a-f]{64}", package.get("sha256", "")) or type(package.get("size")) is not int or not 0 < package["size"] <= MAX_PACKAGE:
        raise ValueError("更新清单中的文件摘要或大小无效")
    return package

def verify_file(path, package):
    if path.stat().st_size != package["size"]:
        raise ValueError("安装包大小不匹配，请重新下载")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != package["sha256"]:
        raise ValueError("安装包 SHA-256 校验失败，已阻止安装")

def prepare(home, release, current, cancel, progress):
    import io
    base = release["url"].rsplit("/", 1)[0] + "/"
    repo = release["repository"]
    tag = urllib.parse.unquote(base.rstrip("/").rsplit("/", 1)[1])
    raw, signature = io.BytesIO(), io.BytesIO()
    progress("正在验证更新清单签名…")
    transfer(base + "update-manifest.json", raw, 65536, cancel,
             route_notice=lambda name: progress(f"下载更新清单 · {name}"))
    transfer(base + "update-manifest.sig", signature, 4096, cancel,
             route_notice=lambda name: progress(f"下载清单签名 · {name}"))
    package = verify_manifest(raw.getvalue(), signature.getvalue(), repo, tag, release["name"], release["version"], current)
    directory = home / "updates" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    archive = directory / "package.zip"
    try:
        route = ["GitHub"]
        def route_notice(name):
            route[0] = name
            progress(f"下载更新 · {name}")
        with archive.open("xb") as stream:
            transfer(release["url"], stream, package["size"], cancel,
                     lambda n: progress(f"下载更新 · {route[0]} · {n * 100 // package['size']}% · {n / 1048576:.1f}/{package['size'] / 1048576:.1f} MB"), route_notice=route_notice)
        verify_file(archive, package)
        if cancel.is_set():
            raise InterruptedError("已取消更新下载")
        progress("校验通过，正在准备安装…")
        stage = extract_package(archive, directory / "stage")
        return {"archive": archive, "stage": stage, "package": package}
    except Exception:
        # Only this newly-created UUID directory can be removed.
        if directory.resolve().parent == (home / "updates").resolve():
            shutil.rmtree(directory, ignore_errors=True)
        raise

def extract_package(archive, destination):
    """Validate the entire archive before creating any output files."""
    with zipfile.ZipFile(archive) as bundle:
        seen, total = set(), 0
        members = bundle.infolist()
        if len(members) > 20000:
            raise ValueError("安装包文件数量异常")
        for item in members:
            parts = item.filename.rstrip("/").split("/")
            if (len(parts) < 2 or parts[0] != "JMBatch" or parts[1] not in ROOT_ITEMS
                    or "\\" in item.filename or any(not p or p in (".", "..") or re.search(r'[<>:"|?*\x00-\x1f]', p)
                    or p.endswith((" ", ".")) or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p) for p in parts)
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError("安装包包含不安全的文件路径")
            key = item.filename.rstrip("/").casefold()
            if key in seen:
                raise ValueError("安装包包含重名路径")
            seen.add(key)
            total += item.file_size
        if total > 2 * 1024**3 or "jmbatch/jmbatch.exe" not in seen:
            raise ValueError("安装包结构或大小异常")
        destination.mkdir(parents=True, exist_ok=False)
        bundle.extractall(destination)
    stage = destination / "JMBatch"
    if not (stage / "JMBatch.exe").is_file() or not (stage / "_internal").is_dir():
        raise ValueError("缺少程序文件")
    return stage

def replace_install(stage, target):
    """Replace only distributed root items; preserve unrelated user files."""
    stage, target = Path(stage).resolve(), Path(target).resolve()
    if stage == target or stage.is_relative_to(target) or target.is_relative_to(stage) or not (target / "JMBatch.exe").is_file():
        raise ValueError("安装目录无效")
    for name in ROOT_ITEMS:
        if (target / name).is_symlink() or (target / name).is_junction():
            raise ValueError("安装目录含链接，无法安全替换")
    backup = target / (".jmbatch-update-backup-" + uuid.uuid4().hex)
    backup.mkdir()
    moved, added = [], []
    try:
        for name in sorted(ROOT_ITEMS):
            old, new = target / name, stage / name
            if old.exists():
                old.rename(backup / name)
                moved.append(name)
            if new.exists():
                added.append(name)
                if new.is_dir():
                    shutil.copytree(new, old)
                else:
                    shutil.copy2(new, old)
    except Exception:
        for name in reversed(added):
            path = target / name
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        for name in reversed(moved):
            (backup / name).rename(target / name)
        raise
    return backup

def launch_helper(ready):
    if not getattr(sys, "frozen", False) or os.name != "nt":
        raise ValueError("应用内安装仅支持打包的 Windows 版；源码运行请手动更新")
    verify_file(ready["archive"], ready["package"])
    target = Path(sys.executable).resolve().parent
    stage = ready["stage"].resolve()
    if stage == target or stage.is_relative_to(target) or target.is_relative_to(stage):
        raise ValueError("程序目录与更新缓存重叠，请将程序移到独立目录")
    probe = target / (".update-write-test-" + uuid.uuid4().hex)
    try:
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as error:
        raise ValueError("程序目录不可写，请将程序放到有写入权限的目录后重试") from error
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen([str(ready["stage"] / "JMBatch.exe"), "--apply-update", str(target), str(os.getpid())],
                     cwd=str(ready["stage"]), env=env, creationflags=subprocess.CREATE_NO_WINDOW)

def apply_update(target, pid):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000, False, int(pid))
    if not handle and ctypes.get_last_error() != 87:
        ctypes.windll.user32.MessageBoxW(None, "无法确认旧程序是否退出，更新已取消。", "JM Batch 更新", 0x10)
        return
    if handle:
        result = kernel.WaitForSingleObject(handle, 120000)
        kernel.CloseHandle(handle)
        if result != 0:
            ctypes.windll.user32.MessageBoxW(None, "旧程序未退出，更新已取消。", "JM Batch 更新", 0x10)
            return
    try:
        replace_install(Path(sys.executable).parent, Path(target))
    except Exception as error:
        ctypes.windll.user32.MessageBoxW(None, "更新失败，已尝试恢复旧版：\n" + str(error), "JM Batch 更新", 0x10)
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    try:
        subprocess.Popen([str(Path(target) / "JMBatch.exe")], cwd=target, env=env)
    except OSError as error:
        ctypes.windll.user32.MessageBoxW(None, "请手动启动程序：\n" + str(error), "JM Batch 更新", 0x10)
