"""外联 URL 守卫测试（Mimosa 安全约束验收项）。"""
from __future__ import annotations

import ipaddress
import socket

import pytest

from astroforge.utils.url_guard import UrlGuardError, validate_external_url


def _addrinfo(ip: str):
    addr = ipaddress.ip_address(ip)
    family = socket.AF_INET6 if addr.version == 6 else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, 443))]


def test_rejects_non_http_scheme():
    with pytest.raises(UrlGuardError):
        validate_external_url("ftp://example.com/file")
    with pytest.raises(UrlGuardError):
        validate_external_url("file:///etc/passwd")


def test_rejects_localhost_and_local_domain():
    with pytest.raises(UrlGuardError):
        validate_external_url("http://localhost:8420/api")
    with pytest.raises(UrlGuardError):
        validate_external_url("http://myhost.local/x")


@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.9", "169.254.1.1", "::1", "fe80::1"],
)
def test_rejects_private_and_reserved_ips(ip, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _addrinfo(ip))
    with pytest.raises(UrlGuardError):
        validate_external_url("https://evil.example.com/x")


def test_accepts_public_ip(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _addrinfo("93.184.216.34"))
    assert validate_external_url("https://example.com/x?a=1") == "https://example.com/x?a=1"


def test_rejects_dns_failure(monkeypatch):
    def _fail(*a, **k):
        raise socket.gaierror("boom")

    monkeypatch.setattr(socket, "getaddrinfo", _fail)
    with pytest.raises(UrlGuardError):
        validate_external_url("https://nope.invalid/")


def test_rejects_empty():
    with pytest.raises(UrlGuardError):
        validate_external_url("")
