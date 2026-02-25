# OverlayLab Documentation

This folder contains implementation-level documentation for the project, with a focus on the backend OverlayFS design.

## Start Here

1. [Backend OverlayFS Implementation](./backend-overlayfs-implementation.md)
2. [Backend API and Request Flows](./backend-api-and-flows.md)
3. [Operations and Troubleshooting](./operations-and-troubleshooting.md)

## What You Will Find

- How `lowerdir`, `upperdir`, `workdir`, and `merged` are built per node
- How branching and linear progression are persisted in graph metadata
- Why lowerdir stacks are flattened (and how legacy data is normalized)
- How file writes trigger copy-on-write in this implementation
- API-level request/response behavior used by the frontend graph UI
- Operational commands for Linux host runs and mount failure triage

## Source of Truth

The docs reference live source files under:

- `backend/app/services/*`
- `backend/app/api/routes/*`
- `backend/app/main.py`
- `backend/tests/*`

When behavior and docs diverge, code is authoritative.
