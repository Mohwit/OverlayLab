# Backend API and Request Flows

This document maps backend endpoints to implementation behavior and graph/layer transitions.

## 1. Endpoint Inventory

### Health and Preflight

- `GET /health/preflight`
  - returns `{ linux, overlay_supported, mount_capable, message }`
  - source: [backend/app/api/routes/health.py](../backend/app/api/routes/health.py)

### Sessions

- `POST /session/create`
  - creates a new session + root node
  - mounts root node immediately
  - source: [backend/app/api/routes/sessions.py](../backend/app/api/routes/sessions.py)
- `POST /session/branch/{node_id}`
  - creates a new session rooted from `node_id`
  - source node is mounted first
  - new branch root lowerdirs derive from source node lineage
  - source: [backend/app/api/routes/sessions.py](../backend/app/api/routes/sessions.py)

### Nodes

- `POST /node/create`
  - creates child node in an existing session
  - parent defaults to active node if `from_node_id` absent
  - source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)
- `POST /node/revert/{node_id}`
  - sets session active pointer to target node
  - mounts target node first if needed
  - source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)
- `GET /node/{node_id}/layers`
  - returns layer path metadata (merged/upper/work/lowerdirs)
  - source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)
- `GET /graph`
  - returns sessions, nodes, and parent->child edges
  - source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)

### Files and Layer Inspection

- `GET /node/{node_id}/files`
  - merged-view recursive listing
- `GET /node/{node_id}/file?path=<relative>`
  - reads one text file
- `GET /node/{node_id}/layer-files?layer=merged|upper|lower&index=<n>`
  - inspects file listings of a specific layer root
- `POST /node/{node_id}/file`
  - writes file (overwrite/append)
- `DELETE /node/{node_id}/file`
  - deletes a file from merged view
- source: [backend/app/api/routes/files.py](../backend/app/api/routes/files.py)

### Diff

- `GET /diff?from_node_id=...&to_node_id=...`
  - unified diff over `.txt`/`.md`
  - source: [backend/app/api/routes/diff.py](../backend/app/api/routes/diff.py), [backend/app/services/file_service.py](../backend/app/services/file_service.py)

### Admin

- `POST /admin/reset`
  - unmount + cleanup + metadata/node directory wipe
  - source: [backend/app/api/routes/admin.py](../backend/app/api/routes/admin.py)

## 2. Request Flow: Create Session

Sequence:

1. API route calls `graph_store.create_session(name=...)`
2. `graph_store` creates node directories (`upper/work/merged`)
3. root node lowerdir starts from `base`
4. route mounts root node with `overlay_manager.mount_node(...)`
5. route sets `node.mount_state = "mounted"` and persists
6. response includes `session`, `root_node`, `graph_delta`

Reference snippets:

```python
session, node = container.graph_store.create_session(name=payload.name)
container.overlay_manager.mount_node(node)
node.mount_state = "mounted"
container.graph_store.update_node(node)
```

Source: [backend/app/api/routes/sessions.py](../backend/app/api/routes/sessions.py)

## 3. Request Flow: Create Node in Existing Session

Key invariant: child node lowerdirs are flattened from parent lineage.

```python
from_node_id = payload.from_node_id or session.active_node_id
node = container.graph_store.create_node(session_id=payload.session_id, from_node_id=from_node_id)
container.overlay_manager.mount_node(node)
node.mount_state = "mounted"
container.graph_store.update_node(node)
```

Source: [backend/app/api/routes/nodes.py](../backend/app/api/routes/nodes.py)

Inside graph store:

```python
parent = self.nodes[from_node_id]
lowerdirs = self._expand_lowerdirs([parent.upperdir, *parent.lowerdirs], {parent.node_id})
```

Source: [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

## 4. Request Flow: Branch Session from Any Node

Branch creates a new session root whose parent points to source node and whose layer stack is derived from source ancestry.

```python
session, root_node = container.graph_store.create_session(name=payload.name, from_node_id=node_id)
container.overlay_manager.mount_node(root_node)
root_node.mount_state = "mounted"
container.graph_store.update_node(root_node)
```

Source: [backend/app/api/routes/sessions.py](../backend/app/api/routes/sessions.py)

## 5. Request Flow: File Write (Copy-On-Write)

1. route validates node
2. route ensures merged mount exists
3. `FileService.write_file(...)` writes to `node.merged/<relative path>`
4. overlay manager `touch(node_id)` updates access time for idle-cleanup logic

```python
bytes_written = container.file_service.write_file(node, payload.path, payload.content, payload.mode)
container.overlay_manager.touch(node_id)
```

Source: [backend/app/api/routes/files.py](../backend/app/api/routes/files.py)

## 6. Layer Inspection API Semantics

- `layer=merged`: mount-aware view (what app sees)
- `layer=upper`: node-local changes only
- `layer=lower&index=n`: specific lowerdir item in order

Relevant code:

```python
if layer == "merged":
    root = Path(node.merged)
elif layer == "upper":
    root = Path(node.upperdir)
else:
    root = Path(node.lowerdirs[index])
```

Source: [backend/app/api/routes/files.py](../backend/app/api/routes/files.py)

## 7. Request Flow: Reset

`POST /admin/reset` is a full lab cleanup operation:

```python
for node in container.graph_store.get_all_nodes():
    container.overlay_manager.unmount_path(node.merged)
container.overlay_manager.startup_cleanup_orphan_mounts(set())
summary = container.graph_store.reset_graph()
container.overlay_manager.clear_access_cache()
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

### Read Layer Files (Upperdir)

```bash
curl -s "http://localhost:8000/node/node_abcd1234/layer-files?layer=upper" | jq
```

### Diff Two Nodes

```bash
curl -s "http://localhost:8000/diff?from_node_id=node_aaa&to_node_id=node_bbb" | jq
```

### Reset Lab

```bash
curl -s -X POST http://localhost:8000/admin/reset | jq
```
