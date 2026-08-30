# 安全守卫：外联 URL 校验（方案 8.4 硬性条款的 URL 版）
#
# 规则：仅允许 http/https；发请求前校验 host，拒绝 localhost、环回、
# 私有与保留地址。用于服务自身按用户输入发起的任意 URL 请求。
# 注意：本模块为 stdlib-only 独立拷贝（modules 与 server 分环境部署），
# 修改时需同步 server/astroforge/utils/url_guard.py。
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
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UrlGuardError(f"主机名解析失败: {host}") from exc
    for info in infos:
        _check_ip(info[4][0])
    return parsed.geturl()
