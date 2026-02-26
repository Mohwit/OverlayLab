# Recall FS Documentation

This folder contains implementation-level documentation for the project, with a focus on the backend SQLite overlay engine.

## Start Here

1. [Backend SQLite Overlay Implementation](./backend-overlayfs-implementation.md)
2. [Backend API and Request Flows](./backend-api-and-flows.md)
3. [Operations and Troubleshooting](./operations-and-troubleshooting.md)

## What You Will Find

- How the SQLite copy-on-write overlay engine resolves files through ancestry chains
- How `node_files` (upper layer) and `base_files` (base layer) tables combine via merged-view resolution
- How whiteout markers handle deletions without removing data from lower layers
- How branching reuses the parent ancestry chain with zero data copy
- API-level request/response behavior used by the frontend graph UI
- Operational guidance for running and troubleshooting the application

## Source of Truth

The docs reference live source files under:

- `backend/app/services/*`
- `backend/app/api/routes/*`
- `backend/app/main.py`
- `backend/tests/*`

When behavior and docs diverge, code is authoritative.
