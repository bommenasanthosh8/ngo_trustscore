"""Utilities package."""
import hashlib


def compute_sha256(content: bytes) -> str:
    """Compute hex SHA-256 hash of byte contents."""
    return hashlib.sha256(content).hexdigest()
