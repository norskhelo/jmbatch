"""Download presentation; image estimates never include retry traffic."""
import math
import time


def format_size(value):
    value = max(0, value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


def format_speed(value):
    return format_size(value) + "/s"


def percent(done, total, status):
    if status == "done":
        return 100.0
    # Reserve completion for the verified, saved PDF/ZIP.
    return min(99.9, max(0, done) * 100 / total) if total > 0 else 0.0


def progress_text(done, total, status):
    return f"{percent(done, total, status):.1f}% · {done}/{total if total else '?'} 张"


def size_text(done, total, image_bytes, result_bytes, status):
    if status == "done":
        return "漫画大小 " + (format_size(result_bytes) if result_bytes > 0 else "未知（旧记录）")
    if done <= 0 or image_bytes <= 0:
        return "已下载图片 0 B · 预计大小 计算中"
    if total > done:
        return f"已下载图片 {format_size(image_bytes)} / 预计大小 {format_size(image_bytes * total / done)}"
    return "图片大小 " + format_size(image_bytes)


def eta_text(status, stage, done, total, cached, elapsed, speed, now=None):
    if status != "running":
        return {"done": "下载完成", "paused": "已暂停", "resetting": "重连后重新估算",
                "failed": "下载失败", "cancelled": "已取消"}.get(status, "等待下载")
    if stage == "cache":
        return "正在校验已有图片，完成后继续下载"
    if total > 0 and done >= total or stage in ("verify", "export"):
        return "正在校验 / 导出，预计完成时间待定"
    if stage == "page_retry":
        return "正在重试失败页，预计完成时间待定"
    if stage != "download" or done <= cached or total <= 0 or elapsed <= 0 or speed <= 0:
        return "预计完成时间：计算中"
    remaining = max(1, math.ceil((total - done) * elapsed / (done - cached)))
    if remaining > 365 * 86400:
        return "预计完成时间：计算中"
    now = time.time() if now is None else now
    clock = time.strftime("%m-%d %H:%M:%S", time.localtime(now + remaining))
    duration = f"{remaining} 秒" if remaining < 60 else (f"{math.ceil(remaining / 60)} 分钟" if remaining < 3600 else f"{remaining / 3600:.1f} 小时")
    return f"预计完成 {clock}（约剩 {duration}，导出另计）"
