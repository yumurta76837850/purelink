"""
sentinel_crypto.py
XOR tabanlı hafif şifreleme kütüphanesi.
"""

import os
import struct
import time


def xor_bytes(data: bytes, key: bytes) -> bytes:
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def xor_encrypt(plaintext: str, key: str, encoding: str = "utf-8") -> bytes:
    return xor_bytes(plaintext.encode(encoding), key.encode(encoding))


def xor_decrypt(ciphertext: bytes, key: str, encoding: str = "utf-8") -> str:
    return xor_bytes(ciphertext, key.encode(encoding)).decode(encoding)


def derive_key(password: str, salt: bytes, iterations: int = 1000) -> bytes:
    key = (password + salt.hex()).encode()
    for _ in range(iterations):
        key = bytes(key[i] ^ key[(i + 1) % len(key)] for i in range(len(key)))
    return key


def generate_salt(length: int = 16) -> bytes:
    return os.urandom(length)


class KeyRotator:
    def __init__(self, base_key: str, rotate_every: int = 10):
        self.base_key     = base_key
        self.rotate_every = rotate_every
        self._counter     = 0

    def _current_key(self) -> str:
        step = self._counter // self.rotate_every
        return f"{self.base_key}:rot{step}"

    def encrypt(self, plaintext: str) -> bytes:
        key = self._current_key()   # önce key'i al
        self._counter += 1          # sonra artır
        return xor_encrypt(plaintext, key)

    def decrypt(self, ciphertext: bytes) -> str:
        key = self._current_key()
        self._counter += 1
        return xor_decrypt(ciphertext, key)

    @property
    def counter(self) -> int:
        return self._counter


class DataMasker:
    def __init__(self, key: str):
        self.key = key

    def mask(self, data: str) -> str:
        return xor_encrypt(data, self.key).hex()

    def unmask(self, masked: str) -> str:
        return xor_decrypt(bytes.fromhex(masked), self.key)

    def mask_fields(self, record: dict, fields: list) -> dict:
        result = dict(record)
        for field in fields:
            if field in result:
                result[field] = self.mask(str(result[field]))
        return result


HEADER_FORMAT = ">BHQ"
HEADER_SIZE   = struct.calcsize(HEADER_FORMAT)


def pack_header(version: int = 1, flags: int = 0) -> bytes:
    ts_ms = int(time.time() * 1000)
    return struct.pack(HEADER_FORMAT, version, flags, ts_ms)


def unpack_header(raw: bytes) -> dict:
    if len(raw) < HEADER_SIZE:
        raise ValueError(f"Başlık en az {HEADER_SIZE} byte olmalı.")
    version, flags, ts_ms = struct.unpack(HEADER_FORMAT, raw[:HEADER_SIZE])
    return {"version": version, "flags": flags, "timestamp_ms": ts_ms}


def build_packet(payload: str, key: str, version: int = 1) -> bytes:
    return pack_header(version=version) + xor_encrypt(payload, key)


def parse_packet(packet: bytes, key: str) -> dict:
    header_data = unpack_header(packet)
    plaintext   = xor_decrypt(packet[HEADER_SIZE:], key)
    return {**header_data, "payload": plaintext}
