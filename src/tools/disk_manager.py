"""Инструмент для работы с разделами диска."""

import logging
import platform
import subprocess
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


class DiskManager:
    """Управление разделами и блочными устройствами."""

    def list_partitions(self) -> list[dict]:
        """
        Возвращает все разделы с mountpoint, filesystem, size, used, free.
        """
        partitions = []
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "filesystem": part.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                        "total_human": self._human_size(usage.total),
                        "used_human": self._human_size(usage.used),
                        "free_human": self._human_size(usage.free),
                        "opts": part.opts,
                    })
                except (PermissionError, OSError):
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "filesystem": part.fstype,
                        "error": "нет доступа",
                    })
        except Exception as e:
            logger.error(f"list_partitions error: {e}")
        return partitions

    def get_partition_info(self, partition: str) -> dict:
        """Возвращает подробную информацию о разделе."""
        try:
            usage = psutil.disk_usage(partition)
            # Ищем в списке разделов
            for part in psutil.disk_partitions(all=True):
                if part.mountpoint == partition or part.device == partition:
                    return {
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "filesystem": part.fstype,
                        "opts": part.opts,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                        "total_human": self._human_size(usage.total),
                        "used_human": self._human_size(usage.used),
                        "free_human": self._human_size(usage.free),
                    }
            # Если не нашли в списке — возвращаем только usage
            return {
                "mountpoint": partition,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
                "total_human": self._human_size(usage.total),
                "used_human": self._human_size(usage.used),
                "free_human": self._human_size(usage.free),
            }
        except Exception as e:
            logger.error(f"get_partition_info error: {e}")
            return {"error": str(e)}

    def mount_partition(
        self,
        device: str,
        mountpoint: str,
        filesystem: str = "",
        password: Optional[str] = None,
    ) -> bool:
        """
        Монтирует раздел. Требует sudo.
        password — пароль sudo (если None — пробует без пароля).
        """
        if platform.system() == "Windows":
            logger.error("mount_partition не поддерживается на Windows")
            return False
        try:
            cmd = ["mount"]
            if filesystem:
                cmd += ["-t", filesystem]
            cmd += [device, mountpoint]

            if password:
                proc = subprocess.run(
                    ["sudo", "-S"] + cmd,
                    input=(password + "\n").encode(),
                    capture_output=True,
                    timeout=30,
                )
            else:
                proc = subprocess.run(
                    ["sudo"] + cmd,
                    capture_output=True,
                    timeout=30,
                )
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"mount_partition error: {e}")
            return False

    def unmount_partition(
        self,
        mountpoint: str,
        force: bool = False,
        password: Optional[str] = None,
    ) -> bool:
        """
        Размонтирует раздел. Требует sudo.
        """
        if platform.system() == "Windows":
            logger.error("unmount_partition не поддерживается на Windows")
            return False
        try:
            cmd = ["umount"]
            if force:
                cmd.append("-f")
            cmd.append(mountpoint)

            if password:
                proc = subprocess.run(
                    ["sudo", "-S"] + cmd,
                    input=(password + "\n").encode(),
                    capture_output=True,
                    timeout=30,
                )
            else:
                proc = subprocess.run(
                    ["sudo"] + cmd,
                    capture_output=True,
                    timeout=30,
                )
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"unmount_partition error: {e}")
            return False

    def list_block_devices(self) -> list[dict]:
        """
        Возвращает информацию о блочных устройствах (аналог lsblk).
        """
        if platform.system() == "Windows":
            return self._list_windows_drives()

        try:
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL,SERIAL,VENDOR"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                return data.get("blockdevices", [])
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

        # Fallback: используем psutil
        return self._fallback_block_devices()

    def _fallback_block_devices(self) -> list[dict]:
        """Fallback для получения блочных устройств через psutil."""
        devices = {}
        for part in psutil.disk_partitions(all=True):
            dev = part.device
            if dev not in devices:
                devices[dev] = {
                    "name": dev,
                    "mountpoints": [],
                    "fstype": part.fstype,
                }
            devices[dev]["mountpoints"].append(part.mountpoint)

        result = []
        for dev_info in devices.values():
            try:
                if dev_info["mountpoints"]:
                    usage = psutil.disk_usage(dev_info["mountpoints"][0])
                    dev_info["size"] = self._human_size(usage.total)
            except Exception:
                pass
            result.append(dev_info)
        return result

    def _list_windows_drives(self) -> list[dict]:
        """Список дисков на Windows."""
        drives = []
        try:
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drives.append({
                        "name": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "size": self._human_size(usage.total),
                        "used": self._human_size(usage.used),
                        "free": self._human_size(usage.free),
                    })
                except Exception:
                    drives.append({"name": part.device, "mountpoint": part.mountpoint})
        except Exception as e:
            logger.error(f"_list_windows_drives error: {e}")
        return drives

    @staticmethod
    def _human_size(size: int) -> str:
        """Конвертирует байты в читаемый формат."""
        for unit in ["Б", "КБ", "МБ", "ГБ", "ТБ"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ПБ"
