from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, diff, files, health, nodes, sessions
from app.core.errors import AppError
from app.services.container import container


@asynccontextmanager
async def lifespan(_: FastAPI):
    container.graph_store.load()
    known_paths = {node.merged for node in container.graph_store.get_all_nodes()}
    container.overlay_manager.startup_cleanup_orphan_mounts(known_paths)

    for node in container.graph_store.get_all_nodes():
        node.mount_state = "mounted" if container.overlay_manager.is_mounted(node.merged) else "unmounted"
        container.graph_store.update_node(node)

    await container.cleanup_worker.start()
    try:
        yield
    finally:
        await container.cleanup_worker.stop()
        await container.cleanup_worker.shutdown_unmount_all()


app = FastAPI(title="OverlayFS Session Graph Lab", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(admin.router)
app.include_router(sessions.router)
app.include_router(nodes.router)
app.include_router(files.router)
app.include_router(diff.router)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
    )


@app.get("/api/status")
def api_status():
    return {"name": "OverlayFS Session Graph Lab", "status": "ok"}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend_dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_root():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        candidate = frontend_dist / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_dist / "index.html")
else:
    @app.get("/")
    def root():
        return {"name": "OverlayFS Session Graph Lab", "status": "ok", "ui": "frontend_dist not found"}
