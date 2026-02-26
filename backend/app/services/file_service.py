from __future__ import annotations

import difflib
from datetime import datetime
from pathlib import Path

from app.core.errors import AppError
from app.core.schemas import DiffDTO, DiffFileDTO, FileEntryDTO
from app.services.sqlite_overlay import SqliteOverlayFS
from app.utils.paths import validate_relative_file_path


def _iso_to_timestamp(iso_str: str) -> float:
    try:
        return datetime.fromisoformat(iso_str).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _decode_content(raw: bytes | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore")
    return raw


class FileService:
    """High-level file operations backed by SqliteOverlayFS.

    All reads resolve through the COW ancestry chain; writes and deletes
    target the specified node's upper layer.
    """

    def __init__(self, overlay: SqliteOverlayFS) -> None:
        self._overlay = overlay

    def list_files(self, node_id: str) -> list[FileEntryDTO]:
        merged = self._overlay.resolve_merged_files(node_id)
        entries: list[FileEntryDTO] = []
        for _path, record in sorted(merged.items()):
            entries.append(
                FileEntryDTO(
                    path=record.path,
                    type="dir" if record.is_dir else "file",
                    size=record.size,
                    mtime=_iso_to_timestamp(record.created_at),
                )
            )
        return entries

    def read_text_files(self, node_id: str) -> dict[str, str]:
        merged = self._overlay.resolve_merged_files(node_id)
        data: dict[str, str] = {}
        for path, record in sorted(merged.items()):
            if record.is_dir:
                continue
            if Path(path).suffix.lower() not in {".txt", ".md"}:
                continue
            data[path] = _decode_content(record.content)
        return data

    def read_text_file(self, node_id: str, path_str: str) -> str:
        relative = validate_relative_file_path(path_str)
        rel_str = relative.as_posix()
        record = self._overlay.resolve_file(node_id, rel_str)
        if record is None or record.is_dir:
            raise AppError(
                "INVALID_FILE_PATH",
                "Requested file does not exist.",
                status_code=404,
            )
        return _decode_content(record.content)

    def write_file(
        self, node_id: str, path_str: str, content: str, mode: str
    ) -> int:
        relative = validate_relative_file_path(path_str)
        rel_str = relative.as_posix()

        if mode == "append":
            existing = self._overlay.resolve_file(node_id, rel_str)
            if existing is not None and existing.content is not None:
                content = _decode_content(existing.content) + content

        content_bytes = content.encode("utf-8")
        return self._overlay.write_file(node_id, rel_str, content_bytes)

    def delete_file(self, node_id: str, path_str: str) -> None:
        relative = validate_relative_file_path(path_str)
        rel_str = relative.as_posix()
        self._overlay.delete_file(node_id, rel_str)

    def diff_nodes(self, from_node_id: str, to_node_id: str) -> DiffDTO:
        before = self.read_text_files(from_node_id)
        after = self.read_text_files(to_node_id)

        files: list[DiffFileDTO] = []
        all_paths = sorted(set(before) | set(after))
        for path in all_paths:
            b = before.get(path)
            a = after.get(path)
            if b is None:
                status = "added"
            elif a is None:
                status = "removed"
            elif a == b:
                status = "unchanged"
            else:
                status = "modified"

            if status == "unchanged":
                continue

            diff_lines = difflib.unified_diff(
                (b or "").splitlines(),
                (a or "").splitlines(),
                fromfile=f"{from_node_id}:{path}",
                tofile=f"{to_node_id}:{path}",
                lineterm="",
            )
            files.append(
                DiffFileDTO(path=path, status=status, diff="\n".join(diff_lines))
            )

        return DiffDTO(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            files=files,
        )
