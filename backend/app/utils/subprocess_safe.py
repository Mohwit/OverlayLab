from __future__ import annotations

import subprocess
from typing import Sequence

from app.core.errors import AppError


def run_command(args: Sequence[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(args),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError("MOUNT_FAILED", f"Command timed out: {' '.join(args)}", status_code=500) from exc
    except OSError as exc:
        raise AppError("MOUNT_FAILED", f"Command failed to start: {' '.join(args)}", details=str(exc), status_code=500) from exc

    return result
