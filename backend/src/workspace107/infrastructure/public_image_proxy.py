"""Ephemeral HTTPS CONNECT proxy: public IPs only, pinned DNS, bounded traffic.

Both the HTTP downloader and Apptainer use this proxy, including registry auth
and redirected blob downloads. No application or host proxy credentials leak
into subprocesses. CONNECT resolves once and connects to that numeric address.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import ipaddress
import secrets
import socket
from urllib.parse import urlsplit


def is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and not (
            isinstance(address, ipaddress.IPv6Address) and (address.sixtofour or address.teredo)
        )
    )


async def public_addresses(host: str, port: int) -> list[str]:
    if port != 443:
        raise ValueError("only HTTPS port 443 is allowed")
    records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not is_public_address(address) for address in addresses):
        raise ValueError("destination is not a public address")
    return addresses


class PublicImageProxy:
    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self.received = 0
        self.rejected = False
        self._token = secrets.token_urlsafe(32)
        self._authorization = "Basic " + base64.b64encode(f"import:{self._token}".encode()).decode()
        self._tasks: set[asyncio.Task] = set()
        self._slots = asyncio.Semaphore(16)

    async def __aenter__(self) -> PublicImageProxy:
        self._server = await asyncio.start_server(self._accept, "127.0.0.1", 0, limit=8192)
        port = self._server.sockets[0].getsockname()[1]
        self.url = f"http://import:{self._token}@127.0.0.1:{port}"
        return self

    async def unix_listener(self, path: str) -> asyncio.Server:
        return await asyncio.start_unix_server(self._accept, path, limit=8192)

    async def __aexit__(self, *_: object) -> None:
        self._server.close()
        await self._server.wait_closed()
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.create_task(self._serve(reader, writer))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream = None
        try:
            async with self._slots, asyncio.timeout(30):
                header = (await reader.readuntil(b"\r\n\r\n")).decode("ascii")
                lines = header.split("\r\n")
                method, authority, protocol = lines[0].split(" ")
                headers = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
                auth = next(
                    (v.strip() for k, v in headers.items() if k.lower() == "proxy-authorization"),
                    "",
                )
                if (
                    method != "CONNECT"
                    or protocol != "HTTP/1.1"
                    or not secrets.compare_digest(auth, self._authorization)
                ):
                    raise ValueError("invalid proxy request")
                url = urlsplit("https://" + authority)
                if (
                    not url.hostname
                    or url.username
                    or url.password
                    or url.path
                    or url.query
                    or url.fragment
                ):
                    raise ValueError("invalid CONNECT authority")
                addresses = await public_addresses(url.hostname, url.port or 443)
                last_error: OSError | None = None
                for address in addresses:
                    try:
                        remote, upstream = await asyncio.open_connection(address, 443)
                        break
                    except OSError as exc:
                        last_error = exc
                if upstream is None:
                    raise last_error or OSError("cannot connect")
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
            await self._tunnel(reader, writer, remote, upstream)
        except asyncio.CancelledError:
            raise
        except (
            ValueError,
            OSError,
            TimeoutError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
        ):
            self.rejected = True
            with contextlib.suppress(OSError):
                writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                await writer.drain()
        finally:
            if upstream:
                upstream.close()
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()

    async def _tunnel(self, client_reader, client_writer, remote_reader, remote_writer) -> None:
        async def copy(reader, writer, incoming: bool) -> None:
            while chunk := await reader.read(65536):
                if incoming:
                    self.received += len(chunk)
                    if self.received > self.max_bytes:
                        raise ValueError("download exceeds byte budget")
                writer.write(chunk)
                await writer.drain()

        tasks = [
            asyncio.create_task(copy(client_reader, remote_writer, False)),
            asyncio.create_task(copy(remote_reader, client_writer, True)),
        ]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
