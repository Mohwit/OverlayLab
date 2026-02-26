from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Recall FS"
    overlay_root: Path = Path(os.getenv("OVERLAY_LAB_ROOT", "overlay_lab")).resolve()

    @property
    def db_path(self) -> Path:
        return self.overlay_root / "recall.db"


settings = Settings()
