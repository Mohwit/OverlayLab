# Backend SQLite Overlay Implementation

This document explains how the backend implements a copy-on-write filesystem in SQLite, with direct references to source code.

## 1. Service Composition

The backend container wires four core services:

- `SqliteOverlayFS` for copy-on-write file resolution, writes, and deletions
- `GraphStore` for persistent session/node graph metadata in SQLite
- `FileService` for high-level file CRUD and node diff generation
- `Database` for SQLite connection management and schema initialization

Reference: [backend/app/services/container.py](../backend/app/services/container.py)

```python
class ServiceContainer:
    def __init__(self):
        self.db = Database()
        self.db.init_schema()
        self.sqlite_overlay = SqliteOverlayFS(self.db)
        self.graph_store = GraphStore(self.db)
        self.file_service = FileService(self.sqlite_overlay)
```

## 2. Storage Layout

All data lives in a single SQLite database (`recall.db`) under `OVERLAY_LAB_ROOT` (default: `overlay_lab/`).

```text
overlay_lab/
  recall.db           # single SQLite database (WAL journal mode)
```

The database contains four tables:

```sql
base_files    -- shared base layer files (equivalent to old overlay base/)
sessions      -- session metadata (replaces old session JSON files)
nodes         -- node metadata with parent_node_id ancestry chain
node_files    -- per-node file writes and whiteout deletion markers
```

Settings reference: [backend/app/core/config.py](../backend/app/core/config.py)

Database schema reference: [backend/app/services/db.py](../backend/app/services/db.py)

## 3. Metadata Model

`NodeRecord` stores graph ancestry; `SessionRecord` stores the active pointer.

Reference: [backend/app/core/models.py](../backend/app/core/models.py)

```python
class NodeRecord(BaseModel):
    node_id: str
    parent_node_id: str | None = None
    session_id: str
    created_at: str = Field(default_factory=now_utc)

class SessionRecord(BaseModel):
    session_id: str
    name: str | None = None
    root_node_id: str
    active_node_id: str
    created_at: str = Field(default_factory=now_utc)
    color: str
```

Overlay path fields (`lowerdirs`, `upperdir`, `workdir`, `merged`, `mount_state`) no longer exist on the model. They are computed as virtual labels in the DTO layer for frontend display.

## 4. Graph Persistence

### 4.1 SQLite-Backed Persistence

Sessions and nodes are stored directly in the `sessions` and `nodes` tables. There are no JSON files or in-memory caches.

Reference: [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

```python
def create_session(self, name=None, from_node_id=None):
    # Inserts into sessions and nodes tables in a single transaction
    ...

def create_node(self, session_id, from_node_id):
    # Inserts into nodes table, updates active_node_id on session
    ...
```

### 4.2 Implicit Ancestry (Replaces Lowerdir Flattening)

Previously, each node stored a flattened `lowerdirs` list with explicit filesystem paths. Now ancestry is tracked implicitly via the `parent_node_id` column in the `nodes` table. The overlay engine walks this chain at query time.

Reference: [backend/app/services/sqlite_overlay.py](../backend/app/services/sqlite_overlay.py)

```python
def get_ancestry_chain(self, node_id: str) -> list[str]:
    """Return [node_id, parent_id, grandparent_id, ...] up to root."""
    chain = []
    current = node_id
    while current is not None:
        chain.append(current)
        row = conn.execute(
            "SELECT parent_node_id FROM nodes WHERE node_id = ?",
            (current,),
        ).fetchone()
        current = row["parent_node_id"] if row else None
    return chain
```

### 4.3 New Root Session

A fresh session root starts with `parent_node_id = None`. Its only lower layer is `base_files`.

### 4.4 Branching from an Existing Node

A branch creates a new session whose root node has `parent_node_id` pointing to the source node. The ancestry chain gives it access to all ancestor layers automatically -- zero data copy.

## 5. Copy-on-Write Resolution (Core Algorithm)

### 5.1 Merged-View Resolution

The key function that replaces kernel OverlayFS reads:

Reference: [backend/app/services/sqlite_overlay.py](../backend/app/services/sqlite_overlay.py)

```python
def resolve_merged_files(self, node_id):
    ancestry = self.get_ancestry_chain(node_id)
    merged = {}

    # Start from base layer
    for bf in self.get_base_files():
        merged[bf.path] = bf

    # Apply each ancestor's upper layer, oldest first
    for ancestor_id in reversed(ancestry):
        for entry in self.get_node_upper_files(ancestor_id):
            if entry.whiteout:
                merged.pop(entry.path, None)  # deletion marker
            else:
                merged[entry.path] = entry    # override / add

    return merged
```

### 5.2 Single-File Resolution

For reading a single file, the engine checks the node's own upper layer first, then walks up to each ancestor, and finally falls back to the base layer. The first match wins (newest ancestor first).

```python
def resolve_file(self, node_id, path):
    ancestry = self.get_ancestry_chain(node_id)
    for ancestor_id in ancestry:
        row = get_node_file(ancestor_id, path)
        if row is not None:
            if row.whiteout:
                return None     # file was deleted at this layer
            return row          # found it
    return get_base_file(path)  # fall back to base
```

### 5.3 Preflight

Preflight verifies the SQLite database is writable. No Linux, kernel, or root privilege checks are needed.

Reference: [backend/app/services/sqlite_overlay.py](../backend/app/services/sqlite_overlay.py)

```python
def preflight(self):
    conn.execute("SELECT 1")
    return {"ready": True, "message": "SQLite overlay engine is operational."}
```

## 6. Application Startup

FastAPI lifespan initializes the database schema and closes the connection on shutdown:

Reference: [backend/app/main.py](../backend/app/main.py)

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    container.db.init_schema()
    yield
    container.db.close()
```

There is no mount lifecycle, orphan cleanup, or background worker to manage.

## 7. File IO and Copy-on-Write Behavior

All UI file operations go through `FileService`, which delegates to `SqliteOverlayFS`.

Reference: [backend/app/services/file_service.py](../backend/app/services/file_service.py)

**Write**: encodes content as bytes and inserts into `node_files` for the active node.

```python
content_bytes = content.encode("utf-8")
return self._overlay.write_file(node_id, rel_str, content_bytes)
```

**Delete**: inserts a whiteout marker in `node_files`. The original data in lower layers is preserved.

```python
def delete_file(self, node_id, path):
    # SqliteOverlayFS inserts whiteout=1 row into node_files
    self._overlay.delete_file(node_id, rel_str)
```

**Read**: resolves through the COW ancestry chain, checking the node's upper layer first, then ancestors, then base.

## 8. Path Safety Guardrails

The backend allows only `.txt` and `.md` paths and blocks traversal:

- rejects absolute paths
- rejects `..`
- enforces suffix whitelist

Reference: [backend/app/utils/paths.py](../backend/app/utils/paths.py)

```python
if path.is_absolute() or ".." in path.parts:
    raise AppError("INVALID_FILE_PATH", ...)

if path.suffix.lower() not in ALLOWED_SUFFIXES:
    raise AppError("INVALID_FILE_PATH", ...)
```

## 9. Layer Inspection

The `SqliteOverlayFS.list_layer_files()` method powers the Layer Inspector UI:

- `layer="merged"`: resolved merged view via `resolve_merged_files()`
- `layer="upper"`: node-local writes from `node_files` (excluding whiteouts)
- `layer="lower"` with `index=N`: ancestor N's upper layer, or base layer for the last index

Reference: [backend/app/services/sqlite_overlay.py](../backend/app/services/sqlite_overlay.py)

## 10. Reset Behavior (Destructive)

`POST /admin/reset` deletes all rows from `node_files`, `nodes`, `sessions`, and `base_files`.

Reference: [backend/app/api/routes/admin.py](../backend/app/api/routes/admin.py), [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

## 11. Error Contract

Domain errors use `AppError` and are serialized into:

```json
{
  "code": "DB_ERROR",
  "message": "...",
  "details": { ... }
}
```

Error codes: `NODE_NOT_FOUND`, `INVALID_FILE_PATH`, `SESSION_NOT_FOUND`, `DB_ERROR`.

References:

- [backend/app/core/errors.py](../backend/app/core/errors.py)
- [backend/app/main.py](../backend/app/main.py)

## 12. Virtual Path Labels (Frontend Compatibility)

The frontend Layer Inspector expects `lowerdirs`, `upperdir`, `workdir`, and `merged` fields on `NodeDTO`. These are now computed as virtual descriptors in the DTO layer:

Reference: [backend/app/core/schemas.py](../backend/app/core/schemas.py)

```python
NodeDTO(
    upperdir=f"node:{record.node_id}/upper",
    workdir=f"node:{record.node_id}/work",
    merged=f"node:{record.node_id}/merged",
    lowerdirs=[f"node:{aid}/upper" for aid in ancestry[1:]] + ["base"],
    mount_state="mounted",   # always "mounted" -- no real mounts
)
```

## 13. Test Coverage

Useful tests to review:

- SQLite overlay COW resolution, whiteouts, ancestry:
  - [backend/tests/test_sqlite_overlay.py](../backend/tests/test_sqlite_overlay.py) (if present)
- Graph store CRUD operations:
  - [backend/tests/test_graph_store.py](../backend/tests/test_graph_store.py)
- API flow with real SQLite (in-memory `:memory:` DB):
  - [backend/tests/test_api.py](../backend/tests/test_api.py)

## 14. Practical Implications

- No Linux, kernel modules, or root privileges required.
- Runs on any platform where Python and SQLite are available (Linux, macOS, Windows).
- Nodes are always "available" -- there is no mount/unmount lifecycle.
- Branching is zero-copy: new nodes just point to the parent via `parent_node_id`.
- All data is durable via SQLite WAL journal mode.
