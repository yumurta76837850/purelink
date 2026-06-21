# sentinel-core

Zero-dependency async network security and encryption library for Python.

```bash
pip install sentinel-core
```

## Modüller

- `sentinel_crypto` — XOR şifreleme, key rotation, veri maskeleme
- `network` — Async TCP client/server, health check
- `logger` — Thread-safe renkli logger, performans ölçümü

## Hızlı Başlangıç

```python
from sentinel_core import xor_encrypt, xor_decrypt, DataMasker
from sentinel_core import SentinelClient, check_hosts
from sentinel_core import get_logger, time_execution

# Şifreleme
enc = xor_encrypt("gizli veri", "anahtar")
dec = xor_decrypt(enc, "anahtar")

# PII Maskeleme
masker = DataMasker("key42")
safe = masker.mask_fields({"email": "x@y.com", "name": "Ali"}, ["email"])

# Health Check
import asyncio
results = asyncio.run(check_hosts([("8.8.8.8", 53)]))

# Async Client
async def main():
    async with SentinelClient("127.0.0.1", 9000) as client:
        response = await client.send(b"merhaba")

# Logger
log = get_logger("myapp")
log.info("Başladı", extra={"port": 9000})

@time_execution(logger=log)
def heavy():
    ...
```

## Gereksinimler

- Python 3.11+
- Sıfır dış bağımlılık
