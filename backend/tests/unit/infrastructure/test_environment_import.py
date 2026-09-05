"""Public image import: network boundaries and exact, bounded content."""

import asyncio
import hashlib
import socket

import httpx
import pytest

from workspace107.domain.environment_source import validate_image_source
from workspace107.domain.errors import ValidationFailed
from workspace107.infrastructure.environment_import import RemoteEnvironmentImporter
from workspace107.infrastructure.public_image_proxy import PublicImageProxy, public_addresses
from workspace107.infrastructure.storage.local import LocalStorage


@pytest.mark.parametrize(
    "uri",
    [
        "http://example.com/a.sif",
        "https://127.0.0.1/a.sif",
        "https://[::1]/a",
        "https://a:b@example.com/a",
        "https://example.com:22/a",
        "https://example.com/a?token=private",
        "docker://user:password@registry/image",
        "file:///tmp/a.sif",
        "docker://alpine;id",
        "https://localhost/a",
        "docker://alpine\n--help",
    ],
)
def test_rejects_nonpublic_or_credentialed_source(uri):
    with pytest.raises(ValidationFailed):
        validate_image_source(uri)


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.com/a.sif",
        "docker://python:3.12",
        "oras://ghcr.io/org/image:tag",
        "library://user/collection/image:tag",
        "docker://alpine@sha256:" + "a" * 64,
    ],
)
def test_supported_image_references(uri):
    assert validate_image_source(uri) == uri


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["169.254.169.254"],
        ["10.0.0.1"],
        ["224.0.0.1"],
        ["::1"],
        ["::ffff:127.0.0.1"],
        ["93.184.216.34", "192.168.0.1"],
    ],
)
async def test_proxy_rejects_private_or_mixed_dns(monkeypatch, addresses):
    async def lookup(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", lookup)
    with pytest.raises(ValueError):
        await public_addresses("external.example", 443)


async def test_proxy_rejects_internal_connect_without_opening_upstream(monkeypatch):
    called = []

    async def resolve(host, port):
        called.append((host, port))
        raise ValueError("private address")

    monkeypatch.setattr("workspace107.infrastructure.public_image_proxy.public_addresses", resolve)
    async with PublicImageProxy(1024) as proxy:
        async with httpx.AsyncClient(proxy=proxy.url, trust_env=False) as client:
            with pytest.raises(httpx.ProxyError):
                await client.get("https://internal.example/file.sif")
        assert proxy.rejected
    assert called == [("internal.example", 443)]


async def test_import_streams_and_pins_exact_bytes(tmp_path, monkeypatch):
    content = b"SIF test content" * 100
    storage = LocalStorage(tmp_path / "cas")
    importer = RemoteEnvironmentImporter(storage, max_bytes=4096, timeout=5)
    real_client = httpx.AsyncClient

    def client(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["proxy"].startswith("http://import:")
        return real_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content))
        )

    monkeypatch.setattr(httpx, "AsyncClient", client)
    stages = []

    async def progress(stage, message):
        stages.append(stage)

    candidate = await importer.import_image(
        "https://example.com/image.sif", hashlib.sha256(content).hexdigest(), progress
    )
    assert candidate["locator"] == hashlib.sha256(content).hexdigest()
    assert await storage.read_blob(candidate["locator"]) == content
    assert candidate["size"] == len(content)
    assert stages == ["downloading"]
    with pytest.raises(ValidationFailed, match="SHA-256"):
        await importer.import_image("https://example.com/image.sif", "a" * 64, progress)
    importer.max_bytes = 10
    with pytest.raises(ValidationFailed, match="上限"):
        await importer.import_image("https://example.com/image.sif", "", progress)


async def test_import_timeout(tmp_path, monkeypatch):
    importer = RemoteEnvironmentImporter(LocalStorage(tmp_path), max_bytes=1024, timeout=0.01)

    async def slow(*args):
        await asyncio.sleep(1)

    monkeypatch.setattr(importer, "_download", slow)
    with pytest.raises(ValidationFailed, match="超时"):
        await importer.import_image("https://example.com/image.sif", "", slow)


async def test_proxy_pins_numeric_address_and_rechecks_redirect_destination(monkeypatch):
    from workspace107.infrastructure import public_image_proxy

    calls = []
    connections = []
    real_connect = asyncio.open_connection

    async def lookup(host, port):
        calls.append(host)
        if host == "redirect.internal":
            raise ValueError("private redirect")
        return ["93.184.216.34"]

    class Writer:
        def close(self):
            pass

        def write(self, data):
            pass

        async def drain(self):
            pass

    async def connect(host, port):
        connections.append((host, port))
        reader = asyncio.StreamReader()
        reader.feed_eof()
        return reader, Writer()

    monkeypatch.setattr(public_image_proxy, "public_addresses", lookup)
    async with PublicImageProxy(1024) as proxy:
        from urllib.parse import urlsplit

        endpoint = urlsplit(proxy.url)
        monkeypatch.setattr(asyncio, "open_connection", connect)
        for host, status in [("public.example", b"200"), ("redirect.internal", b"403")]:
            reader, writer = await real_connect(endpoint.hostname, endpoint.port)
            writer.write(
                (
                    f"CONNECT {host}:443 HTTP/1.1\r\n"
                    f"Proxy-Authorization: {proxy._authorization}\r\n\r\n"
                ).encode()
            )
            await writer.drain()
            assert status in await reader.readline()
            writer.close()
            await writer.wait_closed()
    assert calls == ["public.example", "redirect.internal"]
    assert connections == [("93.184.216.34", 443)]


async def test_pull_reports_missing_platform_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "workspace107.infrastructure.environment_import.shutil.which", lambda _: None
    )
    importer = RemoteEnvironmentImporter(LocalStorage(tmp_path / "cas"), max_bytes=1024, timeout=5)

    async def progress(*args):
        pass

    with pytest.raises(ValidationFailed, match="平台缺少"):
        await importer.import_image("docker://alpine:3.22", "", progress)


@pytest.mark.parametrize("cancel", [False, True])
async def test_pull_timeout_or_cancel_kills_process_group_and_cleans_files(
    tmp_path, monkeypatch, cancel
):
    import signal
    from pathlib import Path

    stopped = asyncio.Event()
    launched = asyncio.Event()
    invocations = []
    killed = []

    class Process:
        pid = 424242
        returncode = None

        async def wait(self):
            await stopped.wait()
            return self.returncode

    process = Process()

    async def launch(*args, **kwargs):
        invocations.append((args, kwargs))
        launched.set()
        return process

    def kill_group(pid, sig):
        killed.append((pid, sig))
        process.returncode = -9
        stopped.set()

    monkeypatch.setattr(
        "workspace107.infrastructure.environment_import.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr("workspace107.infrastructure.environment_import.os.killpg", kill_group)
    importer = RemoteEnvironmentImporter(
        LocalStorage(tmp_path / "cas"), max_bytes=1024, timeout=0.05 if not cancel else 5
    )

    async def progress(*args):
        pass

    task = asyncio.create_task(importer.import_image("docker://alpine:3.22", "", progress))
    await launched.wait()
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(ValidationFailed, match="超时"):
            await task
    assert killed == [(424242, signal.SIGKILL)]
    args, options = invocations[0]
    assert "--net" in args and "--map-root-user" in args
    assert options["start_new_session"] is True
    assert not await asyncio.to_thread(Path(options["cwd"]).exists)
    assert set(options["env"]) == {
        "PATH",
        "HOME",
        "LANG",
        "TMPDIR",
        "APPTAINER_TMPDIR",
        "APPTAINER_CACHEDIR",
        "APPTAINER_DISABLE_CACHE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "NO_PROXY",
        "no_proxy",
    }
