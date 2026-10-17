"""Bounded public release downloads; mirrors never change the signed identity."""
import http.client
import time
import urllib.error
import urllib.parse
import urllib.request

HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com", "github-releases.githubusercontent.com"}
MIRRORS = (("GitHub", ""), ("GHFast", "https://ghfast.top/"), ("GH-Proxy", "https://gh-proxy.com/"))


class DownloadFailure(OSError):
    """Only remote transport failures are eligible for the next route."""


def allowed_url(url, original=None):
    try:
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or p.username or p.password or p.port not in (None, 443) or p.fragment:
            return False
        if p.hostname in HOSTS:
            return True
        return bool(original and url in (prefix + original for _, prefix in MIRRORS[1:]))
    except ValueError:
        return False


def download_routes(url):
    p = urllib.parse.urlsplit(url)
    parts = p.path.split("/")
    if (p.scheme != "https" or p.netloc != "github.com" or p.query or p.fragment
            or len(parts) != 7 or parts[3:5] != ["releases", "download"]
            or any(not part or urllib.parse.unquote(part) in (".", "..")
                   or "/" in urllib.parse.unquote(part) or "\\" in urllib.parse.unquote(part)
                   for part in parts[1:])):
        raise ValueError("更新源必须是 GitHub Release 的固定附件地址")
    return [(name, prefix + url) for name, prefix in MIRRORS]


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, original=None):
        super().__init__()
        self.original = original

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl, self.original):
            raise ValueError("更新下载重定向到不可信地址，已阻止")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def network(call):
    try:
        return call()
    except (OSError, http.client.HTTPException) as error:
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        raise DownloadFailure("更新线路连接或读取失败") from error


def transfer(url, output, limit, cancel, progress=lambda n: None, route_notice=lambda name: None):
    routes = download_routes(url)
    start = output.tell()
    deadline = time.monotonic() + 1800

    def check():
        if cancel.is_set():
            raise InterruptedError("已取消更新下载")
        if time.monotonic() > deadline:
            raise TimeoutError("更新下载超时，请重试")

    for name, address in routes:
        check()
        # Local seek/write/flush errors must not be mistaken for a failed route.
        output.seek(start)
        output.truncate()
        route_notice(name)
        progress(0)
        request = urllib.request.Request(address, headers={"User-Agent": "JMBatch-Updater", "Accept-Encoding": "identity"})
        try:
            response = network(lambda: urllib.request.build_opener(SafeRedirect(url)).open(request, timeout=15))
            try:
                if response.status != 200:
                    raise DownloadFailure("更新服务器未返回文件")
                if "text/html" in response.headers.get("Content-Type", "").lower():
                    raise DownloadFailure("更新线路返回网页而非文件")
                try:
                    expected = int(response.headers.get("Content-Length", "-1"))
                except ValueError:
                    raise DownloadFailure("更新响应长度无效") from None
                if expected > limit:
                    raise ValueError("更新文件超过允许大小")
                total = 0
                while True:
                    check()
                    chunk = network(lambda: response.read(65536))
                    check()
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("更新文件超过允许大小")
                    output.write(chunk)
                    progress(total)
                if total == 0 or expected >= 0 and total != expected:
                    raise DownloadFailure("更新响应为空或下载不完整")
                output.flush()
                return
            finally:
                response.close()
        except DownloadFailure:
            check()
            output.seek(start)
            output.truncate()
    raise DownloadFailure("GitHub、GHFast、GH-Proxy 更新下载均失败，请检查网络后重试") from None
