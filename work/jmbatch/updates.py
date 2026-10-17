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
CURRENT_NOTES ="Windows 0.3.15 / Android 0.5.10 — 沉浸阅读\n\n阅读体验\n\n• 在软件内阅读时，轻点漫画区域即可隐藏阅读工具栏、页码状态栏和滚动条，只保留漫画；再次轻点恢复。\n• 工具栏以约 220 毫秒的滑动过渡收起或展开，Android 同时淡入淡出；动画中再次点击可平滑反向。Android 遵循系统动画开关，隐藏时同时收起系统状态栏与导航栏。\n• 滚动阅读和左右翻页均支持。轻点页面任何位置统一切换工具栏，左右滑动/拖动继续翻页；Windows 还可使用方向键、PageUp/PageDown 或滚轮，工具栏显示时仍可点击上一页/下一页。\n• 区分轻点、滑动和长按，Android 多指操作不触发工具栏切换。收起与恢复保留当前页，滚动模式的高度变化不重新解码漫画。\n• Windows 按 Esc 可恢复工具栏；Android 隐藏时按返回先恢复工具栏，再次返回退出阅读。\n\n版本与兼容性\n\n• Windows 0.3.14 → 0.3.15；Android 0.5.9 → 0.5.10（versionCode 510）。保留原应用包名、APK 签名证书及更新公钥。\n• 图片文件夹、ZIP、PDF，以及章节、收藏、书签、阅读进度与下载设置继续兼容。\n• 验证覆盖 Windows 实际阅读窗口和冻结成品、Android 宿主手势/动画/布局检查及原签名构建。未连接 Android 真机，宿主检查不代表手机视觉验收。\n"


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


def announcement_baseline(saved, seen, current, repo):
    """Keep one installed upgrade range across checks/restarts, scoped to its repo."""
    try:
        if (saved.get("repository") == repo and saved.get("installed_version") == current
                and version(saved["from_version"]) <= version(current)):
            return saved["from_version"]
    except (AttributeError, KeyError, ValueError, TypeError):
        pass
    try:
        if version(seen) > version(current):
            return current  # A downgrade is not an upgrade from an older cache.
    except (ValueError, TypeError):
        pass
    previous = []
    for candidate in (seen, saved.get("installed_version") if isinstance(saved, dict)
                      and saved.get("repository") == repo else None):
        try:
            if version(candidate) < version(current):
                previous.append(candidate)
        except (ValueError, TypeError):
            pass
    return max(previous, key=version) if previous else current


def announcement_text(bulletin, repo, current, local_notes, upgrade_from=None):
    upgrading = False
    try:
        upgrading = version(upgrade_from) < version(current)
    except (ValueError, TypeError):
        pass
    if upgrading:
        fallback = (f"本次升级 {upgrade_from} → {current} 的完整日志尚未获取，联网检查后补齐。\n\n"
                    + "本版更新日志\n\n" + local_notes)
    else:
        fallback = local_notes
    try:
        if bulletin.get("repository") == repo and version(bulletin["version"]) >= version(current):
            latest = bulletin["version"]
            if bulletin.get("history_schema") == 2:
                baseline = version(bulletin["from_version"])
                history = bulletin["history"]
                required_from = version(upgrade_from) if upgrading else version(current)
                if baseline > required_from or not isinstance(history, list) or not history:
                    return fallback
                previous = None
                for entry in history:
                    number = version(entry["version"])
                    if (number < baseline or number > version(latest)
                            or (previous is not None and number <= previous)
                            or not isinstance(entry["notes"], str)):
                        return fallback
                    previous = number
                if previous != version(latest):
                    return fallback
                if upgrading:
                    completed = [entry for entry in history
                                 if required_from < version(entry["version"]) <= version(current)]
                    if not completed or version(completed[-1]["version"]) != version(current):
                        return fallback
                    sections = [f"本次升级：{upgrade_from} → {current} 的全部更新（按版本升序）\n\n"
                                + "\n\n────────\n\n".join("版本 " + e["version"] + "\n\n" + e["notes"] for e in completed)]
                    pending = [entry for entry in history if version(entry["version"]) > version(current)]
                    if pending:
                        sections.append(f"可用更新：当前版本 {current} → 最新版本 {latest}\n\n"
                                        + "\n\n────────\n\n".join("版本 " + e["version"] + "\n\n" + e["notes"] for e in pending))
                    return "\n\n════════\n\n".join(sections)
                if version(latest) == version(current):
                    notes = history[-1]["notes"]
                    return local_notes if notes == "发布者未填写更新日志。" else "版本 " + latest + " 更新日志\n\n" + notes
                sections = ["版本 " + entry["version"] + "\n\n" + entry["notes"]
                            for entry in history if version(entry["version"]) > version(current)]
                return ("从当前版本 " + current + " → 最新版本 " + latest
                        + " 的全部更新（不含当前版，按版本升序）\n\n" + "\n\n────────\n\n".join(sections))
            if upgrading:
                return fallback  # A legacy one-release cache cannot prove the upgrade range.
            notes = bulletin.get("notes", "")
            if isinstance(notes, str) and notes.strip() and notes != "发布者未填写更新日志。":
                warning = "旧缓存仅包含最新版日志；请检查更新以获取完整升级日志。\n\n" if version(latest) > version(current) else ""
                return warning + "版本 " + latest + " 更新日志\n\n" + notes
    except (AttributeError, KeyError, ValueError, TypeError):
        pass
    return fallback


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
        self.notes_window = None
        self.downloading, self.ready = False, None
        self.checking = False
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
        self.status = "等待检查" if self.repo else "未设置更新来源"
        if settings != data:
            from core import atomic_json
            try:
                atomic_json(self.path, settings)
            except OSError:
                pass  # A read-only config must not prevent startup or downloads.
        from core import VERSION
        self.history_state_path = app.home / "update-announcement-state.json"
        try:
            saved = json.loads(self.history_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        try:
            seen = self.seen_path.read_text(encoding="utf-8").strip()
        except OSError:
            seen = ""
        self.upgrade_from = announcement_baseline(saved, seen, VERSION, self.repo)
        self.save_history_state()

    def save_history_state(self):
        from core import VERSION, atomic_json
        try:
            atomic_json(self.history_state_path, {"repository": self.repo,
                        "installed_version": VERSION, "from_version": self.upgrade_from})
        except OSError:
            pass

    def startup(self):
        from core import VERSION
        try:
            seen = self.seen_path.read_text(encoding="utf-8")
        except OSError:
            seen = ""
        if seen != VERSION:
            self.show_notes()
            try:
                self.seen_path.write_text(VERSION, encoding="utf-8")
            except OSError:
                pass
        if self.automatic and self.repo:
            self.check()

    def show_and_check(self):
        """An explicit user action checks even when automatic checks are off."""
        self.show()
        self.check()

    def check(self):
        if self.downloading or self.ready:
            return
        if self.checking:
            self.refresh()
            return
        if not self.repo:
            self.status = "请先填写更新仓库并保存，再点击检查更新"
            self.refresh()
            return
        if not self.checker.start(self.repo, self.upgrade_from, fetch_bulletin):
            self.status = "上次检查尚未结束，请稍后重试。"
            self.refresh()
            return
        self.checked_repo = self.repo
        self.checking = True
        self.latest = None
        self.status = "正在检查更新…"
        self.refresh()
        self.app.root.after(100, self.poll)

    def poll(self):
        result = self.checker.poll()
        if result is None:
            self.app.root.after(100, self.poll)
            return
        self.checking = False
        if self.repo == self.checked_repo:
            from core import VERSION, atomic_json
            state, bulletin = result
            self.latest = bulletin if bulletin and version(bulletin["version"]) > version(VERSION) else None
            if state == "ok" and bulletin and version(bulletin["version"]) >= version(VERSION):
                self.bulletin = bulletin
                try:
                    atomic_json(self.bulletin_path, bulletin)
                except OSError:
                    pass
            self.status = ("无法获取完整更新日志。已保留本地日志，请稍后重试。" if state == "skipped" else
                           "发现新版 " + self.latest["version"] if self.latest else "当前已是最新版本")
        else:
            self.status = "设置已保存，请点击检查更新" if self.repo else "未设置更新来源"
        self.refresh()

    def refresh(self):
        self.app.update_button.configure(text="发现新版 " + self.latest["version"] if self.latest else "软件更新")
        check_enabled = not (self.checking or self.downloading or self.ready)
        if self.dialog is not None and self.dialog.winfo_exists():
            self.status_var.set(self.status)
            self.check_button.configure(state="normal" if check_enabled else "disabled",
                                        text="检查中…" if self.checking else "检查更新")
            self.download_button.configure(state="normal" if not self.checking and (self.latest or self.downloading or self.ready) else "disabled",
                                           text="取消下载" if self.downloading else "安装并重启" if self.ready else "下载更新")
            self.replace_notes(self.announcement_area, self.notes_text())
        if self.notes_window is not None and self.notes_window.winfo_exists():
            self.notes_status_var.set(self.status)
            self.notes_check_button.configure(state="normal" if check_enabled else "disabled",
                                              text="检查中…" if self.checking else "检查更新")
            self.replace_notes(self.notes_area, self.notes_text())

    @staticmethod
    def replace_notes(area, text):
        if area.get("1.0", "end-1c") == text:
            return
        position = area.yview()[0]
        area.configure(state="normal")
        area.delete("1.0", "end")
        area.insert("1.0", text)
        area.configure(state="disabled")
        area.yview_moveto(position)

    def notes_text(self):
        from core import VERSION
        return announcement_text(self.bulletin, self.repo, VERSION, CURRENT_NOTES, self.upgrade_from)

    def show_notes(self):
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText
        if self.notes_window is not None and self.notes_window.winfo_exists():
            self.refresh()
            self.notes_window.lift()
            return
        window = self.notes_window = tk.Toplevel(self.app.root)
        window.title("更新日志")
        window.transient(self.app.root)
        self.notes_status_var = tk.StringVar(value=self.status)
        ttk.Label(window, textvariable=self.notes_status_var, wraplength=640, padding=12).pack(fill="x")
        area = self.notes_area = ScrolledText(window, width=76, height=24, wrap="word", padx=12, pady=12)
        area.pack(fill="both", expand=True)
        area.insert("1.0", self.notes_text())
        area.configure(state="disabled")

        actions = ttk.Frame(window, padding=12)
        actions.pack(fill="x")
        self.notes_check_button = ttk.Button(actions, text="检查更新", command=self.show_and_check)
        self.notes_check_button.pack(side="left")
        ttk.Button(actions, text="关闭", command=window.destroy).pack(side="right")
        self.refresh()

    def download(self):
        from tkinter import messagebox
        from core import VERSION
        from update_install import prepare, launch_helper
        if self.checking:
            return
        if self.downloading:
            self.cancel.set()
            self.status = "正在取消下载，请稍候…"
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
                    self.status = "更新包校验通过，可安装并重启。"
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
        ttk.Label(frame, text="更新来源（GitHub 用户名/仓库名，留空可停用更新检查）").pack(anchor="w", pady=(16, 6))
        repo_var = tk.StringVar(value=self.repo)
        ttk.Entry(frame, textvariable=repo_var, width=60).pack(fill="x")
        auto_var = tk.BooleanVar(value=self.automatic)
        ttk.Checkbutton(frame, text="启动时自动检查更新", variable=auto_var).pack(anchor="w", pady=12)
        self.status_var = tk.StringVar(value=self.status)
        ttk.Label(frame, textvariable=self.status_var).pack(anchor="w", pady=6)
        from tkinter.scrolledtext import ScrolledText
        ttk.Label(frame, text="更新日志（支持离线查看）").pack(anchor="w", pady=(8, 4))
        self.announcement_area = ScrolledText(frame, width=72, height=10, wrap="word")
        self.announcement_area.pack(fill="both", expand=True)
        ttk.Label(frame, text="修改更新来源后请先保存。关闭自动检查后，仍可手动检查。\n更新包通过签名和完整性校验后即可安装，安装时会暂停任务并重启应用。\n检查更新不会发送漫画编号或 Cookie。", justify="left").pack(anchor="w", pady=12)
        def save():
            if self.downloading or self.ready:
                messagebox.showinfo("更新进行中", "当前更新完成前不能更改仓库，请安装更新或重启程序。", parent=dialog)
                return
            try:
                repo = normalize_repo(repo_var.get())
                atomic_json(self.path, {"repository": repo, "automatic": auto_var.get(), "repository_default_v1": True})
                if repo != self.repo:
                    self.latest = None
                    self.upgrade_from = VERSION
                self.repo, self.automatic = repo, auto_var.get()
                self.save_history_state()
                if not self.checking:
                    self.status = "设置已保存" if repo else "未设置更新来源"
                self.refresh()
            except (ValueError, OSError) as error:
                messagebox.showerror("无法保存更新设置", str(error), parent=dialog)
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        ttk.Button(actions, text="保存", command=save).pack(side="left")
        self.check_button = ttk.Button(actions, text="检查更新", command=self.check)
        self.check_button.pack(side="left", padx=8)
        ttk.Button(actions, text="完整更新日志", command=self.show_notes).pack(side="left", padx=4)
        self.download_button = ttk.Button(actions, text="下载更新", command=self.download)
        self.download_button.pack(side="right")
        self.refresh()
