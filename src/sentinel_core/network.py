"""
network.py — Asenkron bağlantı ve protokol katmanı
Async context manager desteği ile.
"""

import asyncio
import struct
import time
from dataclasses import dataclass
from typing import Optional

HEADER_FORMAT = ">BHQ"
HEADER_SIZE   = struct.calcsize(HEADER_FORMAT)  # 11 byte


# ──────────────────────────────────────────────
# 1. Veri Yapıları
# ──────────────────────────────────────────────

@dataclass
class ConnectionResult:
    host: str
    port: int
    reachable: bool
    latency_ms: float
    error: Optional[str] = None

    def __str__(self) -> str:
        if self.reachable:
            return f"✓ {self.host}:{self.port} ({self.latency_ms}ms)"
        return f"✗ {self.host}:{self.port} [{self.error}]"


@dataclass
class Packet:
    version: int
    flags: int
    timestamp_ms: int
    payload: bytes

    def to_bytes(self) -> bytes:
        header = struct.pack(HEADER_FORMAT, self.version, self.flags, self.timestamp_ms)
        return header + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "Packet":
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Veri çok kısa: {len(data)} byte (min {HEADER_SIZE})")
        version, flags, ts_ms = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        return cls(version=version, flags=flags, timestamp_ms=ts_ms, payload=data[HEADER_SIZE:])

    @property
    def age_ms(self) -> float:
        return int(time.time() * 1000) - self.timestamp_ms


# ──────────────────────────────────────────────
# 2. Health Check
# ──────────────────────────────────────────────

async def check_host(host: str, port: int, timeout: float = 3.0) -> ConnectionResult:
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        latency_ms = (time.perf_counter() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return ConnectionResult(host=host, port=port, reachable=True, latency_ms=round(latency_ms, 2))
    except asyncio.TimeoutError:
        return ConnectionResult(host=host, port=port, reachable=False, latency_ms=-1, error="timeout")
    except ConnectionRefusedError:
        return ConnectionResult(host=host, port=port, reachable=False, latency_ms=-1, error="connection refused")
    except Exception as e:
        return ConnectionResult(host=host, port=port, reachable=False, latency_ms=-1, error=str(e))


async def check_hosts(
    targets: list[tuple[str, int]],
    timeout: float = 3.0,
    max_concurrency: int = 50
) -> list[ConnectionResult]:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def bounded(host, port):
        async with semaphore:
            return await check_host(host, port, timeout)

    return await asyncio.gather(*[bounded(h, p) for h, p in targets])


# ──────────────────────────────────────────────
# 3. SentinelClient — Async Context Manager
# ──────────────────────────────────────────────

class SentinelClient:
    """
    Kullanım:
        async with SentinelClient("127.0.0.1", 9000) as client:
            response = await client.send(b"merhaba")
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9000, timeout: float = 5.0):
        self.host    = host
        self.port    = port
        self.timeout = timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def connect(self):
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=self.timeout
        )

    async def close(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._reader = None
            self._writer = None

    async def __aenter__(self) -> "SentinelClient":
        await self.connect()
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def send(self, payload: bytes, version: int = 1, flags: int = 0) -> Optional[Packet]:
        if not self._writer:
            raise RuntimeError("Önce connect() çağırın veya async with kullanın.")
        packet = Packet(
            version=version,
            flags=flags,
            timestamp_ms=int(time.time() * 1000),
            payload=payload
        )
        self._writer.write(packet.to_bytes())
        await self._writer.drain()
        raw = await asyncio.wait_for(self._reader.read(4096), timeout=self.timeout)  # type: ignore[union-attr]
        return Packet.from_bytes(raw) if raw else None


# ──────────────────────────────────────────────
# 4. SentinelServer — Async Context Manager
# ──────────────────────────────────────────────

class SentinelServer:
    """
    Kullanım:
        async with SentinelServer("127.0.0.1", 9000) as server:
            await server.serve_forever()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host    = host
        self.port    = port
        self._server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        try:
            raw = await asyncio.wait_for(reader.read(4096), timeout=10.0)
            if raw:
                packet = Packet.from_bytes(raw)
                print(f"[Server] {addr} → {len(packet.payload)}B, v{packet.version}")
                writer.write(packet.to_bytes())
                await writer.drain()
        except Exception as e:
            print(f"[Server] Hata {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self):
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        print(f"[Server] Dinleniyor: {self.host}:{self.port}")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def __aenter__(self) -> "SentinelServer":
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.stop()


# ──────────────────────────────────────────────
# 5. Hızlı Test
# ──────────────────────────────────────────────

async def _demo():
    print("=== Health Check ===")
    results = await check_hosts([("8.8.8.8", 53), ("127.0.0.1", 9999)], timeout=2.0)
    for r in results:
        print(f"  {r}")

    print("\n=== Async Context Manager ===")
    server = SentinelServer()
    await server.start()
    server_task = asyncio.create_task(server._server.serve_forever())
    await asyncio.sleep(0.1)

    async with SentinelClient("127.0.0.1", 9000) as client:
        response = await client.send(b"context manager calisiyor!")
        if response:
            print(f"Yanıt: {response.payload.decode()} (age: {response.age_ms}ms)")

    await server.stop()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(_demo())
