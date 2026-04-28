"""Архиватор: zip, tar.gz, tar.bz2, tar.xz."""

from __future__ import annotations

import logging
import os
import tarfile
import zipfile
from typing import Any

logger = logging.getLogger(__name__)


_TAR_FORMATS = {
    "tar": ("w", ""),
    "tar.gz": ("w:gz", ".tar.gz"),
    "tgz": ("w:gz", ".tgz"),
    "tar.bz2": ("w:bz2", ".tar.bz2"),
    "tbz2": ("w:bz2", ".tbz2"),
    "tar.xz": ("w:xz", ".tar.xz"),
    "txz": ("w:xz", ".txz"),
}


class ArchiveTool:
    """Создание/распаковка/просмотр архивов."""

    def create_archive(
        self,
        source: str,
        destination: str,
        format: str = "tar.gz",
    ) -> dict[str, Any]:
        """Создать архив. format: zip, tar, tar.gz, tar.bz2, tar.xz."""
        try:
            source = os.path.expanduser(source)
            destination = os.path.expanduser(destination)
            if not os.path.exists(source):
                return {"error": f"Источник не существует: {source}"}

            os.makedirs(os.path.dirname(os.path.abspath(destination)) or ".", exist_ok=True)

            fmt = format.lower().lstrip(".")
            base_name = os.path.basename(source.rstrip("/\\")) or "archive"

            if fmt == "zip":
                if not destination.endswith(".zip"):
                    destination += ".zip"
                with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
                    if os.path.isfile(source):
                        zf.write(source, arcname=os.path.basename(source))
                    else:
                        for root, _dirs, files in os.walk(source):
                            for f in files:
                                full = os.path.join(root, f)
                                arc = os.path.relpath(full, os.path.dirname(source))
                                zf.write(full, arcname=arc)
            elif fmt in _TAR_FORMATS:
                mode, ext = _TAR_FORMATS[fmt]
                if ext and not destination.endswith(ext):
                    destination += ext
                with tarfile.open(destination, mode) as tf:
                    tf.add(source, arcname=base_name)
            else:
                return {"error": f"Неподдерживаемый формат: {format}"}

            size = os.path.getsize(destination)
            return {
                "success": True,
                "path": destination,
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "format": fmt,
            }
        except Exception as e:
            return {"error": f"create_archive error: {e}"}

    def extract_archive(self, source: str, destination: str) -> dict[str, Any]:
        """Распаковать архив (автоопределение формата)."""
        try:
            source = os.path.expanduser(source)
            destination = os.path.expanduser(destination)
            if not os.path.isfile(source):
                return {"error": f"Архив не найден: {source}"}
            os.makedirs(destination, exist_ok=True)

            extracted = []
            if zipfile.is_zipfile(source):
                with zipfile.ZipFile(source) as zf:
                    zf.extractall(destination)
                    extracted = zf.namelist()
            elif tarfile.is_tarfile(source):
                with tarfile.open(source) as tf:
                    tf.extractall(destination)
                    extracted = tf.getnames()
            else:
                return {"error": "Неизвестный формат архива"}

            return {
                "success": True,
                "destination": destination,
                "files_extracted": len(extracted),
                "first_files": extracted[:20],
            }
        except Exception as e:
            return {"error": f"extract_archive error: {e}"}

    def list_archive(self, path: str) -> dict[str, Any]:
        """Список файлов в архиве."""
        try:
            path = os.path.expanduser(path)
            if not os.path.isfile(path):
                return {"error": f"Файл не найден: {path}"}
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as zf:
                    items = [
                        {"name": i.filename, "size": i.file_size, "compressed": i.compress_size}
                        for i in zf.infolist()
                    ]
                return {"format": "zip", "count": len(items), "files": items[:500]}
            if tarfile.is_tarfile(path):
                with tarfile.open(path) as tf:
                    items = [{"name": m.name, "size": m.size, "type": "dir" if m.isdir() else "file"} for m in tf.getmembers()]
                return {"format": "tar", "count": len(items), "files": items[:500]}
            return {"error": "Неизвестный формат архива"}
        except Exception as e:
            return {"error": f"list_archive error: {e}"}

    def get_archive_size(self, path: str) -> dict[str, Any]:
        """Размер архива и суммарный размер после распаковки."""
        try:
            path = os.path.expanduser(path)
            if not os.path.isfile(path):
                return {"error": f"Файл не найден: {path}"}
            archive_size = os.path.getsize(path)
            uncompressed = 0
            count = 0
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as zf:
                    for i in zf.infolist():
                        uncompressed += i.file_size
                        count += 1
            elif tarfile.is_tarfile(path):
                with tarfile.open(path) as tf:
                    for m in tf.getmembers():
                        uncompressed += m.size
                        count += 1
            else:
                return {"error": "Неизвестный формат архива"}
            ratio = (archive_size / uncompressed) if uncompressed else 0
            return {
                "archive_size_bytes": archive_size,
                "archive_size_mb": round(archive_size / (1024 * 1024), 2),
                "uncompressed_bytes": uncompressed,
                "uncompressed_mb": round(uncompressed / (1024 * 1024), 2),
                "compression_ratio": round(ratio, 3),
                "files_count": count,
            }
        except Exception as e:
            return {"error": f"get_archive_size error: {e}"}
