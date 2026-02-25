from __future__ import annotations

import difflib
from pathlib import Path

from app.core.errors import AppError
from app.core.models import NodeRecord
from app.core.schemas import DiffDTO, DiffFileDTO, FileEntryDTO
from app.utils.paths import safe_join, validate_relative_file_path


class FileService:
    def list_files(self, node: NodeRecord) -> list[FileEntryDTO]:
        merged = Path(node.merged)
        entries: list[FileEntryDTO] = []
        if not merged.exists():
            return entries

        for path in sorted(merged.rglob("*")):
            rel = path.relative_to(merged).as_posix()
            stat = path.stat()
            entries.append(
                FileEntryDTO(
                    path=rel,
                    type="dir" if path.is_dir() else "file",
                    size=0 if path.is_dir() else stat.st_size,
                    mtime=stat.st_mtime,
                )
            )
        return entries

    def read_text_files(self, node: NodeRecord) -> dict[str, str]:
        merged = Path(node.merged)
        data: dict[str, str] = {}
        if not merged.exists():
            return data

        for path in sorted(merged.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".txt", ".md"}:
                continue
            rel = path.relative_to(merged).as_posix()
            data[rel] = path.read_text(encoding="utf-8", errors="ignore")
        return data

    def read_text_file(self, node: NodeRecord, path_str: str) -> str:
        relative = validate_relative_file_path(path_str)
        merged = Path(node.merged)
        target = safe_join(merged, relative)
        if not target.exists() or not target.is_file():
            raise AppError("INVALID_FILE_PATH", "Requested file does not exist.", status_code=404)
        return target.read_text(encoding="utf-8", errors="ignore")

    def list_files_from_root(self, root: Path) -> list[FileEntryDTO]:
        entries: list[FileEntryDTO] = []
        if not root.exists():
            return entries

        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root).as_posix()
            stat = path.stat()
            entries.append(
                FileEntryDTO(
                    path=rel,
                    type="dir" if path.is_dir() else "file",
                    size=0 if path.is_dir() else stat.st_size,
                    mtime=stat.st_mtime,
                )
            )
        return entries

    def write_file(self, node: NodeRecord, path_str: str, content: str, mode: str) -> int:
        relative = validate_relative_file_path(path_str)
        merged = Path(node.merged)
        target = safe_join(merged, relative)
        target.parent.mkdir(parents=True, exist_ok=True)

        write_mode = "a" if mode == "append" else "w"
        with target.open(write_mode, encoding="utf-8") as handle:
            written = handle.write(content)
        return written

    def delete_file(self, node: NodeRecord, path_str: str) -> None:
        relative = validate_relative_file_path(path_str)
        merged = Path(node.merged)
        target = safe_join(merged, relative)
        if not target.exists():
            raise AppError("INVALID_FILE_PATH", "File does not exist in selected node merged view.", status_code=404)
        if target.is_dir():
            raise AppError("INVALID_FILE_PATH", "Deleting directories is not supported.", status_code=400)
        target.unlink()

    def diff_nodes(self, from_node: NodeRecord, to_node: NodeRecord) -> DiffDTO:
        before = self.read_text_files(from_node)
        after = self.read_text_files(to_node)

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
                fromfile=f"{from_node.node_id}:{path}",
                tofile=f"{to_node.node_id}:{path}",
                lineterm="",
            )
            files.append(DiffFileDTO(path=path, status=status, diff="\n".join(diff_lines)))

        return DiffDTO(from_node_id=from_node.node_id, to_node_id=to_node.node_id, files=files)
