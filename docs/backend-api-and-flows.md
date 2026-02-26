# Backend API and Request Flows

This document maps backend endpoints to implementation behavior and graph/layer transitions.

## 1. Endpoint Inventory

### Health and Preflight

- `GET /health/preflight`
  - returns `{ ready, message }`
  - source: [backend/app/api/routes/health.py](../backend/app/api/routes/health.py)

### Sessions

- `POST /session/create`
  - creates a new session + root node in SQLite
  - source: [backend/app/api/routes/sessions.py](../backend/app/api/routes/sessions.py)
- `POST /session/branch/{node_id}`
  - creates a new session rooted from `node_id`
  - new branch root's `parent_node_id` points to source node; ancestry chain gives it all lower layers
  - source: [backend/app/api/routes/sessions.py](../backend/app/api/routes/sessions.py)

### Nodes

- `POST /node/create`
  - creates child node in an existing session
  - parent defaults to active node if `from_node_id` absent
  - source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)
- `POST /node/revert/{node_id}`
  - sets session active pointer to target node
  - source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)
- `GET /node/{node_id}/layers`
  - returns virtual layer path metadata (merged/upper/work/lowerdirs) computed from ancestry
  - source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)
- `GET /graph`
  - returns sessions, nodes, and parent->child edges
  - source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)

### Files and Layer Inspection

- `GET /node/{node_id}/files`
  - merged-view file listing resolved through the COW ancestry chain
- `GET /node/{node_id}/file?path=<relative>`
  - reads one text file from the resolved merged view
- `GET /node/{node_id}/layer-files?layer=merged|upper|lower&index=<n>`
  - inspects file listings of a specific layer
- `POST /node/{node_id}/file`
  - writes file to the node's upper layer in `node_files`
- `DELETE /node/{node_id}/file`
  - inserts a whiteout marker in `node_files`
- source: [backend/app/api/routes/files.py](../backend/app/api/routes/files.py)

### Diff

- `GET /diff?from_node_id=...&to_node_id=...`
  - unified diff over `.txt`/`.md` files between two nodes' resolved merged views
  - source: [backend/app/api/routes/diff.py](../backend/app/api/routes/diff.py), [backend/app/services/file_service.py](../backend/app/services/file_service.py)

### Admin

- `POST /admin/reset`
  - deletes all rows from `node_files`, `nodes`, `sessions`, `base_files`
  - source: [backend/app/api/routes/admin.py](../backend/app/api/routes/admin.py)

## 2. Request Flow: Create Session

Sequence:

1. API route calls `graph_store.create_session(name=...)`
2. `graph_store` inserts rows into `sessions` and `nodes` tables
3. Root node's `parent_node_id` is `None`; its only lower layer is `base_files`
4. Ancestry chain is computed for the DTO response
5. Response includes `session`, `root_node`, `graph_delta`

Reference snippet:

```python
session, node = container.graph_store.create_session(name=payload.name)
ancestry = container.sqlite_overlay.get_ancestry_chain(node.node_id)

return SessionCreateResponse(
    session=SessionDTO(**session.model_dump()),
    root_node=NodeDTO.from_record(node, ancestry),
    graph_delta=GraphDelta(added_node_id=node.node_id),
)
```

Source: [backend/app/api/routes/sessions.py](../backend/app/api/routes/sessions.py)

## 3. Request Flow: Create Node in Existing Session

The child node's `parent_node_id` points to the source node. The ancestry chain gives it access to all ancestor layers.

```python
from_node_id = payload.from_node_id or session.active_node_id
node = container.graph_store.create_node(session_id=payload.session_id, from_node_id=from_node_id)
ancestry = container.sqlite_overlay.get_ancestry_chain(node.node_id)
```

Source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)

Inside graph store, `create_node` inserts the row and updates `active_node_id`:

```python
conn.execute("INSERT INTO nodes (node_id, parent_node_id, session_id, created_at) VALUES (?, ?, ?, ?)", ...)
conn.execute("UPDATE sessions SET active_node_id = ? WHERE session_id = ?", ...)
```

Source: [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

## 4. Request Flow: Branch Session from Any Node

Branch creates a new session root whose `parent_node_id` points to the source node. The ancestry chain provides all lower layers from the source node's lineage.

```python
session, root_node = container.graph_store.create_session(name=payload.name, from_node_id=node_id)
ancestry = container.sqlite_overlay.get_ancestry_chain(root_node.node_id)
```

Source: [backend/app/api/routes/sessions.py](../backend/app/api/routes/sessions.py)

## 5. Request Flow: File Write (Copy-On-Write)

1. Route validates node exists
2. `FileService.write_file(...)` encodes content as bytes
3. `SqliteOverlayFS.write_file()` inserts/replaces a row in `node_files` for that node
4. If mode is `"append"`, existing content is resolved first and prepended

```python
bytes_written = container.file_service.write_file(node_id, payload.path, payload.content, payload.mode)
```

Source: [backend/app/api/routes/files.py](../backend/app/api/routes/files.py)

## 6. Layer Inspection API Semantics

- `layer=merged`: resolved COW view (base + all ancestors + node)
- `layer=upper`: only rows from `node_files` for this node (excluding whiteouts)
- `layer=lower&index=n`: ancestor N's upper layer files, or base layer for the last index

```python
records = container.sqlite_overlay.list_layer_files(node_id, layer, index)
```

Source: [backend/app/api/routes/files.py](../backend/app/api/routes/files.py)

## 7. Request Flow: Reset

`POST /admin/reset` clears all data from the SQLite database:

```python
summary = container.graph_store.reset_graph()
return ResetResponseDTO(
    cleared_nodes=summary["nodes"],
    cleared_sessions=summary["sessions"],
    message="Reset complete. All sessions, nodes, and file data were cleared.",
)
```

Source: [backend/app/api/routes/admin.py](../backend/app/api/routes/admin.py)

## 8. Example cURL Calls

### Preflight

```bash
curl -s http://localhost:8000/health/preflight | jq
```

### Create Session

```bash
curl -s -X POST http://localhost:8000/session/create \
  -H 'content-type: application/json' \
  -d '{"name":"start"}' | jq
```

### Create Node from Active

```bash
curl -s -X POST http://localhost:8000/node/create \
  -H 'content-type: application/json' \
  -d '{"session_id":"sess_abcd1234"}' | jq
```

### Write File

```bash
curl -s -X POST http://localhost:8000/node/node_abcd1234/file \
  -H 'content-type: application/json' \
  -d '{"path":"notes.md","content":"hello","mode":"overwrite"}' | jq
```

### Read Layer Files (Upper Layer)

```bash
curl -s "http://localhost:8000/node/node_abcd1234/layer-files?layer=upper" | jq
```

### Diff Two Nodes

```bash
curl -s "http://localhost:8000/diff?from_node_id=node_aaa&to_node_id=node_bbb" | jq
```

### Reset

```bash
curl -s -X POST http://localhost:8000/admin/reset | jq
```
