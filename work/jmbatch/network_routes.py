"""Bounded route failover; diagnostic text never includes request headers or URLs."""
from __future__ import annotations

import copy
import re
import socket
import ssl
from urllib.parse import urlsplit, urlunsplit


class HttpFailure(OSError):
    def __init__(self, code):
        self.status = code
        reason = {401: "需要登录或账号无权限", 403: "访问被拒绝", 404: "资源不存在", 429: "服务端限流，请降低线程数后稍后重试"}.get(code, "服务器请求失败")
        super().__init__(f"HTTP {code}：{reason}")


class BadResponse(OSError):
    pass


class RoutesExhausted(OSError):
    pass


def merge_hosts(primary, fallback):
    result = []
    for source, limit in ((primary, 8), (fallback, 16)):
        for host in source:
            if not isinstance(host, str):
                continue
            host = host.lower()
            if (len(host) <= 253 and ".." not in host and
                    re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", host) and host not in result):
                result.append(host)
            if len(result) >= limit:
                break
    return result


def failure_kind(error):
    for _ in range(8):
        if error is None:
            break
        if isinstance(error, HttpFailure):
            return "http"
        text = str(error).lower()
        if re.search(r"\[::\]|/0\.0\.0\.0(?::|\b)|0:0:0:0:0:0:0:0", text):
            return "address"
        code = getattr(error, "code", None)  # curl_cffi CurlECode
        if isinstance(error, socket.gaierror) or code in (5, 6):
            return "dns"
        if isinstance(error, ssl.SSLError) or code in (35, 51, 58, 60, 77, 80, 82, 83, 90, 91):
            return "tls"
        if isinstance(error, TimeoutError) or code == 28:
            return "timeout"
        if isinstance(error, ConnectionError) or code in (7, 55, 56):
            return "connect"
        if isinstance(error, BadResponse) or code in (18, 52):
            return "response"
        error = error.__cause__ or error.__context__
    return "other"


def failure_reason(error):
    return {
        "address": "连接目标出现未指定地址（:: / 0.0.0.0），可能与 DNS、代理或过滤设置有关",
        "dns": "DNS 解析失败，未取得服务器地址",
        "connect": "连接被拒绝、重置或网络不可达",
        "timeout": "连接或读取超时",
        "tls": "HTTPS 握手或证书校验失败（未关闭校验）",
        "response": "服务器响应为空、不完整或格式异常",
        "http": str(error) if isinstance(error, HttpFailure) else "HTTP 请求失败",
    }.get(failure_kind(error), "请求失败")


def run_routes(hosts, retries, stage, request, notice=lambda _: None, check=lambda: None):
    reasons, counts, skip = {}, {}, set()
    attempts, budget = 0, len(hosts) + max(0, min(5, retries))
    while attempts < budget:
        tried = False
        for host in hosts:
            if attempts >= budget:
                break
            if host in skip:
                continue
            check()
            tried = True
            attempts += 1
            if attempts > 1:
                notice(f"{stage}：切换/重试线路 {host}（请求 {attempts}/{budget}）")
            try:
                return request(host)
            except Exception as error:
                check()
                kind = failure_kind(error)
                if kind == "other" or isinstance(error, HttpFailure) and error.status < 500:
                    raise
                reasons[host] = failure_reason(error)
                counts[host] = counts.get(host, 0) + 1
                if kind in ("address", "dns", "tls", "connect"):
                    skip.add(host)
        if not tried:
            break
    check()
    details = "\n".join(f"{host} ×{counts[host]}：{reason}" for host, reason in reasons.items())
    raise RoutesExhausted(
        f"{stage}：所有可用线路均失败（{len(reasons)} 条，{attempts} 次请求）。\n{details}\n"
        "请检查应用联网权限，切换网络对比，并核对 DNS、代理及过滤设置。"
        "仅凭此错误不能确定是设备故障；重试保留已下载图片。") from None


def make_strategy(notice=lambda _: None):
    """Use jmcomic's supported request strategy hook, including session initialization."""
    def strategy(client, request=None, url=None, is_image=False, **kwargs):
        from jmcomic import JmModuleConfig
        if request is None:
            client._jmbatch_preferred = None
            return
        if url.startswith("/"):
            hosts = merge_hosts(client.domain_list, JmModuleConfig.DOMAIN_API_LIST)
            preferred = client._jmbatch_preferred
            if preferred in hosts:
                hosts.remove(preferred)
                hosts.insert(0, preferred)
            client.domain_list = hosts
            make_url = lambda host: client.of_api_url(url, host)
        else:
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port:
                raise ValueError("下载地址无效：必须使用 HTTPS 域名地址")
            hosts = merge_hosts([parsed.hostname], JmModuleConfig.DOMAIN_IMAGE_LIST if is_image else [])
            make_url = lambda host: urlunsplit(("https", host, parsed.path, parsed.query, ""))

        def send(host):
            options = copy.deepcopy(kwargs)
            client.update_request_with_specify_domain(options, None if is_image else host, is_image)
            timeout = options.get("timeout", client.get_meta_data("timeout", 25))
            if isinstance(timeout, (int, float)):
                options["timeout"] = (min(8, timeout), timeout)
            response = request(make_url(host), **options)
            if response.status_code != 200:
                raise HttpFailure(response.status_code)
            try:
                response = client.raise_if_resp_should_retry(response, is_image)
            except Exception:
                raise BadResponse("服务器响应格式异常") from None
            if not is_image:
                client._jmbatch_preferred = host
            return response

        try:
            return run_routes(hosts, client.retry_times, "图片下载" if is_image else "漫画接口", send,
                              (lambda _: None) if is_image else notice)
        except RoutesExhausted:
            JmModuleConfig.DOMAIN_API_UPDATED_LIST = None
            raise
    return strategy
