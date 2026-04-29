"""Сетевые инструменты: ping, проверка портов, скачивание файлов, IP."""

from __future__ import annotations

import logging
import os
import re
import socket
import subprocess
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NetworkTool:
    """Сетевые операции."""

    def ping(self, host: str, count: int = 4) -> dict[str, Any]:
        """Пинг хоста, возвращает avg/min/max задержку и % потерь."""
        try:
            cmd = ["ping", "-c", str(count), "-W", "3", host]

            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=count * 5 + 5
            )
            output = proc.stdout + proc.stderr

            avg_ms: Optional[float] = None
            min_ms: Optional[float] = None
            max_ms: Optional[float] = None
            loss_pct: Optional[float] = None

            # Linux: rtt min/avg/max/mdev = 0.1/0.2/0.3/0.0 ms
            m = re.search(r"min/avg/max[^=]*=\s*([\d.]+)/([\d.]+)/([\d.]+)", output)
            if m:
                min_ms = float(m.group(1))
                avg_ms = float(m.group(2))
                max_ms = float(m.group(3))

            m_loss = re.search(r"(\d+(?:\.\d+)?)%\s*(?:packet\s+)?loss", output)
            if m_loss:
                loss_pct = float(m_loss.group(1))

            return {
                "host": host,
                "count": count,
                "avg_ms": avg_ms,
                "min_ms": min_ms,
                "max_ms": max_ms,
                "loss_percent": loss_pct,
                "success": proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Таймаут пинга {host}"}
        except FileNotFoundError:
            return {"error": "Команда ping не найдена"}
        except Exception as e:
            return {"error": f"ping error: {e}"}

    def check_port(self, host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
        """Проверить, открыт ли TCP-порт."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                result = s.connect_ex((host, int(port)))
                return {
                    "host": host,
                    "port": int(port),
                    "open": result == 0,
                }
        except socket.gaierror:
            return {"error": f"Не удалось разрешить хост: {host}"}
        except Exception as e:
            return {"error": f"check_port error: {e}"}

    def download_file(
        self,
        url: str,
        destination: str,
        show_progress: bool = True,
    ) -> dict[str, Any]:
        """Скачать файл по URL. Возвращает путь и размер."""
        try:
            import requests  # type: ignore
        except ImportError:
            return {"error": "Не установлен пакет requests"}

        try:
            destination = os.path.expanduser(destination)
            # Если destination — директория, формируем имя файла из URL
            if os.path.isdir(destination):
                filename = url.rstrip("/").split("/")[-1] or "downloaded_file"
                destination = os.path.join(destination, filename)
            os.makedirs(os.path.dirname(os.path.abspath(destination)) or ".", exist_ok=True)

            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0))
                downloaded = 0
                with open(destination, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

            return {
                "success": True,
                "path": destination,
                "size_bytes": downloaded,
                "size_mb": round(downloaded / (1024 * 1024), 2),
                "expected_bytes": total,
            }
        except Exception as e:
            return {"error": f"download_file error: {e}"}

    def get_network_speed(self, interval: float = 1.0) -> dict[str, Any]:
        """Текущая скорость входящего/исходящего трафика."""
        try:
            import psutil  # type: ignore
            t1 = psutil.net_io_counters()
            time.sleep(interval)
            t2 = psutil.net_io_counters()
            rx = (t2.bytes_recv - t1.bytes_recv) / interval
            tx = (t2.bytes_sent - t1.bytes_sent) / interval
            return {
                "rx_mbps": round(rx / (1024 * 1024), 3),
                "tx_mbps": round(tx / (1024 * 1024), 3),
                "rx_bytes_per_sec": int(rx),
                "tx_bytes_per_sec": int(tx),
            }
        except Exception as e:
            return {"error": f"get_network_speed error: {e}"}

    def get_public_ip(self) -> dict[str, Any]:
        """Получить публичный IP адрес."""
        try:
            import requests  # type: ignore
            for url in (
                "https://api.ipify.org",
                "https://ifconfig.me/ip",
                "https://icanhazip.com",
            ):
                try:
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200:
                        ip = r.text.strip()
                        if ip:
                            return {"ip": ip, "source": url}
                except Exception:
                    continue
            return {"error": "Не удалось определить публичный IP"}
        except ImportError:
            return {"error": "Не установлен пакет requests"}

    def get_interfaces(self) -> list[dict[str, Any]]:
        """Список сетевых интерфейсов с IP-адресами."""
        try:
            import psutil  # type: ignore
            result = []
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for name, addr_list in addrs.items():
                ipv4 = []
                ipv6 = []
                mac = ""
                for a in addr_list:
                    family = getattr(a, "family", None)
                    fam_name = getattr(family, "name", str(family))
                    if "AF_INET6" in str(fam_name):
                        ipv6.append(a.address)
                    elif "AF_INET" in str(fam_name) or fam_name == "2":
                        ipv4.append(a.address)
                    elif "AF_PACKET" in str(fam_name) or "AF_LINK" in str(fam_name):
                        mac = a.address
                st = stats.get(name)
                result.append({
                    "name": name,
                    "ipv4": ipv4,
                    "ipv6": ipv6,
                    "mac": mac,
                    "is_up": bool(st.isup) if st else None,
                    "speed_mbps": st.speed if st else None,
                })
            return result
        except Exception as e:
            return [{"error": f"get_interfaces error: {e}"}]
