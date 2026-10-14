"""Optional GitHub checks and user-confirmed, signed in-app updates."""
from __future__ import annotations

import json
import queue
import re
import threading
import time
import urllib.parse
import urllib.request

LIMIT = 1024 * 1024
TIMEOUT = 8
DEFAULT_REPOSITORY = "norskhelo/jmbatch"
CURRENT_NOTES = 'Windows 0.2.0 / Android 0.3.0 — 2026-10-14\n\n下载与导出分离\n\n• 下载默认保存为可直接查看的图片目录，不再自动合成 PDF 或 ZIP。图片按章节、页码排序：0001/00001.jpg、0001/00002.jpg、0002/00001.jpg。\n• 图片目录保存下载处理后的原分辨率图片；保存和后续 ZIP/PDF 导出不额外缩放图片。上游图片的必要解码/还原沿用现有实现，并非承诺与网站原始响应逐字节一致。\n• 首页取消下载格式选择；PDF、ZIP、纯编号命名、单章节 ZIP 平铺等选项移入“导出”。图片始终保留，导出可重复进行且无需重新联网下载。\n• PDF 提供统一导出和分章节导出；分章节按章节编号生成独立 PDF，文件名附 0001、0002 等序号。ZIP 多章节始终按章节分目录。\n• 可在导出时选择保存目录；遇到同名文件停止并提示，不覆盖原有文件。取消或失败保留源图片。\n\n漫画库与兼容\n\n• 漫画库支持图片目录的扫描、打开、收藏、导出和删除；Android 应用内目录浏览与系统文档入口支持章节图片。\n• 保留已有 PDF/ZIP 记录和收藏；未完成的旧下载任务继续时改为图片保存，并复用已验证缓存。\n• 图片目录包含 .jmbatch-album.json 清单，供扫描、排序、恢复和导出使用。删除该清单或改动图片路径/大小可能导致校验失败。\n• 保留百分比、预计时间、大小与自动速度单位；文件校验并保存成功后显示 100.0% 和“下载完成”。\n\n版本与交付\n\n• Windows 0.2.0；Android 0.3.0（versionCode 300），保留原包名和签名。\n• 本次按要求推送源码与日志；安装包在本地分版本交付，未创建 GitHub Release 或上传新安装包。\n• 离线测试及本地构建用于回归；Android 真机、系统目录提供方及真实网络下载仍需实际设备验证。\n'


def update_settings(data):
    """Migrate the old unconfigured default once; respect later blank choices."""
    repo = normalize_repo(data.get("repository", ""))
    if not data.get("repository_default_v1") and not repo:
        repo = DEFAULT_REPOSITORY
    return {"repository": repo, "automatic": bool(data.get("automatic", True)),
            "repository_default_v1": True}


def normalize_repo(value):
    value = value.strip()
    if not value:
        return ""
    if value.startswith("https://github.com/"):
        value = value[len("https://github.com/"):].rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", value) or value.split("/")[1] in (".", ".."):
        raise ValueError("请填写公开 GitHub 仓库：用户名/仓库名，或对应的 https://github.com/ 链接。")
    return value


def version(value):
    if not re.fullmatch(r"[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}", value):
        raise ValueError("版本号无效")
    return tuple(map(int, value.split(".")))


def select_release(releases, repo, current):
    best = None
    current_version = version(current)
    if not isinstance(releases, list):
        raise ValueError("无效的 GitHub 响应")
    for release in releases[:20]:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            match = re.fullmatch(r"JMBatch-([0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6})-Windows-x64\.zip", name)
            if not match or asset.get("state") != "uploaded" or asset.get("size", 0) <= 0:
                continue
            url = asset.get("browser_download_url", "")
            parsed = urllib.parse.urlsplit(url)
            path = urllib.parse.unquote(parsed.path)
            if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment
                    or not path.lower().startswith("/" + repo.lower() + "/releases/download/")
                    or path.rsplit("/", 1)[-1] != name or any(p in (".", "..") for p in path.split("/"))):
                continue
            candidate = version(match[1])
            if candidate > current_version and (best is None or candidate > version(best["version"])):
                notes = release.get("body") or "发布者未填写更新日志。"
                best = {"version": match[1], "name": name, "url": url, "repository": repo, "notes": str(notes)[:8000]}
    return best


def fetch_release(repo, current, include_current=False):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    url = f"https://api.github.com/repos/{repo}/releases?per_page=20"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "JMBatch-Updater",
                                                  "X-GitHub-Api-Version": "2022-11-28"})
    # urllib uses Windows system proxy settings as well as environment proxies.
    opener = urllib.request.build_opener(NoRedirect)
    deadline = time.monotonic() + TIMEOUT
    with opener.open(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise ValueError("GitHub 暂不可用")
        data = bytearray()
        while True:
            chunk = response.read(65536)
            if time.monotonic() >= deadline:
                raise TimeoutError("更新检查超时")
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > LIMIT:
                raise ValueError("更新响应过大")
        result = select_release(json.loads(data), repo, "0.0.0" if include_current else current)
        return result if result is None or version(result["version"]) >= version(current) else None


def fetch_bulletin(repo, current):
    return fetch_release(repo, current, include_current=True)


def announcement_text(bulletin, repo, current, local_notes):
    try:
        if bulletin.get("repository") == repo and version(bulletin["version"]) >= version(current):
            notes = bulletin.get("notes", "")
            if isinstance(notes, str) and notes.strip() and notes != "发布者未填写更新日志。":
                return "版本 " + bulletin["version"] + " 更新公告\n\n" + notes[:8000]
    except (AttributeError, KeyError, ValueError, TypeError):
        pass
    return local_notes


class Checker:
    """The UI stops waiting at its deadline even if OS DNS hasn't returned."""
    def __init__(self):
        self.thread = None
        self.pending = None

    def start(self, repo, current, fetch=fetch_release):
        if self.pending is not None or (self.thread is not None and self.thread.is_alive()):
            return False
        channel = queue.Queue(maxsize=1)
        self.pending = (time.monotonic() + TIMEOUT, channel)
        def worker():
            try:
                channel.put(("ok", fetch(repo, current)))
            except Exception:
                channel.put(("skipped", None))
        self.thread = threading.Thread(target=worker, daemon=True, name="github-update-check")
        self.thread.start()
        return True

    def poll(self):
        if self.pending is None:
            return None
        deadline, channel = self.pending
        if time.monotonic() >= deadline:
            self.pending = None
            return ("skipped", None)
        try:
            result = channel.get_nowait()
        except queue.Empty:
            return None
        self.pending = None
        return result


class UpdateUI:
    def __init__(self, app):
        self.app = app
        self.checker = Checker()
        self.path = app.home / "updates.json"
        self.repo, self.automatic = DEFAULT_REPOSITORY, True
        self.latest, self.dialog, self.status = None, None, "等待检查"
        self.downloading, self.ready = False, None
        self.cancel = threading.Event()
        self.download_events = queue.Queue()
        self.bulletin_path = app.home / "update-announcement.json"
        self.seen_path = app.home / "announcement-seen.txt"
        try:
            self.bulletin = json.loads(self.bulletin_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.bulletin = None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, AttributeError):
            data = {}
        try:
            settings = update_settings(data)
        except (ValueError, TypeError, AttributeError):
            settings = update_settings({})
        self.repo, self.automatic = settings["repository"], settings["automatic"]
        self.status = "等待检查" if self.repo else "仓库留空，不检查更新"
        if settings != data:
            from core import atomic_json
            try:
                atomic_json(self.path, settings)
            except OSError:
                pass  # A read-only config must not prevent startup or downloads.

    def startup(self):
        from core import VERSION
        try:
            seen = self.seen_path.read_text(encoding="utf-8")
        except OSError:
            seen = ""
        if seen != VERSION:
            self.show_notes(local=True)
            try:
                self.seen_path.write_text(VERSION, encoding="utf-8")
            except OSError:
                pass
        if self.automatic and self.repo:
            self.check()

    def check(self):
        from core import VERSION
        if self.downloading or self.ready:
            return
        if not self.repo:
            self.status = "仓库留空，已跳过检查"
            self.refresh()
            return
        if not self.checker.start(self.repo, VERSION, fetch_bulletin):
            self.status = "上次检查仍在结束中，已跳过本次检查"
            self.refresh()
            return
        self.checked_repo = self.repo
        self.status = "正在后台检查，最多等待 8 秒…"
        self.refresh()
        self.app.root.after(100, self.poll)

    def poll(self):
        result = self.checker.poll()
        if result is None:
            self.app.root.after(100, self.poll)
            return
        if self.repo == self.checked_repo:
            from core import VERSION, atomic_json
            state, bulletin = result
            self.latest = bulletin if bulletin and version(bulletin["version"]) > version(VERSION) else None
            if state == "ok" and bulletin:
                self.bulletin = bulletin
                try:
                    atomic_json(self.bulletin_path, bulletin)
                except OSError:
                    pass
            self.status = ("检查失败或超时，已跳过" if state == "skipped" else
                           "发现新版 " + self.latest["version"] if self.latest else "当前已是适用版本，可查看下方更新公告")
            self.app.update_button.configure(text="发现新版 " + self.latest["version"] if self.latest else "软件更新 / 公告")
            self.refresh()

    def refresh(self):
        if self.dialog is not None and self.dialog.winfo_exists():
            self.status_var.set(self.status)
            self.download_button.configure(state="normal" if self.latest or self.downloading else "disabled",
                                           text="取消下载" if self.downloading else "安装并重启" if self.ready else "下载新版")
            self.announcement_area.configure(state="normal")
            self.announcement_area.delete("1.0", "end")
            self.announcement_area.insert("1.0", self.notes_text())
            self.announcement_area.configure(state="disabled")

    def notes_text(self):
        from core import VERSION
        return announcement_text(self.bulletin, self.repo, VERSION, CURRENT_NOTES)

    def show_notes(self, local=False):
        import tkinter as tk
        from tkinter.scrolledtext import ScrolledText
        window = tk.Toplevel(self.app.root)
        window.title("更新公告")
        window.transient(self.app.root)
        area = ScrolledText(window, width=76, height=24, wrap="word", padx=12, pady=12)
        area.pack(fill="both", expand=True)
        area.insert("1.0", CURRENT_NOTES if local else self.notes_text())
        area.configure(state="disabled")

    def download(self):
        from tkinter import messagebox
        from core import VERSION
        from update_install import prepare, launch_helper
        if self.downloading:
            self.cancel.set()
            self.status = "正在取消，当前网络请求结束后停止…"
            self.refresh()
            return
        if self.ready:
            if not messagebox.askyesno("安装更新", "更新将暂停下载任务、保存设置并重启程序。是否继续？", parent=self.dialog):
                return
            try:
                self.app.engine.settings = self.app.current_settings()
                self.app.engine.close()
                launch_helper(self.ready)
                self.app.root.destroy()
            except Exception as error:
                messagebox.showerror("无法安装更新", str(error), parent=self.dialog)
            return
        if not self.latest:
            return
        self.downloading = True
        self.cancel.clear()
        self.status = "正在准备更新…"
        release = dict(self.latest)
        def worker():
            try:
                ready = prepare(self.app.home, release, VERSION, self.cancel, lambda s: self.download_events.put(("progress", s)))
                self.download_events.put(("ready", ready))
            except Exception as error:
                self.download_events.put(("error", f"{type(error).__name__}: {error}"))
        threading.Thread(target=worker, daemon=True, name="update-download").start()
        self.refresh()
        self.app.root.after(100, self.poll_download)

    def poll_download(self):
        try:
            while True:
                kind, value = self.download_events.get_nowait()
                if kind == "progress":
                    self.status = value
                elif kind == "ready":
                    self.downloading = False
                    self.ready = value
                    self.status = "签名和 SHA-256 校验通过，可以安装并重启"
                else:
                    self.downloading = False
                    self.status = "更新未完成：" + value
        except queue.Empty:
            pass
        self.refresh()
        if self.downloading:
            self.app.root.after(100, self.poll_download)

    def show(self):
        import tkinter as tk
        from tkinter import ttk, messagebox
        from core import VERSION, atomic_json
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        dialog = self.dialog = tk.Toplevel(self.app.root)
        dialog.title("软件更新")
        dialog.transient(self.app.root)
        frame = ttk.Frame(dialog, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"当前 Windows 版本：{VERSION}").pack(anchor="w")
        ttk.Label(frame, text="GitHub 公开仓库（用户名/仓库名；留空不检查）").pack(anchor="w", pady=(16, 6))
        repo_var = tk.StringVar(value=self.repo)
        ttk.Entry(frame, textvariable=repo_var, width=60).pack(fill="x")
        auto_var = tk.BooleanVar(value=self.automatic)
        ttk.Checkbutton(frame, text="启动时自动检查更新", variable=auto_var).pack(anchor="w", pady=12)
        self.status_var = tk.StringVar(value=self.status)
        ttk.Label(frame, textvariable=self.status_var).pack(anchor="w", pady=6)
        from tkinter.scrolledtext import ScrolledText
        ttk.Label(frame, text="更新公告（离线也可查看）").pack(anchor="w", pady=(8, 4))
        self.announcement_area = ScrolledText(frame, width=72, height=10, wrap="word")
        self.announcement_area.pack(fill="both", expand=True)
        ttk.Label(frame, text="检测无响应时静默跳过，不影响下载任务。\n在应用内下载，验证签名和 SHA-256 后，确认安装并重启。\n只信任本软件发布密钥签署的更新；不发送漫画编号或 Cookie。", justify="left").pack(anchor="w", pady=12)
        def save(check=False):
            if self.downloading or self.ready:
                messagebox.showinfo("更新进行中", "当前更新完成前不能更改仓库，请安装更新或重启程序。", parent=dialog)
                return
            try:
                repo = normalize_repo(repo_var.get())
                atomic_json(self.path, {"repository": repo, "automatic": auto_var.get(), "repository_default_v1": True})
                if repo != self.repo:
                    self.latest = None
                    self.app.update_button.configure(text="软件更新 / 公告")
                self.repo, self.automatic = repo, auto_var.get()
                self.status = "设置已保存" if repo else "仓库留空，不检查更新"
                self.refresh()
                if check:
                    self.check()
            except (ValueError, OSError) as error:
                messagebox.showerror("无法保存更新设置", str(error), parent=dialog)
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        ttk.Button(actions, text="保存", command=save).pack(side="left")
        ttk.Button(actions, text="保存并检查", command=lambda: save(True)).pack(side="left", padx=8)
        ttk.Button(actions, text="完整更新公告", command=self.show_notes).pack(side="left", padx=4)
        self.download_button = ttk.Button(actions, text="下载新版", command=self.download)
        self.download_button.pack(side="right")
        self.refresh()
