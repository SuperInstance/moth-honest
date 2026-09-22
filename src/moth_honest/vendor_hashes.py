# Vendored from SuperInstance/moth-ledger @ e95c786 via moth-corpus
# via moth-honest (hashes.py).
# Bytes-law: fnv1a-64 over UTF-8 bytes, never characters.
# Pinned: "café Δ 日本語" -> 0x24a555471370b18d (integer-equal to the
# spec's 0x024a555471370b18d; canonical string form is 64-bit padded).
from __future__ import annotations

import hashlib
from typing import Union

FNV1A64_OFFSET = 0xCBF29CE484222325
FNV1A64_PRIME = 0x100000001B3
MASK64 = 0xFFFFFFFFFFFFFFFF

PINNED_VECTORS = [
    (b"", 0xCBF29CE484222325),
    ("café Δ 日本語".encode("utf-8"), 0x24A555471370B18D),
    (b"hello", 0xA430D84680Aabd0B),
]


def fnv1a_64(data: Union[bytes, bytearray, memoryview]) -> int:
    h = FNV1A64_OFFSET
    for byte in bytes(data):
        h ^= byte
        h = (h * FNV1A64_PRIME) & MASK64
    return h


def fnv1a_64_hex(data: Union[bytes, bytearray, memoryview]) -> str:
    return f"{fnv1a_64(data):016x}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_pins() -> None:
    for raw, expected in PINNED_VECTORS:
        got = fnv1a_64(raw)
        if got != expected:
            raise AssertionError(f"bytes-law pin broken: {raw[:24]!r}")
