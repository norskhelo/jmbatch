"""Optional GitHub checks and user-confirmed, signed in-app updates."""
from __future__ import annotations

import json
import queue
import re
import threading
import time
import urllib.parse
import urllib.request

LIMIT = 8 * 1024 * 1024
PAGE_SIZE = 100
MAX_PAGES = 10
TIMEOUT = 8
DEFAULT_REPOSITORY = "norskhelo/jmbatch"
CURRENT_NOTES = 'Windows 0.2.3 / Android 0.3.3 — 2026-10-15\n\n多任务同时下载\n\n• 下载队列支持同时下载多本漫画。设置中新增“同时下载任务数”，默认 2，可设为 1–4；设为 1 时按原来的顺序逐本下载。\n• “每个任务图片线程数”独立控制单本的图片并发，仍为 1–16、默认 8。并行任务越多，总网络连接和内存占用越高，手机发热或遇到限流时可调低。\n• 保存并行任务数后用于后续调度；提高上限时自动启动等待任务，降低上限时等待当前任务结束，不中断正在下载的漫画。新加入的任务也会自动补位。\n• 各任务分别记录进度、速度、预计完成时间、缓存和自动重连次数。界面显示同时运行数量及总速度；Windows 选中运行中的任务可查看该任务的详细进度，Android 通知展示多个任务。\n• 取消或失败的任务不会停止其他下载。暂停会停止全部任务并保留已验证缓存；Android 在旧请求完全退出后才释放任务名额，防止立即重试时重复写入缓存。关闭应用后重新打开，未完成任务保持暂停，点击开始继续。\n• 其他网络参数继续用于新任务和手动重试；已有任务的保存目录和下载参数保持原快照。原有图片保存、PDF/ZIP 导出、收藏及更新签名验证继续保留。\n\n版本与兼容\n\n• Windows 升至 0.2.3；Android 升至 0.3.3（versionCode 303）。保留 app.jmbatch.android 包名、原 APK 签名与更新公钥，支持覆盖安装。\n• 旧版队列和设置自动采用默认 2 个并行任务；如需串行下载，可在设置中改为 1。\n• 发布双端安装包、同版日志、SHA-256 校验文件、签名更新清单；主页原始下载与国内镜像入口同步至本版。\n\n验证范围\n\n• 验证真实 Windows 子进程同时运行、并发上限与补位、进度隔离、取消、暂停恢复、任务失败、进程崩溃和有上限的自动重连；执行完整单元测试及源码/成品离线自检。\n• 执行 Android 宿主并发测试、既有回归测试、编译与原证书签名校验。未连接 Android 真机，未进行真实网站多任务下载或各地区镜像测速；实际速度受网络、设备和服务端限制。\n'


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


def select_release(releases, repo, current, include_current=False):
    """Select the installer and every applicable bulletin in its upgrade range."""
    candidates = {}
    current_version = version(current)
    if not isinstance(releases, list):
        raise ValueError("无效的 GitHub 响应")
    for release in releases:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        assets = release.get("assets")
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = asset.get("name", "")
            if not isinstance(name, str):
                continue
            match = re.fullmatch(r"JMBatch-([0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6})-Windows-x64\.zip", name)
            if (not match or asset.get("state") != "uploaded"
                    or not isinstance(asset.get("size"), (int, float)) or asset["size"] <= 0):
                continue
            url = asset.get("browser_download_url", "")
            if not isinstance(url, str):
                continue
            try:
                parsed = urllib.parse.urlsplit(url)
            except ValueError:
                continue
            path = urllib.parse.unquote(parsed.path)
            if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment
                    or not path.lower().startswith("/" + repo.lower() + "/releases/download/")
                    or path.rsplit("/", 1)[-1] != name or any(p in (".", "..") for p in path.split("/"))):
                continue
            candidate = version(match[1])
            if candidate < current_version or (candidate == current_version and not include_current):
                continue
            notes = release.get("body")
            if not isinstance(notes, str) or not notes.strip():
                notes = "发布者未填写更新日志。"
            rank = (str(release.get("published_at") or ""), str(release.get("tag_name") or ""))
            if candidate not in candidates or rank > candidates[candidate][0]:
                candidates[candidate] = (rank, {"version": match[1], "name": name, "url": url,
                                               "repository": repo, "notes": notes})
    if not candidates:
        return None
    latest = max(candidates)
    best = dict(candidates[latest][1])
    best.update(history_schema=2, from_version=current, history=[
        {"version": candidates[v][1]["version"], "notes": candidates[v][1]["notes"]}
        for v in sorted(candidates) if v > current_version or v == latest
    ])
    return best


def fetch_release(repo, current, include_current=False):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    repo = normalize_repo(repo)
    if not repo:
        return None
    # urllib uses Windows system proxy settings as well as environment proxies.
    opener = urllib.request.build_opener(NoRedirect)
    deadline = time.monotonic() + TIMEOUT
    releases, total = [], 0
    for page in range(1, MAX_PAGES + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("完整更新日志读取超时")
        url = f"https://api.github.com/repos/{repo}/releases?per_page={PAGE_SIZE}&page={page}"
        request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "JMBatch-Updater",
                                                      "X-GitHub-Api-Version": "2022-11-28"})
        with opener.open(request, timeout=remaining) as response:
            if response.status != 200:
                raise ValueError("GitHub 暂不可用")
            data = bytearray()
            while True:
                chunk = response.read(65536)
                if time.monotonic() >= deadline:
                    raise TimeoutError("完整更新日志读取超时")
                if not chunk:
                    break
                data.extend(chunk)
                total += len(chunk)
                if total > LIMIT:
                    raise ValueError("完整更新日志响应过大")
        batch = json.loads(data)
        if not isinstance(batch, list):
            raise ValueError("无效的 GitHub 响应")
        releases.extend(batch)
        if len(batch) < PAGE_SIZE:
            return select_release(releases, repo, current, include_current)
    # Never label a truncated set of releases as a complete upgrade history.
    raise ValueError("完整更新日志超过读取页数上限")


def fetch_bulletin(repo, current):
    return fetch_release(repo, current, include_current=True)


def announcement_text(bulletin, repo, current, local_notes):
    try:
        if bulletin.get("repository") == repo and version(bulletin["version"]) >= version(current):
            latest = bulletin["version"]
            if bulletin.get("history_schema") == 2:
                baseline = version(bulletin["from_version"])
                history = bulletin["history"]
                if baseline > version(current) or not isinstance(history, list) or not history:
                    return local_notes
                previous = None
                for entry in history:
                    number = version(entry["version"])
                    if (number < baseline or number > version(latest)
                            or (previous is not None and number <= previous)
                            or not isinstance(entry["notes"], str)):
                        return local_notes
                    previous = number
                if previous != version(latest):
                    return local_notes
                if version(latest) == version(current):
                    notes = history[-1]["notes"]
                    return local_notes if notes == "发布者未填写更新日志。" else "版本 " + latest + " 更新公告\n\n" + notes
                sections = ["版本 " + entry["version"] + "\n\n" + entry["notes"]
                            for entry in history if version(entry["version"]) > version(current)]
                return ("从当前版本 " + current + " → 最新版本 " + latest
                        + " 的全部更新（不含当前版，按版本升序）\n\n" + "\n\n────────\n\n".join(sections))
            notes = bulletin.get("notes", "")
            if isinstance(notes, str) and notes.strip() and notes != "发布者未填写更新日志。":
                warning = "旧缓存仅包含最新版日志；请检查更新以获取完整升级日志。\n\n" if version(latest) > version(current) else ""
                return warning + "版本 " + latest + " 更新公告\n\n" + notes
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
            self.status = ("未能取得完整更新日志，已保留离线公告，请稍后重试" if state == "skipped" else
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
