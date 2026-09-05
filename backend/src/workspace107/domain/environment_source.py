"""Public, credential-free image references accepted by environment import."""

import ipaddress
import re
from urllib.parse import urlsplit

from .errors import ValidationFailed


def validate_image_source(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 2048 or re.search(r"[\s\\\x00-\x1f]", value):
        raise ValidationFailed("请填写完整的公开镜像地址")
    scheme, sep, reference = value.partition("://")
    if not sep or scheme not in {"https", "docker", "oras", "library"} or not reference:
        raise ValidationFailed("支持 HTTPS SIF、docker://、oras://、library:// 镜像地址")
    if "?" in reference or "#" in reference:
        raise ValidationFailed("公开镜像地址不能包含查询参数或片段；不接受凭据链接")
    if scheme == "https":
        try:
            url = urlsplit(value)
            if not url.hostname or url.username or url.password or url.port not in {None, 443}:
                raise ValueError
            if not url.path or url.path == "/":
                raise ValueError
            host = url.hostname
        except ValueError as exc:
            raise ValidationFailed("请填写不带凭据、使用标准 HTTPS 端口的文件地址") from exc
    else:
        if not re.fullmatch(r"[A-Za-z0-9._:/@+-]+", reference):
            raise ValidationFailed("镜像引用包含无效字符")
        if "@" in reference and not re.fullmatch(r"[^@]+@sha256:[a-fA-F0-9]{64}", reference):
            raise ValidationFailed("镜像引用不能包含账号密码；摘要须使用 @sha256: 格式")
        host = reference.split("/", 1)[0].split(":", 1)[0]
    if host.lower() in {"localhost", "localhost.localdomain"} or host.lower().endswith(
        ".localhost"
    ):
        raise ValidationFailed("不允许导入本机或内部网络地址")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValidationFailed("不允许导入本机或内部网络地址")
    return value
