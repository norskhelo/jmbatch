"""Platform-independent queue models, validation, errors and export logic."""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
import zipfile
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "0.2.4"
ZIP_LAYOUT_VERSION = 3
MAX_TASKS = 2000


def parse_ids(text: str) -> list[str]:
    text = re.sub(r"\s*([-~～—–至])\s*", "-", text.strip())
    tokens = re.split(r"[\s,，;；、]+", text)
    result: dict[str, None] = {}
    for token in filter(None, tokens):
        match = re.fullmatch(r"(?:JM)?(\d{3,10})(?:-(?:JM)?(\d{3,10}))?", token, re.I)
        if not match:
            raise ValueError(f"无法识别：{token[:60]}。请输入编号或区间，例如 123456、123460-123465。")
        start = int(match[1])
        end = int(match[2]) if match[2] else start
        if start <= 0 or end < start:
            raise ValueError(f"区间无效：{token}。起始编号必须大于 0，且不能大于结束编号。")
        if end - start + 1 > MAX_TASKS:
            raise ValueError(f"单次最多添加 {MAX_TASKS} 个编号，请缩小区间。")
        for value in range(start, end + 1):
            result[str(value)] = None
            if len(result) > MAX_TASKS:
                raise ValueError(f"单次最多添加 {MAX_TASKS} 个编号。")
    if not result:
        raise ValueError("请先输入至少一个编号。")
    return list(result)


@dataclass
class Settings:
    output: str = field(default_factory=lambda: str(Path.home() / "Downloads" / "JMBatch"))
    format: str = "images"
    threads: int = 8
    concurrent_tasks: int = 2
    timeout: int = 25
    request_retries: int = 2
    auto_reset: bool = True
    slow_kbps: int = 30
    slow_seconds: int = 90
    stall_seconds: int = 180
    max_resets: int = 3
    keep_images: bool = False
    numeric_filename: bool = False
    flat_zip: bool = False

    def validate(self):
        if self.format not in ("images", "pdf", "zip"):
            raise ValueError("输出格式必须是图片、PDF 或 ZIP。")
        for name, low, high, label in [
            ("concurrent_tasks", 1, 4, "同时下载任务数"),
            ("threads", 1, 16, "图片线程数"), ("timeout", 5, 120, "请求超时"),
            ("request_retries", 0, 5, "请求重试次数"), ("slow_kbps", 0, 10240, "慢速阈值"),
            ("slow_seconds", 15, 600, "慢速观察窗口"), ("stall_seconds", 30, 1800, "无进度超时"),
            ("max_resets", 0, 10, "最大重置次数"),
        ]:
            value = getattr(self, name)
            if not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"{label}必须在 {low}–{high} 之间。")
        if not self.output.strip() or not Path(self.output).is_absolute():
            raise ValueError("请选择完整的绝对输出路径。")
        return self


@dataclass
class Task:
    album_id: str
    settings: dict
    key: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"
    title: str = "等待获取标题"
    done: int = 0
    total: int = 0
    cached: int = 0
    speed: float = 0
    image_bytes: int = 0
    result_bytes: int = 0
    resets: int = 0
    phase: str = "排队中"
    error: str = ""
    result: str = ""
    metrics: dict = field(default_factory=dict)
    created: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self):
        return asdict(self)


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def sanitize_error(value: str, cookie: str = "") -> str:
    text = str(value)
    for part in cookie.split(";"):
        if "=" in part:
            secret = part.partition("=")[2].strip()
            if secret:
                text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"https?://[^\s\]<>\"']+", "[请求地址已隐藏]", text)
    text = re.sub(r"(?i)(cookie|authorization|token)\s*[:=][^\n]+", r"\1=[已隐藏]", text)
    return text[:2500]


def explain_error(exc: Exception, cookie: str = "") -> str:
    raw = sanitize_error(str(exc), cookie)
    name = type(exc).__name__
    lower = (name + " " + raw).lower()
    if "所有可用线路均失败" in raw:
        return raw
    if isinstance(exc, FileExistsError):
        tip = "同名成品已存在，未覆盖。请移动已有文件、更换目录或关闭纯编号命名后重试。"
    elif isinstance(exc, PermissionError):
        tip = "输出目录不可写，或文件正被占用。请更换目录并关闭占用文件的程序。"
    elif isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:
        tip = "磁盘空间不足。请释放空间或更换输出目录。"
    elif "missingalbum" in lower or "不存在" in lower or "404" in lower:
        tip = "未找到该编号，或当前账号无权访问。请检查编号及访问权限。"
    elif "429" in lower:
        tip = "服务端限流（429）。请稍后重试，并降低图片线程数。"
    elif any(word in lower for word in ("403", "401", "avs", "登录", "login", "forbidden")):
        tip = "访问被拒绝或需要登录。请检查 Cookie 是否有效及账号访问权限。"
    elif any(word in lower for word in ("timeout", "timed out", "超时")):
        tip = "网络请求超时。请检查网络或代理，并适当增大请求超时。"
    elif any(word in lower for word in ("connect", "resolve", "ssl", "curl", "proxy")):
        tip = "网络连接失败。请检查网络、代理、DNS 或证书状态。"
    elif "partialdownload" in lower:
        tip = "部分章节或图片下载失败，未生成成品。可重试并复用已验证图片。"
    else:
        tip = "任务未完成。下方为具体原因；修正后可选中任务重试。"
    return f"{tip}\n{name}: {raw}"


class SpeedWatch:
    """Rates use completed image bytes, not network-layer transfer bytes."""
    def __init__(self, settings: Settings, now: float):
        self.settings = settings
        self.start = now
        self.last_progress = now
        self.samples = deque([(now, 0)])
        self.last_bytes = 0

    def sample(self, now: float, received: int) -> tuple[float, str | None]:
        if received > self.last_bytes:
            self.last_progress = now
        self.last_bytes = received
        self.samples.append((now, received))
        window = self.settings.slow_seconds
        while len(self.samples) > 2 and self.samples[1][0] <= now - window:
            self.samples.popleft()
        recent = next((s for s in self.samples if s[0] >= now - 10), self.samples[0])
        speed = max(0, received - recent[1]) / max(1, now - recent[0])
        if not self.settings.auto_reset:
            return speed, None
        if now - self.last_progress >= self.settings.stall_seconds:
            return speed, f"连续 {self.settings.stall_seconds} 秒没有完成新图片或元数据进度"
        elapsed = now - self.samples[0][0]
        if now - self.start >= 30 + window and elapsed >= window:
            avg = max(0, received - self.samples[0][1]) / max(1, elapsed)
            if avg < self.settings.slow_kbps * 1024:
                return speed, f"最近 {window} 秒平均落盘速度 {avg / 1024:.1f} KB/s，低于 {self.settings.slow_kbps} KB/s"
        return speed, None


def verify_image(path: Path):
    from PIL import Image
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()


def safe_name(text: str) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(text)).strip(" .")
    return (text or "未命名")[:60]


def task_cache(task: dict) -> Path:
    key = task["key"]
    if not re.fullmatch(r"[0-9a-f]{32}", key):
        raise ValueError("任务标识无效，拒绝使用缓存路径。")
    return Path(task["settings"]["output"]).resolve() / ".jmbatch-work" / key


def clean_cache(task: dict):
    target = task_cache(task)
    parent = (Path(task["settings"]["output"]).resolve() / ".jmbatch-work").resolve()
    if target.is_symlink() or target.resolve().parent != parent:
        raise ValueError("缓存路径异常，未执行清理。")
    if target.exists():
        shutil.rmtree(target)


def export_images(task: dict, title: str, entries: list[dict], emit) -> Path:
    """Entries are ordered by chapter and page; output commit follows validation."""
    import img2pdf
    from pypdf import PdfReader

    output = Path(task["settings"]["output"])
    cache = task_cache(task)
    cache.mkdir(parents=True, exist_ok=True)
    if not entries:
        raise ValueError("没有可导出的图片，拒绝生成空文件。")
    paths = [Path(e["path"]) for e in entries]
    if len({str(p.resolve()) for p in paths}) != len(paths):
        raise ValueError("检测到重复图片路径，拒绝生成可能缺页的文件。")
    emit({"type": "phase", "phase": "verify", "message": "正在校验图片完整性"})
    for n, path in enumerate(paths, 1):
        verify_image(path)
        emit({"type": "export_progress", "message": f"校验图片 {n}/{len(paths)}"})
    need = int(sum(p.stat().st_size for p in paths) * 1.2) + 64 * 1024 ** 2
    if shutil.disk_usage(output).free < need:
        raise OSError(28, f"导出需要至少约 {need // 1024 ** 2} MB 可用空间。")
    fmt = task["settings"]["format"]
    numeric = task["settings"].get("numeric_filename", False)
    flat = task["settings"].get("flat_zip", False)
    chapter_count = len({entry["chapter"] for entry in entries})
    flatten_images = chapter_count == 1
    album_id = str(task["album_id"])
    if not re.fullmatch(r"[0-9]{1,10}", album_id):
        raise ValueError("编号无效，无法生成文件名。")
    final = output / (f"{album_id}.{fmt}" if numeric else f"JM{album_id}-{safe_name(title)}-{uuid.uuid4().hex[:8]}.{fmt}")
    if final.exists():
        raise FileExistsError(f"同名文件已存在：{final.name}，未覆盖。")
    temporary = cache / ("export.partial." + fmt)
    emit({"type": "phase", "phase": "export", "message": "正在合成 PDF" if fmt == "pdf" else "正在打包图片 ZIP"})
    if fmt == "pdf":
        with temporary.open("wb") as stream:
            img2pdf.convert(*map(str, paths), outputstream=stream, engine=img2pdf.Engine.internal)
        with temporary.open("rb") as stream:
            if len(PdfReader(stream).pages) != len(paths):
                raise ValueError("PDF 页数与图片数不一致，成品未保存。")
    else:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
            for n, (entry, path) in enumerate(zip(entries, paths), 1):
                name = f'{n:05d}{path.suffix.lower()}' if flatten_images else f'{entry["chapter"]:04d}/{entry["page"]:05d}{path.suffix.lower()}'
                archive.write(path, name)
                emit({"type": "export_progress", "message": f"打包图片 {n}/{len(paths)}"})
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or len(archive.infolist()) != len(paths):
                raise ValueError("ZIP 完整性校验失败，成品未保存。")
    # Windows rename fails atomically if the destination exists, including races.
    if os.name == "nt":
        os.rename(temporary, final)
    else:
        os.link(temporary, final)
        temporary.unlink()
    atomic_json(cache / "completed.json", {"path": str(final), "images": len(paths), "numeric_filename": numeric, "flat_zip": flat, "zip_layout_version": ZIP_LAYOUT_VERSION})
    return final
