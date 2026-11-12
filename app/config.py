"""Shared limits for uploaded and generated documents."""

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_TABLE_ROWS = 500
MAX_UNPACKED_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024


def validate_upload_size(content: bytes, *, label: str) -> None:
    """Reject empty or oversized uploads with a user-facing error."""
    if not content:
        raise ValueError(f"{label}: файл пуст.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"{label}: размер файла превышает лимит 20 МБ."
        )
