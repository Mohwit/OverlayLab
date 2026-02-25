from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(self, code: str, message: str, details: Any | None = None, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code


ERROR_CODES = {
    "OVERLAY_NOT_SUPPORTED",
    "MOUNT_FAILED",
    "NODE_NOT_FOUND",
    "INVALID_FILE_PATH",
    "UNMOUNT_FAILED",
    "SESSION_NOT_FOUND",
}
