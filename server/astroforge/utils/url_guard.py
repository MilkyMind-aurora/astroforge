"""外联 URL 安全守卫（方案 8.4 硬性条款的 URL 版）。

规则：仅允许 http/https；发请求前校验 host，拒绝 localhost、环回、
私有与保留地址。服务核心对用户输入 URL 发起的任何请求必须先过此关。
注意：本模块与 modules/_shared/url_guard.py 为分环境部署的同源拷贝，修改需同步。
爬虫模块按业务设计需要访问任意目标站，守卫在其入口做 scheme/解析校验。
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


class UrlGuardError(ValueError):
    """URL 未通过外联安全校验。"""


def _check_ip(ip: str) -> None:
    addr = ipaddress.ip_address(ip)
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    ):
        raise UrlGuardError(f"禁止访问内网/保留地址: {ip}")


def validate_external_url(url: str) -> str:
    """校验用户提供的 URL 可被安全外联，返回规范化 URL；不通过则抛 UrlGuardError。"""
    if not url or not isinstance(url, str):
        raise UrlGuardError("URL 不能为空")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UrlGuardError(f"仅允许 http/https 协议，收到: {parsed.scheme or '(空)'}")
    host = parsed.hostname
    if not host:
        raise UrlGuardError("URL 缺少主机名")
    if host.lower() in {"localhost"} or host.endswith(".local"):
        raise UrlGuardError(f"禁止访问本机域名: {host}")
    try:
        infos = socket.getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP
        )
    except socket.gaierror as exc:
        raise UrlGuardError(f"主机名解析失败: {host}") from exc
    for info in infos:
        _check_ip(info[4][0])
    return parsed.geturl()
