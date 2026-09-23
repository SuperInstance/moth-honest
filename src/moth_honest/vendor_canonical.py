# Vendored from SuperInstance/moth-ledger @ e95c786 via moth-corpus
# via moth-honest (canonical.py).
# The canonical recipe both independent durability stacks converged on:
# sorted keys, minimal separators, UTF-8 bytes.
from __future__ import annotations

import json
from typing import Any


class CanonicalError(ValueError):
    """Raised when a value cannot be represented canonically."""


def canonical_dumps(obj: Any) -> bytes:
    try:
        return json.dumps(
            obj, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalError(f"not canonically serializable: {exc}") from exc


def canonical_equal(a: Any, b: Any) -> bool:
    return canonical_dumps(a) == canonical_dumps(b)
