# Operations and Troubleshooting

This guide focuses on running the backend reliably on Linux hosts and diagnosing OverlayFS issues.

## 1. Host Prerequisites

- Linux kernel runtime
- OverlayFS available via:
  - `/proc/filesystems` containing `overlay`, or
  - overlay module files under `/lib/modules/<kernel>/kernel/fs/overlayfs/overlay.ko*`
- `mount` and `umount` available in PATH
- backend process with mount privilege (root in this implementation)

Preflight logic reference: [backend/app/services/overlay_manager.py](../backend/app/services/overlay_manager.py)

## 2. Verify OverlayFS Manually

```bash
uname -a
cat /proc/filesystems | grep overlay || true
ls /lib/modules/$(uname -r)/kernel/fs/overlayfs/overlay.ko* 2>/dev/null || true
```

## 3. Start Backend with Root Privileges

If `uv` is installed under `~/.local/bin`, preserve PATH when using `sudo`:

```bash
sudo env "PATH=$HOME/.local/bin:$PATH" make backend-dev
```

Alternative direct run:

```bash
sudo env "PATH=$HOME/.local/bin:$PATH" uv run uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

## 4. Confirm Preflight from API

```bash
curl -s http://localhost:8000/health/preflight | jq
```

Expected success shape:

```json
{
  "linux": true,
  "overlay_supported": true,
  "mount_capable": true,
  "message": "OverlayFS available."
}
```

## 5. Common Errors

### 5.1 `OVERLAY_NOT_SUPPORTED`

Meaning:

- not running on Linux, or
- no overlay support detected

Where raised:

- `OverlayManager.ensure_supported()`
- reference: [backend/app/services/overlay_manager.py](../backend/app/services/overlay_manager.py)

### 5.2 `MOUNT_FAILED` with `wrong fs type, bad option, bad superblock`

Typical causes:

- process not running with mount privileges
- invalid/incompatible mount options
- kernel policy restrictions
- path issues around `upperdir/workdir/merged`

Inspect details from API error response (`details.stderr`), then check kernel logs:

```bash
dmesg | tail -n 80
```

Mount invocation reference:

```python
result = run_command([
    "mount",
    "-t",
    "overlay",
    "overlay",
    "-o",
    options,
    node.merged,
])
```

Source: [backend/app/services/overlay_manager.py](../backend/app/services/overlay_manager.py)

### 5.3 `make: uv: No such file or directory`

Cause:

- `uv` not installed or not in root PATH under `sudo`

Fix:

- install uv, or
- call `sudo env "PATH=$HOME/.local/bin:$PATH" ...`

## 6. Mount State and Cleanup Behavior

### Idle cleanup

- background worker periodically checks mounted nodes
- nodes not active and older than TTL are unmounted

Reference:

- [backend/app/services/cleanup.py](../backend/app/services/cleanup.py)
- [backend/app/core/config.py](../backend/app/core/config.py)

Environment knobs:

- `MOUNT_IDLE_TTL_SECONDS` (default `120`)
- `CLEANUP_INTERVAL_SECONDS` (default `30`)

### Startup orphan cleanup

At startup, unknown overlay mounts under node root are unmounted to recover from crashes.

Reference: [backend/app/main.py](../backend/app/main.py), [backend/app/services/overlay_manager.py](../backend/app/services/overlay_manager.py)

## 7. Data Reset Behavior

`POST /admin/reset` clears:

- mounted overlays (best effort unmount)
- session JSON metadata
- all node directories (`upper/work/merged`)
- in-memory mount access cache

Reference:

- [backend/app/api/routes/admin.py](../backend/app/api/routes/admin.py)
- [backend/app/services/graph_store.py](../backend/app/services/graph_store.py)

## 8. Security and File Validation Rules

Only `.txt` and `.md` files are accepted for write/read operations.  
Paths must be relative and cannot traverse upward.

Reference: [backend/app/utils/paths.py](../backend/app/utils/paths.py)

## 9. Operational Checks

Use this quick checklist when debugging:

1. `GET /health/preflight` returns all `true`.
2. Backend process runs as root.
3. `/proc/filesystems` has `overlay` or module fallback exists.
4. `overlay_lab/nodes/<node>/upper|work|merged` directories exist.
5. Failed mount stderr and recent `dmesg` lines are reviewed.
6. `POST /admin/reset` works if state gets inconsistent.

## 10. Tests You Can Run

From repo root:

```bash
make test
```

Targeted:

```bash
uv run pytest backend/tests/test_overlay_manager.py -q
uv run pytest backend/tests/test_graph_store.py -q
uv run pytest backend/tests/test_api.py -q
```

Note: tests mock mount behavior for API routes, so they can run without real kernel mounts.
