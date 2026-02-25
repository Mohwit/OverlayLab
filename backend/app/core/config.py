from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "OverlayFS Session Graph Lab"
    overlay_root: Path = Path(os.getenv("OVERLAY_LAB_ROOT", "overlay_lab")).resolve()
    mount_idle_ttl_seconds: int = int(os.getenv("MOUNT_IDLE_TTL_SECONDS", "120"))
    cleanup_interval_seconds: int = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "30"))

    @property
    def base_dir(self) -> Path:
        return self.overlay_root / "base"

    @property
    def nodes_dir(self) -> Path:
        return self.overlay_root / "nodes"

    @property
    def sessions_dir(self) -> Path:
        return self.overlay_root / "sessions"


settings = Settings()
