from __future__ import annotations


class CleanupWorker:
    """No-op stub retained for startup/shutdown compatibility.

    With the SQLite overlay engine there are no kernel mounts to manage,
    so the periodic cleanup loop is unnecessary.  The async start/stop
    interface is preserved so ``main.py`` lifespan code keeps working
    without changes.
    """

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def shutdown_unmount_all(self) -> None:
        pass
