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
CURRENT_NOTES = 'Windows 0.3.41 — 封面恢复与下载体验修订\n\n发布日期：2026-10-30\n\nWindows 0.3.40 → 0.3.41。保留原更新公钥，可保留现有配置、下载队列和漫画文件。Android 正式版保持 0.6.25。\n\n• 进入软件时优先恢复已保存的下载小封面，下载中的任务也保存预览；后台继续检查源图，减少先空白、再逐张显示的问题。\n• 下载期间可导出、删除其他已下载漫画的文件、移除记录或删除章节；仅拦截与目标漫画冲突的任务，其他下载继续。\n• 阅读页码“当前页/总页数”移到底部中央，工具栏隐藏后仍显示；下载列表显示所有运行任务的总实时速度。\n• 取消仅因下载速度慢而触发的整任务重连，保留无进度恢复、请求超时、失败重试和暂停续传。\n• 下载失败后直接显示具体原因；设置中可打开当前保存目录。\n\n验证：业务源码与最新已验证 Windows 本地修订一致；沿用封面恢复 24 项源码及 24 项冻结模块检查、文件操作 40 项相关回归与 7 项冻结模块检查，以及页码/速度、失败原因、目录入口和慢速检测的既有专项验证。添加下载多行输入的普通/窄窗口 15 项实际 Tk 检查正常。本次重新构建并核验冻结模块、版本及公告、完整 ZIP、源码包、SHA-256 和原公钥签名更新清单；未重复无关功能测试或进行真实网站下载测速。\n\n使用：暂停下载并退出旧程序，完整解压 ZIP 后运行 JMBatch.exe，保留同目录依赖文件。无需清空下载或删除用户配置。\n'


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
        self.settings_button = None
        self.downloading, self.ready = False, None
        self.download_started = False
        self.download_fraction = None
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
            from ui_common import notice
            notice(self.app.root,"更新完成")
            try:
                self.seen_path.write_text(VERSION, encoding="utf-8")
            except OSError:
                pass
        if self.automatic and self.repo:
            self.check()

    def show_and_check(self):
        """Check once, then offer the already discovered update."""
        if self.ready or self.downloading:
            self.confirm_update()
        elif self.latest:
            self.confirm_update()
        else:
            self.manual = True
            self.check()

    def bind_settings_button(self, button):
        self.settings_button = button
        button.configure(command=self.show_and_check)
        self.refresh()

    def confirm_update(self):
        import tkinter as tk
        from tkinter import ttk
        from ui_common import modal, actions, BG, ACCENT
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            self.refresh()
            return
        if not self.latest and not self.ready:
            return
        owner = getattr(self.app, 'settings_window', None)
        if owner is None or not owner.winfo_exists():
            owner = self.app.root
        window, body = modal(owner, blur=True)
        self.dialog = window
        content = ttk.Frame(body, height=142, style='Card.TFrame')
        content.pack(fill='x')
        content.pack_propagate(False)
        self.update_title = ttk.Label(content, anchor='center', justify='center', wraplength=380,
                                      font=('Microsoft YaHei UI', 12, 'bold'))
        self.update_title.pack(fill='x', expand=True)
        self.progress_area = ttk.Frame(content, style='Card.TFrame')
        ttk.Style(window).configure('Update.Horizontal.TProgressbar', background=ACCENT, troughcolor=BG,
                                    lightcolor=ACCENT, darkcolor=ACCENT, bordercolor=BG, borderwidth=0, thickness=8)
        self.progress_bar = ttk.Progressbar(self.progress_area, maximum=100, style='Update.Horizontal.TProgressbar')
        self.progress_bar.pack(fill='x', pady=(4, 12))
        self.status_var = tk.StringVar(value=self.status)
        ttk.Label(self.progress_area, textvariable=self.status_var, anchor='center', justify='center',
                  wraplength=380).pack(fill='x')
        row = actions(body, '确认', '取消', self.download, self.close_update)
        self.download_button, self.dismiss_button = row.winfo_children()
        window.bind('<Escape>', lambda e: self.close_update())
        window.protocol('WM_DELETE_WINDOW', self.close_update)
        self.refresh()

    def close_update(self):
        if self.downloading:
            self.cancel.set()
            self.status = "正在取消下载，请稍候…"
            self.refresh()
        elif self.dialog is not None and self.dialog.winfo_exists():
            self.progress_bar.stop()
            self.dialog.destroy()

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
        from ui_common import notice
        owner=getattr(self.app,'settings_window',None)
        if owner is None or not owner.winfo_exists():owner=self.app.root
        if self.latest:
            if getattr(self,"manual",False):self.confirm_update()
            else:notice(self.app.root,"检测到新版本 "+self.latest["version"])
        elif getattr(self,"manual",False):notice(owner,self.status)
        self.manual=False

    def refresh(self):
        self.app.update_button.configure(text="发现新版 " + self.latest["version"] if self.latest else "软件更新")
        action_text = "检查中…" if self.checking else "更新" if self.latest or self.downloading or self.ready else "检查更新"
        if self.settings_button is not None and self.settings_button.winfo_exists():
            self.settings_button.configure(text=action_text, state="disabled" if self.checking else "normal")
        if self.dialog is not None and self.dialog.winfo_exists():
            active = self.download_started or self.downloading or self.ready
            target = self.latest['version'] if self.latest else ''
            self.update_title.configure(text=("更新 " + target if active else "检测到新版本 " + target + "\n是否更新"))
            if active:
                self.update_title.pack_configure(expand=False, pady=(0, 10))
                self.progress_area.pack(fill='x')
            self.status_var.set(self.status)
            indeterminate = self.downloading and self.download_fraction is None
            mode = 'indeterminate' if indeterminate else 'determinate'
            if str(self.progress_bar['mode']) != mode:
                self.progress_bar.stop()
                self.progress_bar.configure(mode=mode)
                if indeterminate:
                    self.progress_bar.start(20)
            if not indeterminate:
                self.progress_bar.configure(value=100 if self.ready else self.download_fraction or 0)
            self.download_button.configure(state="disabled" if self.downloading or self.checking else "normal",
                                           text="下载中…" if self.downloading else "安装并重启" if self.ready else "重试" if self.download_started else "确认")
            self.dismiss_button.configure(text="取消下载" if self.downloading else "关闭" if active else "取消",
                                          state="disabled" if self.downloading and self.cancel.is_set() else "normal")
        if self.notes_window is not None and self.notes_window.winfo_exists():
            self.notes_status_var.set(self.status)
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
        ttk.Button(actions, text="关闭", command=window.destroy).pack(side="right")
        self.refresh()

    def download(self):
        from tkinter import messagebox
        from core import VERSION
        from update_install import prepare, launch_helper
        if self.checking:
            return
        if self.downloading:
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
        self.download_started = True
        self.download_fraction = None
        self.cancel.clear()
        self.status = "正在准备更新…"
        release = dict(self.latest)
        def worker():
            try:
                ready = prepare(self.app.home, release, VERSION, self.cancel,
                                lambda s: self.download_events.put(("progress", s)),
                                lambda n, total: self.download_events.put(("bytes", (n, total))))
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
                    if not self.cancel.is_set():
                        self.status = value
                        self.download_fraction = None
                elif kind == "bytes":
                    self.download_fraction = min(100, max(0, value[0] * 100 / value[1]))
                elif kind == "ready":
                    self.downloading = False
                    self.ready = value
                    self.status = "更新包校验通过，可安装并重启。"
                else:
                    self.downloading = False
                    self.status = "已取消更新下载，可点击重试。" if self.cancel.is_set() else "更新未完成：" + value
        except queue.Empty:
            pass
        self.refresh()
        if self.downloading:
            self.app.root.after(100, self.poll_download)
