"""
tests/test_crypto.py — sentinel_crypto modülü için unit testler
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sentinel_core.sentinel_crypto import (
    xor_bytes,
    xor_encrypt,
    xor_decrypt,
    derive_key,
    generate_salt,
    KeyRotator,
    DataMasker,
    pack_header,
    unpack_header,
    build_packet,
    parse_packet,
    HEADER_SIZE,
)


# ──────────────────────────────────────────────
# xor_bytes
# ──────────────────────────────────────────────

class TestXorBytes:
    def test_basic(self):
        result = xor_bytes(b"\x00\xFF", b"\xFF")
        assert result == b"\xFF\x00"

    def test_self_inverse(self):
        data = b"merhaba dunya"
        key  = b"key"
        assert xor_bytes(xor_bytes(data, key), key) == data

    def test_cyclic_key(self):
        data   = b"ABCABC"
        key    = b"ABC"
        result = xor_bytes(data, key)
        assert result == xor_bytes(data, key * 2)

    def test_empty(self):
        assert xor_bytes(b"", b"key") == b""

    def test_single_byte_key(self):
        data   = bytes(range(16))
        key    = b"\xAB"
        result = xor_bytes(data, key)
        assert all(r == (i ^ 0xAB) for i, r in enumerate(result))


# ──────────────────────────────────────────────
# xor_encrypt / xor_decrypt
# ──────────────────────────────────────────────

class TestXorEncryptDecrypt:
    def test_roundtrip(self):
        plain = "Sentinel güvenli veri"
        key   = "gizlianahtar"
        assert xor_decrypt(xor_encrypt(plain, key), key) == plain

    def test_different_keys_differ(self):
        plain = "test verisi"
        enc1  = xor_encrypt(plain, "key1")
        enc2  = xor_encrypt(plain, "key2")
        assert enc1 != enc2

    def test_returns_bytes(self):
        assert isinstance(xor_encrypt("test", "key"), bytes)

    def test_unicode(self):
        plain = "merhaba dünya 🔐"
        key   = "anahtar"
        assert xor_decrypt(xor_encrypt(plain, key), key) == plain

    def test_long_data(self):
        plain = "A" * 10_000
        key   = "uzunanahtar123"
        assert xor_decrypt(xor_encrypt(plain, key), key) == plain


# ──────────────────────────────────────────────
# derive_key / generate_salt
# ──────────────────────────────────────────────

class TestKeyDerivation:
    def test_salt_length(self):
        salt = generate_salt(16)
        assert len(salt) == 16

    def test_salt_random(self):
        assert generate_salt(16) != generate_salt(16)

    def test_derive_deterministic(self):
        salt = b"sabit_salt_12345"
        k1   = derive_key("parola", salt, iterations=10)
        k2   = derive_key("parola", salt, iterations=10)
        assert k1 == k2

    def test_derive_different_passwords(self):
        salt = generate_salt()
        k1   = derive_key("parola1", salt, iterations=10)
        k2   = derive_key("parola2", salt, iterations=10)
        assert k1 != k2

    def test_derive_different_salts(self):
        k1 = derive_key("parola", b"salt1", iterations=10)
        k2 = derive_key("parola", b"salt2", iterations=10)
        assert k1 != k2


# ──────────────────────────────────────────────
# KeyRotator
# ──────────────────────────────────────────────

class TestKeyRotator:
    def test_counter_increments(self):
        r = KeyRotator("base", rotate_every=5)
        r.encrypt("test")
        assert r.counter == 1

    def test_same_window_consistent(self):
        r1 = KeyRotator("base", rotate_every=5)
        r2 = KeyRotator("base", rotate_every=5)
        enc = r1.encrypt("merhaba")
        dec = r2.decrypt(enc)
        assert dec == "merhaba"

    def test_rotation_changes_key(self):
        # rotate_every=1 → her şifrelemede step değişir
        # step = counter // rotate_every, yani 0//1=0, 1//1=1 → farklı key
        r = KeyRotator("base", rotate_every=1)
        enc1 = r.encrypt("sentinel_rotation_test_123")
        enc2 = r.encrypt("sentinel_rotation_test_123")
        assert enc1 != enc2, "Farklı rotasyon adımları farklı çıktı üretmeli"


# ──────────────────────────────────────────────
# DataMasker
# ──────────────────────────────────────────────

class TestDataMasker:
    def setup_method(self):
        self.masker = DataMasker("test_key_42")

    def test_mask_unmask(self):
        original = "test@example.com"
        masked   = self.masker.mask(original)
        assert self.masker.unmask(masked) == original

    def test_mask_returns_hex(self):
        masked = self.masker.mask("data")
        assert all(c in "0123456789abcdef" for c in masked)

    def test_mask_fields(self):
        record = {"id": 1, "email": "x@y.com", "name": "Ali"}
        result = self.masker.mask_fields(record, ["email"])
        assert result["name"] == "Ali"
        assert result["id"]   == 1
        assert result["email"] != "x@y.com"

    def test_mask_fields_recoverable(self):
        record = {"email": "gizli@ornek.com"}
        masked = self.masker.mask_fields(record, ["email"])
        assert self.masker.unmask(masked["email"]) == "gizli@ornek.com"

    def test_missing_field_ignored(self):
        record = {"name": "Ali"}
        result = self.masker.mask_fields(record, ["email"])
        assert result == {"name": "Ali"}


# ──────────────────────────────────────────────
# Paket Başlığı
# ──────────────────────────────────────────────

class TestPacketHeader:
    def test_header_size(self):
        assert HEADER_SIZE == 11

    def test_pack_unpack(self):
        raw    = pack_header(version=2, flags=0b101)
        parsed = unpack_header(raw)
        assert parsed["version"] == 2
        assert parsed["flags"]   == 0b101
        assert parsed["timestamp_ms"] > 0

    def test_short_header_raises(self):
        with pytest.raises(ValueError):
            unpack_header(b"\x00" * 5)

    def test_build_parse_packet(self):
        payload = "api_key=12345"
        key     = "sentinel"
        packet  = build_packet(payload, key)
        result  = parse_packet(packet, key)
        assert result["payload"] == payload
        assert result["version"] == 1
