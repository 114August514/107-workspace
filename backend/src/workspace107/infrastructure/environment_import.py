"""Bounded, credential-free SIF import using the installed Apptainer runtime."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shutil
import signal
import sys
import tempfile
from pathlib import Path

import httpx

from ..domain.environment_source import validate_image_source
from ..domain.errors import ValidationFailed
from ..domain.ports.environment_import import ImportProgress
from ..domain.ports.storage import StoragePort
from .public_image_proxy import PublicImageProxy


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class RemoteEnvironmentImporter:
    def __init__(self, storage: StoragePort, *, max_bytes: int, timeout: float) -> None:
        self.storage = storage
        self.max_bytes = max_bytes
        self.timeout = timeout

    async def import_image(
        self, source_uri: str, expected_sha256: str, progress: ImportProgress
    ) -> dict[str, object]:
        source_uri = validate_image_source(source_uri)
        try:
            async with asyncio.timeout(self.timeout):
                with tempfile.TemporaryDirectory(prefix="workspace107-image-") as directory:
                    root = Path(directory)
                    output = root / "image.sif"
                    # OCI layers and TLS overhead have a separate, bounded wire budget.
                    async with PublicImageProxy(self.max_bytes * 3) as proxy:
                        if source_uri.startswith("https://"):
                            await progress("downloading", "正在下载 SIF 环境文件")
                            await self._download(source_uri, output, proxy.url)
                        else:
                            converting = source_uri.startswith("docker://")
                            await progress(
                                "converting" if converting else "downloading",
                                "正在拉取 OCI 镜像并转换为 SIF"
                                if converting
                                else "正在拉取 SIF 环境文件",
                            )
                            async with await proxy.unix_listener(str(root / "proxy.sock")):
                                await self._pull(source_uri, output, root, proxy)
                    if output.is_symlink() or not output.is_file():
                        raise ValidationFailed("镜像导入没有生成 SIF 文件")
                    size = output.stat().st_size
                    if not 0 < size <= self.max_bytes:
                        raise ValidationFailed("环境文件为空或超过平台大小上限")
                    digest = await asyncio.to_thread(file_digest, output)
                    if expected_sha256 and digest != expected_sha256.lower():
                        raise ValidationFailed("导入文件的 SHA-256 与预期摘要不一致")
                    locator = await self.storage.write_blob_file(output)
                    return {
                        "locator": locator,
                        "sha256": digest,
                        "size": size,
                        "source_uri": source_uri,
                        "source_digest": "",
                        "architecture": "x86_64",
                    }
        except TimeoutError as exc:
            raise ValidationFailed("镜像导入超时，请稍后重试或上传已构建的 SIF") from exc
        except (httpx.HTTPError, OSError) as exc:
            # Do not expose URLs containing redirected credentials or subprocess environment.
            raise ValidationFailed("镜像下载失败：请确认公开地址可访问，且未指向内部网络") from exc

    async def _download(self, uri: str, output: Path, proxy: str) -> None:
        async with (
            httpx.AsyncClient(
                proxy=proxy, trust_env=False, follow_redirects=True, max_redirects=5, timeout=30
            ) as client,
            client.stream("GET", uri, headers={"Accept-Encoding": "identity"}) as response,
        ):
            response.raise_for_status()
            length = response.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > self.max_bytes):
                raise ValidationFailed("环境文件超过平台大小上限")
            size = 0
            with output.open("wb") as stream:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ValidationFailed("环境文件超过平台大小上限")
                    await asyncio.to_thread(stream.write, chunk)

    async def _pull(self, uri: str, output: Path, root: Path, proxy: PublicImageProxy) -> None:
        executable = shutil.which("apptainer")
        limit = shutil.which("prlimit")
        unshare = shutil.which("unshare")
        if not executable or not limit or not unshare:
            raise ValidationFailed(
                "平台缺少 Apptainer、prlimit 或 unshare，无法拉取镜像；请联系管理员"
            )
        for name in ("home", "cache", "tmp"):
            (root / name).mkdir()
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(root / "home"),
            "LANG": "C.UTF-8",
            "TMPDIR": str(root / "tmp"),
            "APPTAINER_TMPDIR": str(root / "tmp"),
            "APPTAINER_CACHEDIR": str(root / "cache"),
            "APPTAINER_DISABLE_CACHE": "true",
            "HTTP_PROXY": proxy.url,
            "HTTPS_PROXY": proxy.url,
            "http_proxy": proxy.url,
            "https_proxy": proxy.url,
            "NO_PROXY": "",
            "no_proxy": "",
        }
        with (root / "pull.log").open("wb") as log:
            process = await asyncio.create_subprocess_exec(
                limit,
                f"--fsize={self.max_bytes}",
                f"--cpu={int(self.timeout) + 1}",
                "--",
                unshare,
                "--user",
                "--map-root-user",
                "--net",
                sys.executable,
                "-m",
                "workspace107.infrastructure.image_pull_sandbox",
                str(root / "proxy.sock"),
                executable,
                "pull",
                "--disable-cache",
                "--arch",
                "amd64",
                str(output),
                uri,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                env=environment,
                cwd=root,
                start_new_session=True,
            )
            waiter = asyncio.create_task(process.wait())
            try:
                while process.returncode is None:
                    try:
                        await asyncio.wait_for(asyncio.shield(waiter), 0.5)
                    except TimeoutError:
                        total = await asyncio.to_thread(directory_size, root)
                        if total > self.max_bytes * 3 or proxy.received > proxy.max_bytes:
                            raise ValidationFailed("镜像拉取或转换超过平台空间上限") from None
                if process.returncode != 0:
                    raise ValidationFailed(
                        "镜像拉取或转换失败：请确认镜像存在、可公开访问且支持 x86_64；"
                        "平台必须支持非特权网络命名空间隔离，仅允许公网 HTTPS 来源"
                    )
            finally:
                if process.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
                await waiter


def directory_size(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        with contextlib.suppress(FileNotFoundError):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
    return total
