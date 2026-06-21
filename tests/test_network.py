"""
tests/test_network.py — network modülü için async unit testler
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sentinel_core.network import (
    check_host,
    check_hosts,
    SentinelClient,
    SentinelServer,
    Packet,
    ConnectionResult,
    HEADER_SIZE,
)


# ──────────────────────────────────────────────
# Packet
# ──────────────────────────────────────────────

class TestPacket:
    def test_roundtrip(self):
        p   = Packet(version=1, flags=0, timestamp_ms=9999, payload=b"test")
        raw = p.to_bytes()
        p2  = Packet.from_bytes(raw)
        assert p2.version      == 1
        assert p2.flags        == 0
        assert p2.timestamp_ms == 9999
        assert p2.payload      == b"test"

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            Packet.from_bytes(b"\x00" * (HEADER_SIZE - 1))

    def test_empty_payload(self):
        p = Packet(version=1, flags=0, timestamp_ms=1000, payload=b"")
        assert Packet.from_bytes(p.to_bytes()).payload == b""

    def test_age_ms_positive(self):
        import time
        ts = int(time.time() * 1000) - 500
        p  = Packet(version=1, flags=0, timestamp_ms=ts, payload=b"x")
        assert p.age_ms >= 400

    def test_large_payload(self):
        payload = b"X" * 4000
        p       = Packet(version=1, flags=0, timestamp_ms=0, payload=payload)
        assert Packet.from_bytes(p.to_bytes()).payload == payload


# ──────────────────────────────────────────────
# ConnectionResult
# ──────────────────────────────────────────────

class TestConnectionResult:
    def test_str_reachable(self):
        r = ConnectionResult("10.0.0.1", 80, True, 12.5)
        assert "✓" in str(r)
        assert "12.5" in str(r)

    def test_str_unreachable(self):
        r = ConnectionResult("10.0.0.1", 80, False, -1, "timeout")
        assert "✗" in str(r)
        assert "timeout" in str(r)


# ──────────────────────────────────────────────
# check_host
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestCheckHost:
    async def test_refused_port(self):
        result = await check_host("127.0.0.1", 19999, timeout=1.0)
        assert result.reachable is False
        assert result.error == "connection refused"

    async def test_timeout(self):
        # 192.0.2.x TEST-NET — route edilmez, timeout verir
        result = await check_host("192.0.2.1", 9999, timeout=0.5)
        assert result.reachable is False

    async def test_local_server(self):
        # Geçici sunucu aç, bağlantıyı test et
        server = await asyncio.start_server(
            lambda r, w: w.close(), "127.0.0.1", 19876
        )
        async with server:
            result = await check_host("127.0.0.1", 19876, timeout=2.0)
        assert result.reachable is True
        assert result.latency_ms >= 0


# ──────────────────────────────────────────────
# check_hosts
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestCheckHosts:
    async def test_multiple_results(self):
        targets = [
            ("127.0.0.1", 19991),
            ("127.0.0.1", 19992),
        ]
        results = await check_hosts(targets, timeout=1.0)
        assert len(results) == 2
        assert all(isinstance(r, ConnectionResult) for r in results)

    async def test_empty_targets(self):
        results = await check_hosts([], timeout=1.0)
        assert results == []

    async def test_concurrency_limit(self):
        targets = [("127.0.0.1", 20000 + i) for i in range(20)]
        results = await check_hosts(targets, timeout=0.5, max_concurrency=5)
        assert len(results) == 20


# ──────────────────────────────────────────────
# SentinelServer + SentinelClient
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestClientServer:
    async def test_echo(self):
        server = SentinelServer("127.0.0.1", 19100)
        await server.start()
        task = asyncio.create_task(server._server.serve_forever())
        await asyncio.sleep(0.05)

        async with SentinelClient("127.0.0.1", 19100) as client:
            response = await client.send(b"merhaba")
        assert response is not None
        assert response.payload == b"merhaba"

        await server.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_context_manager_closes(self):
        server = SentinelServer("127.0.0.1", 19101)
        await server.start()
        task = asyncio.create_task(server._server.serve_forever())
        await asyncio.sleep(0.05)

        client = SentinelClient("127.0.0.1", 19101)
        async with client:
            assert client._writer is not None
        # Context manager kapattıktan sonra writer None olmalı
        assert client._writer is None

        await server.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_send_without_connect_raises(self):
        client = SentinelClient("127.0.0.1", 19102)
        with pytest.raises(RuntimeError, match="connect"):
            await client.send(b"test")

    async def test_version_flags_preserved(self):
        server = SentinelServer("127.0.0.1", 19103)
        await server.start()
        task = asyncio.create_task(server._server.serve_forever())
        await asyncio.sleep(0.05)

        async with SentinelClient("127.0.0.1", 19103) as client:
            response = await client.send(b"data", version=2, flags=0b11)
        assert response.version == 2
        assert response.flags   == 0b11

        await server.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
