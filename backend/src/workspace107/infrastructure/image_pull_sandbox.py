"""Run Apptainer in an isolated network namespace, with only a Unix proxy relay.

Invoked by ``unshare --user --map-root-user --net``. Even clients that bypass
HTTP_PROXY for loopback have no route to the host or its private services.
"""

from __future__ import annotations

import asyncio
import fcntl
import os
import socket
import struct
import sys
from urllib.parse import urlsplit


async def main() -> int:
    # The fresh namespace has only lo, initially down; CAP_NET_ADMIN is scoped
    # to this new user/network namespace, never the host namespace.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
        request = struct.pack("16sH14s", b"lo", 0x1 | 0x8 | 0x40, b"")
        fcntl.ioctl(control, 0x8914, request)  # SIOCSIFFLAGS: UP, LOOPBACK, RUNNING
    socket_path, *command = sys.argv[1:]

    async def relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream = None
        tasks = []
        try:
            remote, upstream = await asyncio.open_unix_connection(socket_path)

            async def copy(source, target):
                while data := await source.read(65536):
                    target.write(data)
                    await target.drain()

            tasks = [
                asyncio.create_task(copy(reader, upstream)),
                asyncio.create_task(copy(remote, writer)),
            ]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if upstream:
                upstream.close()
            writer.close()

    async with await asyncio.start_server(relay, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        original = urlsplit(os.environ["HTTPS_PROXY"])
        proxy = f"http://{original.username}:{original.password}@127.0.0.1:{port}"
        environment = dict(os.environ)
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            environment[name] = proxy
        process = await asyncio.create_subprocess_exec(*command, env=environment)
        return await process.wait()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
