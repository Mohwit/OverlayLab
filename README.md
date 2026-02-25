# OverlayFS Session Graph Lab

OverlayFS Session Graph Lab is a Linux-only educational tool that maps AI-agent session state transitions to **real OverlayFS mounts**.

- Node = one interaction state (overlay layer)
- Edge = parent relationship (lowerdir ancestry)
- Session = branch/timeline
- Revert = move active pointer without file copy

## Architecture

### Backend (FastAPI)

- `backend/app/services/overlay_manager.py`: mount/unmount and mount lifecycle management
- `backend/app/services/graph_store.py`: persistent session/node graph metadata
- `backend/app/services/file_service.py`: `.txt`/`.md` CRUD and node diff generation
- `backend/app/services/cleanup.py`: startup orphan mount cleanup + idle TTL unmount

### Frontend (React + React Flow)

Graph-first UI built with React Flow:

- Click node: inspect files/layers
- Right-click node:
  - create interaction node
  - branch session
  - revert session to node
  - diff from active

Secondary panel:

- layer inspector (`lowerdir` / `upperdir` / `workdir` / `merged`)
- merged-view file operations (`.txt`, `.md`)
- diff viewer
- contextual OverlayFS learning cues (`i` buttons) + full in-app guide popup

Session UX:

- app auto-creates a default `start` session if graph is empty
- branch sessions are shown with fallback labels `branch-1`, `branch-2`, ... when unnamed
- reset button clears node/session data and reboots the graph back to `start`

## OverlayFS Mapping

Node directory layout:

```text
overlay_lab/
  base/
  nodes/
    <node_id>/
      upper/
      work/
      merged/
  sessions/
    <session_id>.json
```

### Create Root Session

- lowerdir = `overlay_lab/base`
- upperdir/workdir/merged created under node directory
- mounted via:

```bash
mount -t overlay overlay -o lowerdir=<base>,upperdir=<upper>,workdir=<work> <merged>
```

### Create Child Node

- parent = selected or active node
- lowerdirs are flattened from parent ancestry (no nested overlay-on-overlay dependency):
  - `lowerdirs = [parent.upperdir, ...parent.lowerdirs]`
  - duplicates removed while preserving order
- new empty `upper/work`
- mount new `merged`

### Revert

- only `active_node_id` changes
- no file copying
- mount performed on-demand if needed

### Branch Session

- new session root parent = selected source node
- new session root lowerdirs follow source ancestry stack:
  - `lowerdirs = [source.upperdir, ...source.lowerdirs]`
- independent active pointer and future node chain

### Why Flattened lowerdirs

- avoids brittle deep chains like `lowerdir=<other_node_merged>`
- keeps mounts stable across long interaction histories
- makes layer provenance explicit in inspector (`upper` lineage + `base`)

## Linux Requirements

- Linux kernel with OverlayFS support (`/proc/filesystems` includes `overlay`) or available overlay module files
- Mount capability (this implementation expects root privileges)
- `mount`/`umount` binaries available

Preflight endpoint:

- `GET /health/preflight`

## API Endpoints

- `POST /session/create`
- `POST /node/create`
- `POST /session/branch/{node_id}`
- `POST /node/revert/{node_id}`
- `GET /node/{node_id}/files`
- `POST /node/{node_id}/file`
- `DELETE /node/{node_id}/file`
- `GET /graph`
- `POST /admin/reset`
- `GET /node/{node_id}/layers`
- `GET /diff?from_node_id=...&to_node_id=...`

## Run

### Backend

```bash
uv sync
make backend-dev
```

If running directly on host, use root for mount operations:

```bash
sudo env "PATH=/home/<user>/.local/bin:$PATH" make backend-dev
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

- This container is configured with `privileged: true` because OverlayFS mounts require elevated privileges.
- Persistent graph/layer metadata is stored in the named Docker volume `overlay_lab_data`.
- APIs are served from the same origin (`http://localhost:8000`), so no frontend API URL setup is needed.
- Docker image now uses deterministic frontend dependency install via `npm ci`.

## Testing

```bash
make test
```

Note: mount integration behavior requires Linux + mount privileges. Included tests focus on API, graph persistence, and lifecycle logic with mocked mounts.

## Troubleshooting

- `OVERLAY_NOT_SUPPORTED`: host is not Linux or overlay module unavailable.
- `MOUNT_FAILED`: run backend with sufficient privileges and check mount options/path permissions.
- stale mounts after crash: restart backend to trigger startup orphan cleanup, or manually `umount overlay_lab/nodes/*/merged`.
- On macOS, running in Docker can work because Docker Desktop runs Linux inside a VM. It is still kernel/privilege dependent, so keep `privileged: true` and test with `GET /health/preflight`.
- inspector path preview looks stale after file save: hover again or keep hover active; cache refresh is wired to file list updates.
