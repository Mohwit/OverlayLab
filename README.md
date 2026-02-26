# Recall FS -- Session Graph Lab

Recall FS is a cross-platform educational tool that maps AI-agent session state transitions to a **copy-on-write filesystem** backed by SQLite.

- Node = one interaction state (overlay layer)
- Edge = parent relationship (ancestry chain)
- Session = branch/timeline
- Revert = move active pointer without file copy

The overlay engine stores all file data in a single `recall.db` SQLite database, implementing the same copy-on-write semantics as Linux OverlayFS -- but without requiring Linux, kernel modules, or root privileges.

## Detailed Docs

- [Docs Index](docs/README.md)
- [Backend API and Request Flows](docs/backend-api-and-flows.md)
- [Operations and Troubleshooting](docs/operations-and-troubleshooting.md)

## Architecture

### Backend (FastAPI)

- `backend/app/services/sqlite_overlay.py`: SQLite-backed copy-on-write overlay engine (ancestry-chain file resolution, whiteout deletions)
- `backend/app/services/graph_store.py`: persistent session/node graph metadata in SQLite
- `backend/app/services/file_service.py`: `.txt`/`.md` CRUD and node diff generation
- `backend/app/services/db.py`: SQLite database initialization and connection management

### Frontend (React + React Flow)

Graph-first UI built with React Flow:

- Click node: inspect files/layers
- Right-click node:
  - create interaction node
  - branch session
  - revert session to node
  - diff from active

Secondary panel:

- layer inspector (lower layers / upper layer / merged view)
- merged-view file operations (`.txt`, `.md`)
- diff viewer
- contextual learning cues (`i` buttons) + full in-app guide popup

Session UX:

- app auto-creates a default `start` session if graph is empty
- branch sessions are shown with fallback labels `branch-1`, `branch-2`, ... when unnamed
- reset button clears node/session data and reboots the graph back to `start`

## Copy-on-Write Model

All file data lives in SQLite tables:

```text
recall.db
  base_files   -- shared base layer files
  sessions     -- session metadata
  nodes        -- node metadata with parent_node_id ancestry
  node_files   -- per-node file writes and whiteout (deletion) markers
```

### Read (merged view)

Walk the ancestry chain from the current node up to the root, then apply each layer's writes and whiteouts on top of the base layer. The first match wins (newest ancestor checked first for single-file lookups).

### Write

Insert into `node_files` for the active node. Parent nodes are never modified.

### Delete

Insert a whiteout marker in `node_files`. The original data in lower layers is preserved.

### Branch

Create a new session whose root node points to the source node as its parent. Zero data is copied -- the ancestry chain provides all lower layers automatically.

### Revert

Update `active_node_id` on the session. No file copying.

## API Endpoints

- `POST /session/create`
- `POST /node/create`
- `POST /session/branch/{node_id}`
- `POST /node/revert/{node_id}`
- `GET /node/{node_id}/files`
- `POST /node/{node_id}/file`
- `DELETE /node/{node_id}/file`
- `GET /node/{node_id}/file?path=...`
- `GET /node/{node_id}/layers`
- `GET /node/{node_id}/layer-files?layer=...&index=...`
- `GET /graph`
- `GET /diff?from_node_id=...&to_node_id=...`
- `POST /admin/reset`
- `GET /health/preflight`

## Run

### Backend

```bash
uv sync
make backend-dev
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Set API base if needed:

```bash
export VITE_API_BASE=http://localhost:8000
```

### Single-Container Docker (Frontend + Backend)

Build and run:

```bash
docker compose up --build
```

Open:

- `http://localhost:8000` (React UI served by FastAPI)

Notes:

- No elevated privileges required -- the container runs as a normal unprivileged process.
- Persistent graph/layer data is stored in the named Docker volume `overlay_lab_data` as a single `recall.db` SQLite file.
- APIs are served from the same origin (`http://localhost:8000`), so no frontend API URL setup is needed.
- Works on Linux, macOS, and Windows (anywhere Docker or Python runs).

## Testing

```bash
make test
```

Tests run against real SQLite databases (created in temporary directories) with no mocks for the storage layer.

## Troubleshooting

- `DB_ERROR`: check that the configured `OVERLAY_LAB_ROOT` directory is writable and has enough disk space.
- After a crash, data is safe in SQLite (WAL journal mode ensures durability).
- Inspector path preview looks stale after file save: hover again or keep hover active; cache refresh is wired to file list updates.
