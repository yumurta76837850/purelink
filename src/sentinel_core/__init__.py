"""
sentinel-core — Hafif ağ güvenliği ve şifreleme kütüphanesi
Sıfır dış bağımlılık.
"""

from .sentinel_crypto import (
    xor_encrypt,
    xor_decrypt,
    xor_bytes,
    derive_key,
    generate_salt,
    KeyRotator,
    DataMasker,
    pack_header,
    unpack_header,
    build_packet,
    parse_packet,
)

from .logger import (
    SentinelLogger,
    PerformanceTracker,
    get_logger,
    time_execution,
    Level,
)

from .network import (
    check_host,
    check_hosts,
    SentinelServer,
    SentinelClient,
    Packet,
    ConnectionResult,
)

__version__ = "0.1.0"
__all__ = [
    # crypto
    "xor_encrypt", "xor_decrypt", "xor_bytes",
    "derive_key", "generate_salt",
    "KeyRotator", "DataMasker",
    "pack_header", "unpack_header", "build_packet", "parse_packet",
    # logger
    "SentinelLogger", "PerformanceTracker", "get_logger", "time_execution", "Level",
    # network
    "check_host", "check_hosts", "SentinelServer", "SentinelClient",
    "Packet", "ConnectionResult",
]
