import os
import re
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Set, Tuple

# 25 MB max upload size
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

# Allowed MIME types and corresponding allowed extensions
ALLOWED_MIME_TYPES: Set[str] = {
    # Images
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    # Documents & Spreadsheets
    "application/pdf",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    # Videos
    "video/mp4",
    "video/quicktime",
    "video/webm",
}

ALLOWED_EXTENSIONS: Set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".heic",
    ".pdf", ".csv", ".xlsx", ".xls", ".doc", ".docx", ".txt",
    ".mp4", ".mov", ".webm",
}

# Dangerous extensions explicitly blocked regardless of content type
DISALLOWED_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".sh", ".bash", ".bin",
    ".py", ".pyc", ".js", ".ts", ".html", ".htm", ".php",
    ".jsp", ".asp", ".aspx", ".cgi", ".pl", ".vbs", ".jar",
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and filesystem attacks.
    Removes path components, replaces unsafe characters with underscores,
    and ensures a safe length.
    """
    if not filename:
        return "unnamed_file"

    # Strip directory components (both Unix and Windows)
    basename = os.path.basename(filename).replace("\\", "/").split("/")[-1]

    # Split name and extension
    name, ext = os.path.splitext(basename)
    ext = ext.lower().strip()

    # Sanitize name: keep only alphanumeric, dashes, underscores
    clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    # Collapse multiple underscores
    clean_name = re.sub(r"_+", "_", clean_name).strip("_")

    if not clean_name:
        clean_name = "file"

    # Limit base name length to 100 characters
    clean_name = clean_name[:100]

    # Clean extension
    clean_ext = re.sub(r"[^a-z0-9.]", "", ext)
    if not clean_ext.startswith(".") and clean_ext:
        clean_ext = f".{clean_ext}"

    return f"{clean_name}{clean_ext}"


def validate_file(filename: str, content_type: Optional[str], file_size: int) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded file size, extension, and MIME type.
    Returns (is_valid, error_message).
    """
    if file_size <= 0:
        return False, "File is empty."

    if file_size > MAX_FILE_SIZE_BYTES:
        return False, f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB."

    _, ext = os.path.splitext(filename.lower())

    if ext in DISALLOWED_EXTENSIONS:
        return False, f"File extension '{ext}' is not permitted for security reasons."

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File extension '{ext}' is not supported. Allowed formats: images (JPG, PNG, WEBP), documents (PDF, CSV, XLSX), videos (MP4, WEBM)."

    if content_type:
        normalized_mime = content_type.lower().split(";")[0].strip()
        # Some browsers send generic octet-stream for CSV/XLSX
        if normalized_mime != "application/octet-stream" and normalized_mime not in ALLOWED_MIME_TYPES:
            return False, f"Content-Type '{normalized_mime}' is not permitted."

    return True, None


def generate_sha256(content: bytes) -> str:
    """Generate SHA-256 hex digest for binary content."""
    return hashlib.sha256(content).hexdigest()


def generate_storage_key(project_id: uuid.UUID, evidence_id: uuid.UUID, sanitized_name: str) -> str:
    """
    Generate structured, safe storage key:
    evidence/{project_id}/{year}/{month}/{evidence_id}_{sanitized_name}
    """
    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%m")
    return f"evidence/{project_id}/{year}/{month}/{evidence_id}_{sanitized_name}"


class LocalStorageService:
    """
    Local filesystem storage provider with path isolation and safe key management.
    """
    def __init__(self, base_dir: str = "./evidence_storage"):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, storage_key: str, content: bytes) -> str:
        """
        Save content using storage_key as relative path inside base_dir.
        Returns absolute filepath.
        """
        full_path = os.path.abspath(os.path.join(self.base_dir, storage_key))
        # Enforce path containment
        if not full_path.startswith(self.base_dir):
            raise ValueError("Storage key attempts directory traversal.")

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return full_path

    def get_absolute_path(self, storage_key_or_path: str) -> Optional[str]:
        """
        Resolve storage key or file path to absolute path, ensuring isolation.
        Returns None if file does not exist or violates path containment.
        """
        # If it's already an absolute path inside base_dir
        if os.path.isabs(storage_key_or_path):
            abs_path = os.path.abspath(storage_key_or_path)
        else:
            abs_path = os.path.abspath(os.path.join(self.base_dir, storage_key_or_path))

        if not abs_path.startswith(self.base_dir):
            return None

        if os.path.exists(abs_path) and os.path.isfile(abs_path):
            return abs_path

        return None


# Default storage singleton
storage_service = LocalStorageService()
