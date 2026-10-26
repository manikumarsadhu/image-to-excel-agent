"""Document fingerprint helpers for duplicate detection."""

from __future__ import annotations

import hashlib

from models.document import DocumentFingerprint


def fingerprint_from_bytes(content: bytes, *, source_filename: str = "") -> DocumentFingerprint:
    """
    Build a stable fingerprint from file bytes and optional filename.

    Filename is mixed in so identical image bytes uploaded under different names
    remain distinguishable when desired; callers can pass empty filename for
    content-only hashing.
    """
    hasher = hashlib.sha256()
    hasher.update(content)
    if source_filename:
        hasher.update(source_filename.strip().lower().encode("utf-8"))
    return DocumentFingerprint(value=hasher.hexdigest())
