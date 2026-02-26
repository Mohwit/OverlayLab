# Operations and Troubleshooting

This guide covers running the application and diagnosing common issues.

## 1. Prerequisites

- Python 3.10+
- `uv` package manager (or pip with a virtualenv)
- Node.js and npm (for frontend development)
- SQLite3 (included in Python standard library)

No Linux kernel, root privileges, or special filesystem support is required.

## 2. Start Backend

```bash
make backend-dev
```

Or directly:

```bash
uv run uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

## 3. Start Frontend

```bash
cd frontend && npm run dev
```

Set API base if the backend runs on a different host:

```bash
export VITE_API_BASE=http://localhost:8000
```

## 4. Confirm Preflight from API

```bash
curl -s http://localhost:8000/health/preflight | jq
```

Expected success shape:

```json
{
  "ready": true,
  "message": "SQLite overlay engine is operational."
}
```

If `ready` is `false`, the SQLite database at `OVERLAY_LAB_ROOT/recall.db` is not writable. Check directory permissions and disk space.

## 5. Common Errors

### 5.1 `DB_ERROR`

Meaning:

- SQLite database is not writable
- Disk full or directory permissions issue
- Database file is corrupted

Diagnosis:

```bash
ls -la overlay_lab/recall.db
sqlite3 overlay_lab/recall.db "PRAGMA integrity_check;"
```

### 5.2 `make: uv: No such file or directory`

Cause:

- `uv` not installed or not in PATH

Fix:

- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Or use pip: `pip install -r requirements.txt` and run uvicorn directly

### 5.3 `INVALID_FILE_PATH`

Meaning:

- File path is absolute, contains `..`, or has a disallowed extension
- Only `.txt` and `.md` files are accepted

Reference: [backend/app/utils/paths.py](../backend/app/utils/paths.py)

## 6. Configuration

The application reads one environment variable:

| Variable | Default | Description |
| --- | --- | --- |
| `OVERLAY_LAB_ROOT` | `overlay_lab` | Parent directory for the `recall.db` SQLite database |

Reference: [backend/app/core/config.py](../backend/app/core/config.py)

## 7. Data Reset

`POST /admin/reset` clears all data:

- All file data (`node_files`, `base_files`)
- All node metadata (`nodes`)
- All session metadata (`sessions`)

The database schema is preserved. The app auto-creates a new default session on the next frontend load.

```bash
curl -s -X POST http://localhost:8000/admin/reset | jq
```

Reference:

- [backend/app/api/routes/admin.py](../backend/app/api/routes/admin.py)
- [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

## 8. Security and File Validation Rules

Only `.txt` and `.md` files are accepted for write/read operations.
Paths must be relative and cannot traverse upward.

Reference: [backend/app/utils/paths.py](../backend/app/utils/paths.py)

## 9. Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

The container runs as a normal unprivileged process. No `--privileged` flag is needed. Persistent data is stored in the `overlay_lab_data` Docker volume as a single `recall.db` file.

Open `http://localhost:8000` for the full UI.

## 10. Backup and Recovery

The SQLite database uses WAL (Write-Ahead Logging) journal mode for durability. To back up:

```bash
sqlite3 overlay_lab/recall.db ".backup overlay_lab/recall-backup.db"
```

After a crash, SQLite automatically recovers from the WAL journal on the next connection.

## 11. Operational Checks

Use this checklist when debugging:

1. `GET /health/preflight` returns `ready: true`.
2. `overlay_lab/` directory exists and is writable.
3. `recall.db` file is not locked by another process.
4. `POST /admin/reset` works if state gets inconsistent.

## 12. Tests

From repo root:

```bash
make test
```

Targeted:

```bash
uv run pytest backend/tests/test_graph_store.py -q
uv run pytest backend/tests/test_api.py -q
```

Tests run against real SQLite databases (created in temporary directories) with no mocks for the storage layer.
