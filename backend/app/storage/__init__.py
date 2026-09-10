"""Storage abstraction layer (local / safe keys)."""
from app.storage.service import (
    LocalStorageService,
    storage_service,
    sanitize_filename,
    validate_file,
    generate_sha256,
    generate_storage_key,
    MAX_FILE_SIZE_BYTES,
    ALLOWED_MIME_TYPES,
    ALLOWED_EXTENSIONS,
)

# For backward compatibility with existing tests
LocalStorage = LocalStorageService

__all__ = [
    "LocalStorageService",
    "LocalStorage",
    "storage_service",
    "sanitize_filename",
    "validate_file",
    "generate_sha256",
    "generate_storage_key",
    "MAX_FILE_SIZE_BYTES",
    "ALLOWED_MIME_TYPES",
    "ALLOWED_EXTENSIONS",
]
