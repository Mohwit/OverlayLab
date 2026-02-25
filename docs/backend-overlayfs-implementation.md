# Backend OverlayFS Implementation

This document explains how the backend implements OverlayFS-backed graph nodes, with direct references to source code.

## 1. Service Composition

The backend container wires four core services:

- `GraphStore` for persistent graph metadata
- `OverlayManager` for kernel mount/unmount operations
- `FileService` for node file IO/diff
- `CleanupWorker` for idle mount lifecycle

Reference: [backend/app/services/container.py](../backend/app/services/container.py)

```python
class ServiceContainer:
    def __init__(self):
        root = Path(settings.overlay_root)
        base = root / "base"
        nodes = root / "nodes"
        sessions = root / "sessions"

        self.graph_store = GraphStore(base, nodes, sessions)
        self.overlay_manager = OverlayManager(nodes_root=nodes)
        self.file_service = FileService()
        self.cleanup_worker = CleanupWorker(self.graph_store, self.overlay_manager)
```

## 2. On-Disk Layout

Under `OVERLAY_LAB_ROOT` (default: `overlay_lab`), the backend uses:

```text
overlay_lab/
  base/                   # immutable base layer (shared lowerdir)
  nodes/
    node_<id>/
      upper/              # copy-on-write changes for this node
      work/               # OverlayFS required workdir for this node
      merged/             # mountpoint exposed to app operations
  sessions/
    sess_<id>.json        # session + all nodes metadata for that session
```

Settings reference: [backend/app/core/config.py](../backend/app/core/config.py)

## 3. Metadata Model

`NodeRecord` stores layer paths and graph ancestry; `SessionRecord` stores active pointer.

Reference: [backend/app/core/models.py](../backend/app/core/models.py)

```python
class NodeRecord(BaseModel):
    node_id: str
    parent_node_id: str | None = None
    session_id: str
    lowerdirs: list[str] = Field(default_factory=list)
    upperdir: str
    workdir: str
    merged: str
    mount_state: Literal["mounted", "unmounted"] = "unmounted"
```

## 4. Graph Persistence and Lowerdir Flattening

### 4.1 Session JSON Persistence

Each session persists as one JSON file including session data and all nodes in that session.

Reference: [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

```python
def _save_session(self, session_id: str) -> None:
    session = self.sessions[session_id]
    nodes = sorted(
        [n for n in self.nodes.values() if n.session_id == session_id],
        key=lambda item: item.created_at,
    )
    session_file = SessionFile(session=session, nodes=nodes)
    self._session_file_path(session_id).write_text(
        json.dumps(session_file.model_dump(), indent=2),
        encoding="utf-8",
    )
```

### 4.2 Why Lowerdirs Are Flattened

The store expands any `merged` references into explicit `upper + inherited lowerdirs`.  
This avoids overlay-on-overlay nesting and keeps lineage explicit.

Reference: [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

```python
def _expand_lowerdirs(self, lowerdirs: list[str], visited_node_ids: set[str]) -> list[str]:
    expanded: list[str] = []
    for lower in lowerdirs:
        source_node = self._node_by_merged_path(lower)
        if source_node and source_node.node_id not in visited_node_ids:
            nested = self._expand_lowerdirs(
                [source_node.upperdir, *source_node.lowerdirs],
                visited_node_ids | {source_node.node_id},
            )
            expanded.extend(nested)
        else:
            expanded.append(lower)
    ...
```

Normalization is enforced both during `load()` and node creation:

- `load()` calls `_normalize_lowerdir_references()`
- `create_node()` and branch-root `create_session(... from_node_id=...)` call `_expand_lowerdirs(...)`

### 4.3 New Root Session

A fresh session root starts with `lowerdirs = [base_dir]`.

Reference: [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

```python
parent_node_id = from_node_id
lowerdirs = [str(self.base_dir.resolve())]
if from_node_id:
    source = self.nodes[from_node_id]
    lowerdirs = self._expand_lowerdirs([source.upperdir, *source.lowerdirs], {source.node_id})
```

### 4.4 Child Node in Same Session

Child nodes derive their lower stack from the parent node:

```python
parent = self.nodes[from_node_id]
lowerdirs = self._expand_lowerdirs([parent.upperdir, *parent.lowerdirs], {parent.node_id})
```

Reference: [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

## 5. OverlayFS Preflight and Mounting

### 5.1 Preflight Checks

The backend checks:

- running on Linux
- overlay present in `/proc/filesystems` OR module file under `/lib/modules/<kernel>/kernel/fs/overlayfs/overlay.ko*`
- effective user is root (`os.geteuid() == 0`) for mounting

Reference: [backend/app/services/overlay_manager.py](../backend/app/services/overlay_manager.py)

```python
def preflight(self) -> dict[str, object]:
    linux = platform.system().lower() == "linux"
    overlay_supported = linux and self._overlay_supported()
    mount_capable = linux and os.geteuid() == 0
    ...
```

### 5.2 Mount Command

For each node:

```bash
mount -t overlay overlay \
  -o lowerdir=<l1:l2:...>,upperdir=<upperdir>,workdir=<workdir> \
  <merged>
```

Reference implementation:

```python
options = f"lowerdir={':'.join(node.lowerdirs)},upperdir={node.upperdir},workdir={node.workdir}"
result = run_command([
    "mount", "-t", "overlay", "overlay", "-o", options, node.merged
])
```

Source: [backend/app/services/overlay_manager.py](../backend/app/services/overlay_manager.py)

If `mount` fails, backend raises:

- `code = "MOUNT_FAILED"`
- includes `stderr` and `stdout` in error details

### 5.3 Unmount Paths

Unmount checks mount state first and then runs:

```python
result = run_command(["umount", merged])
```

Errors become `UNMOUNT_FAILED`.

Source: [backend/app/services/overlay_manager.py](../backend/app/services/overlay_manager.py)

## 6. Mount Lifecycle and App Startup

FastAPI lifespan does:

1. load persisted graph metadata
2. unmount stale/orphan overlay mounts under `nodes_root`
3. sync `node.mount_state` from actual mounted status
4. start background cleanup worker
5. on shutdown: stop worker and unmount all mounted nodes

Reference: [backend/app/main.py](../backend/app/main.py)

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    container.graph_store.load()
    known_paths = {node.merged for node in container.graph_store.get_all_nodes()}
    container.overlay_manager.startup_cleanup_orphan_mounts(known_paths)
    ...
    await container.cleanup_worker.start()
    try:
        yield
    finally:
        await container.cleanup_worker.stop()
        await container.cleanup_worker.shutdown_unmount_all()
```

## 7. File IO and Copy-on-Write Behavior

All UI file operations target `node.merged`, not `upperdir` directly.

Reference: [backend/app/services/file_service.py](../backend/app/services/file_service.py)

```python
target = safe_join(Path(node.merged), relative)
with target.open(write_mode, encoding="utf-8") as handle:
    written = handle.write(content)
```

Because writes happen via merged mount, OverlayFS places modified/new files in that node's `upperdir` automatically.

Deletes are also executed via merged path (`target.unlink()`), so whiteout semantics are handled by OverlayFS.

## 8. Path Safety Guardrails

The backend allows only `.txt` and `.md` paths and blocks traversal:

- rejects absolute paths
- rejects `..`
- enforces suffix whitelist
- safe-joins and ensures target stays under root

Reference: [backend/app/utils/paths.py](../backend/app/utils/paths.py)

```python
if path.is_absolute() or ".." in path.parts:
    raise AppError("INVALID_FILE_PATH", ...)

if path.suffix.lower() not in ALLOWED_SUFFIXES:
    raise AppError("INVALID_FILE_PATH", ...)
```

## 9. Idle Mount Cleanup Strategy

`OverlayManager` tracks node access timestamps via `touch(node_id)`.  
`CleanupWorker` periodically unmounts mounted non-active nodes past TTL.

Reference:

- [backend/app/services/overlay_manager.py](../backend/app/services/overlay_manager.py)
- [backend/app/services/cleanup.py](../backend/app/services/cleanup.py)

Core logic:

```python
stale = self.overlay_manager.stale_node_ids(
    mounted_node_ids=mounted_ids,
    active_node_ids=active_ids,
    ttl_seconds=settings.mount_idle_ttl_seconds,
)
for node_id in stale:
    ...
    self.overlay_manager.unmount_path(node.merged)
```

## 10. Reset Behavior (Destructive)

`POST /admin/reset` does:

1. unmount all known node merged paths
2. orphan cleanup across all overlay mounts under nodes root
3. delete all session JSON files and node directories
4. clear mount access cache

Reference: [backend/app/api/routes/admin.py](../backend/app/api/routes/admin.py), [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

## 11. Error Contract

Domain errors use `AppError` and are serialized into:

```json
{
  "code": "MOUNT_FAILED",
  "message": "Failed to mount overlay node.",
  "details": { "stderr": "...", "stdout": "..." }
}
```

References:

- [backend/app/core/errors.py](../backend/app/core/errors.py)
- [backend/app/main.py](../backend/app/main.py)

## 12. Test Coverage That Protects Overlay Logic

Useful tests to review:

- lowerdir flatten + legacy normalization:
  - [backend/tests/test_graph_store.py](../backend/tests/test_graph_store.py)
- overlay support fallback and preflight message:
  - [backend/tests/test_overlay_manager.py](../backend/tests/test_overlay_manager.py)
- API flow with mocked overlay manager:
  - [backend/tests/test_api.py](../backend/tests/test_api.py)

## 13. Practical Implications

- Backend requires Linux + mount privileges for real mounts.
- Running as non-root will fail preflight `mount_capable`.
- A node can exist as metadata while mount state is `unmounted`; mount occurs lazily before file/diff operations.
- Branching is metadata-level graph branching plus independent overlay stacks per new branch root.
