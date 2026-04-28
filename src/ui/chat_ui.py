"""Главный интерфейс чата CLI Assistant на Textual."""

import asyncio
import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Optional


# ─── Markdown sanitizer ───────────────────────────────────────────────────────
# Модели иногда игнорируют системный промпт и присылают markdown-разметку.
# Мы рендерим текст в TUI как plain-text, поэтому markdown-символы выглядят
# мусором. Эта функция чистит markdown потоково: вход — произвольная строка
# (в т.ч. кусок стриминга), выход — та же строка без markdown-разметки.
#
# ВАЖНО: поскольку чанки стриминга могут разрезать markdown-разметку
# (например, чанк 1 = "**жир", чанк 2 = "ный**"), мы применяем sanitizer
# к УЖЕ СОБРАННОМУ полному тексту в виджете AssistantMessage, а не к каждому
# чанку отдельно. См. AssistantMessage.append_text.

_MD_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+\-]*\n?")
_MD_FENCE_END_RE = re.compile(r"```")
_MD_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_MD_BOLD_UND_RE = re.compile(r"__(.+?)__", re.DOTALL)
_MD_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_MD_ITALIC_UND_RE = re.compile(r"(?<!_)_([^_\n]+)_(?!_)")
_MD_STRIKE_RE = re.compile(r"~~(.+?)~~", re.DOTALL)
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_BLOCKQUOTE_RE = re.compile(r"^>\s?", re.MULTILINE)
_MD_LIST_BULLET_RE = re.compile(r"^(\s*)[-*+]\s+", re.MULTILINE)
_MD_HR_RE = re.compile(r"^\s*([-*_])\s*\1\s*\1[\s\1]*$", re.MULTILINE)


def sanitize_markdown(text: str) -> str:
    """Удаляет markdown-разметку из текста, возвращая чистый plain-text.

    Что чистится:
    * блоки кода ```...``` → содержимое без обрамления;
    * inline `code` → code (без бэктиков);
    * **bold**, __bold__ → bold;
    * *italic*, _italic_ → italic (только если не это часть слова);
    * ~~strike~~ → strike;
    * заголовки `# Заг` → `Заг`;
    * markdown-ссылки `[text](url)` → `text (url)`;
    * blockquote `> ...` → `...`;
    * маркированные списки `- item` / `* item` → `• item`;
    * горизонтальные линии (---, ***) → пустая строка.

    Дополнительно: НЕ трогает квадратные скобки в `[[`, чтобы не сломать
    последующее экранирование Textual markup (мы экранируем `[` отдельно
    в `AssistantMessage.append_text`).
    """
    if not text:
        return text
    s = text
    # 1) Блоки кода — заменяем тройные бэктики на пустоту, оставляя содержимое.
    s = _MD_FENCE_RE.sub("", s)
    s = _MD_FENCE_END_RE.sub("", s)
    # 2) Inline code
    s = _MD_INLINE_CODE_RE.sub(r"\1", s)
    # 3) Bold/italic/strike
    s = _MD_BOLD_RE.sub(r"\1", s)
    s = _MD_BOLD_UND_RE.sub(r"\1", s)
    s = _MD_ITALIC_STAR_RE.sub(r"\1", s)
    s = _MD_ITALIC_UND_RE.sub(r"\1", s)
    s = _MD_STRIKE_RE.sub(r"\1", s)
    # 4) Заголовки
    s = _MD_HEADING_RE.sub("", s)
    # 5) Ссылки [text](url) → "text (url)"
    s = _MD_LINK_RE.sub(r"\1 (\2)", s)
    # 6) Blockquote
    s = _MD_BLOCKQUOTE_RE.sub("", s)
    # 7) Маркированные списки → bullet •
    s = _MD_LIST_BULLET_RE.sub(r"\1• ", s)
    # 8) Горизонтальные линии
    s = _MD_HR_RE.sub("", s)
    return s


from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Select, Static

from ..core.assistant import Assistant
from ..settings.config_manager import get_config_manager
from .themes import get_theme

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

# Опциональный pynvml для NVIDIA GPU метрик
try:
    import pynvml  # type: ignore
    try:
        pynvml.nvmlInit()
        _HAS_NVML = True
    except Exception:
        _HAS_NVML = False
except Exception:  # pragma: no cover
    pynvml = None  # type: ignore
    _HAS_NVML = False


# ─── Виджеты сообщений ────────────────────────────────────────────────────────

class UserMessage(Static):
    """Пузырь сообщения пользователя (выровнен вправо)."""

    def __init__(self, text: str, timestamp: str = "") -> None:
        content = f"[bold cyan]{text}[/bold cyan]"
        if timestamp:
            content += f"\n[dim]{timestamp}  👤 Вы[/dim]"
        super().__init__(content, classes="user-bubble")


class AssistantMessage(Static):
    """Пузырь сообщения ассистента (выровнен влево).

    Накапливает СЫРОЙ текст модели в `_raw`, при каждом обновлении
    прогоняет его через `sanitize_markdown` и экранирует все «[», чтобы
    Textual не пытался интерпретировать их как разметку. К итоговому
    содержимому добавляется заголовок «🤖 Ассистент <timestamp>».

    ВАЖНО: НЕ переопределяем `_render()` — это внутренний метод Textual,
    он должен возвращать Visual-объект, а не строку. Вместо этого у нас
    есть свой helper `_compose_display`, и мы передаём его результат
    в стандартный `Static.update()`.
    """

    def __init__(self, timestamp: str = "") -> None:
        if timestamp:
            self._header = f"[dim]🤖 Ассистент  {timestamp}[/dim]\n"
        else:
            self._header = "[dim]🤖 Ассистент[/dim]\n"
        message_id = f"assistant-msg-{uuid.uuid4().hex[:8]}"
        super().__init__(self._header, classes="assistant-bubble", id=message_id)
        # Сырой текст ассистента (без header-разметки и без markdown)
        self._raw: str = ""
        # Совместимость со старым кодом: _text используется в _close_current_assistant_bubble
        self._text: str = self._header

    def _compose_display(self) -> str:
        """Собирает финальную строку для показа: header + чистый plain-text."""
        cleaned = sanitize_markdown(self._raw)
        # Экранируем «[» чтобы Textual не вычислял разметку из текста модели
        safe = cleaned.replace("[", r"\[")
        full = self._header + safe
        self._text = full
        return full

    def append_text(self, chunk: str) -> None:
        if not chunk:
            return
        self._raw += chunk
        try:
            self.update(self._compose_display())
        except Exception:
            # Если что-то с разметкой пошло не так — показываем максимально безопасную версию
            try:
                self.update(self._header + self._raw.replace("[", r"\["))
            except Exception:
                pass

    def finalize(self) -> None:
        # Финальная пере-санитизация на полном тексте — на случай, если
        # markdown-разметка была разрезана между чанками.
        try:
            self.update(self._compose_display())
        except Exception:
            pass
        try:
            self.remove_id()
        except Exception:
            pass



    def remove_id(self) -> None:
        try:
            self.id = None
        except Exception:
            pass


class ToolCallWidget(Static):
    """Виджет отображения вызова инструмента."""

    def __init__(self, tool_name: str, tool_input: dict) -> None:
        params = ", ".join(f"{k}={repr(v)[:30]}" for k, v in list(tool_input.items())[:3])
        content = (
            f"[bold yellow]🔧 Инструмент:[/bold yellow] [cyan]{tool_name}[/cyan]\n"
            f"[dim]{params}[/dim]\n"
            f"[yellow]⏳ Выполняю...[/yellow]"
        )
        super().__init__(content, classes="tool-call", id=f"tool-{id(self)}")
        self._tool_name = tool_name

    def set_done(self, elapsed: float) -> None:
        content = (
            f"[bold yellow]🔧 Инструмент:[/bold yellow] [cyan]{self._tool_name}[/cyan]\n"
            f"[green]✅ Готово за {elapsed:.2f}с[/green]"
        )
        self.update(content)

    def set_error(self, error: str) -> None:
        content = (
            f"[bold yellow]🔧 Инструмент:[/bold yellow] [cyan]{self._tool_name}[/cyan]\n"
            f"[red]❌ Ошибка: {error[:80]}[/red]"
        )
        self.update(content)


class ConfirmDialog(Container):
    """Диалог подтверждения опасного действия (Y/n + Enter или кнопки)."""

    can_focus = True

    def __init__(self, action: str, target: str, callback) -> None:
        super().__init__(classes="confirm-dialog")
        self._callback = callback
        self._action = str(action)
        self._target = str(target)[:200]
        self._done = False

    def compose(self) -> ComposeResult:
        safe_action = self._action.replace("[", r"\[")
        safe_target = self._target.replace("[", r"\[")
        yield Static(
            f"[bold yellow]⚠️  ПОДТВЕРЖДЕНИЕ ДЕЙСТВИЯ[/bold yellow]\n\n"
            f"[white]{safe_action}[/white]\n"
            f"[cyan]{safe_target}[/cyan]\n\n"
            f"Введите [bold green]y[/bold green] для подтверждения "
            f"или [bold red]n[/bold red] для отмены, затем Enter:",
            id="confirm-text",
        )
        yield Input(placeholder="y / n", id="confirm-input")
        yield Horizontal(
            Button("✅ Да (y)", id="btn-confirm-yes", variant="success"),
            Button("❌ Нет (n)", id="btn-confirm-no", variant="error"),
            id="confirm-buttons",
        )

    def on_mount(self) -> None:
        """Ставим фокус на поле ввода при открытии."""
        def set_focus(*args, **kwargs):
            try:
                self.query_one("#confirm-input", Input).focus()
            except Exception:
                pass
        self.call_later(set_focus)

    async def _resolve(self, yes: bool) -> None:
        """Завершает диалог с результатом и возвращает фокус в основной input."""
        if self._done:
            return
        self._done = True
        try:
            self.remove()
        except Exception:
            pass
        try:
            if asyncio.iscoroutinefunction(self._callback):
                await self._callback(yes)
            else:
                self._callback(yes)
        except Exception:
            pass
        # Возвращаем фокус в основное поле ввода
        try:
            app = self.app
            if app:
                app.query_one("#message-input", Input).focus()
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Обрабатываем Enter в поле ввода (y/yes/да → True, иначе False)."""
        if event.input.id == "confirm-input":
            value = (event.value or "").strip().lower()
            yes = value in ("y", "yes", "д", "да", "")  # пустая строка = Y по умолчанию
            event.stop()
            await self._resolve(yes)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm-yes":
            await self._resolve(True)
        elif event.button.id == "btn-confirm-no":
            await self._resolve(False)

    def on_key(self, event) -> None:
        """Escape = отмена."""
        try:
            if event.key == "escape":
                event.stop()
                asyncio.create_task(self._resolve(False))
        except Exception:
            pass


class SudoPasswordDialog(Container):
    """Диалог ввода пароля sudo."""

    def __init__(
        self,
        callback,
        title: str = "[bold yellow]🔐 Требуется пароль sudo[/bold yellow]",
        placeholder: str = "Введите пароль sudo...",
    ) -> None:
        super().__init__(id="sudo-dialog")
        self._callback = callback
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Static(self._title, id="sudo-title")
        yield Input(placeholder=self._placeholder, password=True, id="sudo-input")
        yield Horizontal(
            Button("Подтвердить", id="btn-sudo-ok", variant="primary"),
            Button("Отмена", id="btn-sudo-cancel"),
            id="sudo-buttons",
        )

    can_focus = True

    def on_mount(self) -> None:
        """Автоматически ставим фокус на поле ввода при открытии диалога."""
        def set_focus(*args, **kwargs):
            try:
                input_widget = self.query_one("#sudo-input", Input)
                input_widget.focus()
            except Exception:
                pass

        self.call_later(set_focus)

    def on_key(self, event) -> None:
        """Ловим нажатие Escape для закрытия диалога без ввода."""
        try:
            if event.key == "escape":
                self._close_dialog()
                event.stop()
        except Exception:
            pass
    
    def _close_dialog(self) -> None:
        """Закрывает диалог и вызывает callback."""
        try:
            self.remove()
            if asyncio.iscoroutinefunction(self._callback):
                asyncio.create_task(self._callback(""))
            else:
                self._callback("")
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Обрабатываем Enter в поле пароля."""
        if event.input.id == "sudo-input":
            password = event.value
            self.remove()
            if asyncio.iscoroutinefunction(self._callback):
                await self._callback(password)
            else:
                self._callback(password)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-sudo-ok":
            password = self.query_one("#sudo-input", Input).value
            self.remove()
            if asyncio.iscoroutinefunction(self._callback):
                await self._callback(password)
            else:
                self._callback(password)
        elif event.button.id == "btn-sudo-cancel":
            self.remove()
            if asyncio.iscoroutinefunction(self._callback):
                await self._callback("")
            else:
                self._callback("")

    CSS = """
    #sudo-dialog {
        background: #1a2744;
        border: round #ff9800;
        padding: 1 2;
        margin: 1 2;
        height: 11;
        min-height: 11;
        width: 100%;
        layer: dialog;
    }
    #sudo-title {
        color: #ff9800;
        margin-bottom: 1;
        height: 1;
    }
    #sudo-input {
        height: 3;
        margin-bottom: 1;
    }
    #sudo-buttons {
        height: 3;
        margin-top: 0;
    }
    #sudo-buttons Button { margin-right: 1; }
    """


# ─── Боковая панель ───────────────────────────────────────────────────────────

def _human_bytes(n: float) -> str:
    """Преобразует байты в человекочитаемый размер."""
    try:
        n = float(n)
    except Exception:
        return "—"
    units = ["Б", "КБ", "МБ", "ГБ", "ТБ", "ПБ"]
    i = 0
    while n >= 1024.0 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    if i == 0:
        return f"{int(n)} {units[i]}"
    return f"{n:.1f} {units[i]}"


def _bar(percent: float, width: int = 12) -> str:
    """Рисует ASCII прогресс-бар на `width` символов с цветом по уровню."""
    try:
        p = max(0.0, min(100.0, float(percent)))
    except Exception:
        p = 0.0
    filled = int(round(p / 100.0 * width))
    if p >= 90:
        color = "red"
    elif p >= 75:
        color = "yellow"
    else:
        color = "green"
    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}] {p:4.0f}%"


class SidebarWidget(Static):
    """Расширенная боковая панель с метриками системы.

    Показывает: CPU, GPU (если есть NVIDIA + pynvml), RAM, VRAM, диски
    (с пометкой съёмных), скорости сети, скорости диск I/O, top-5 процессов
    по памяти, последние действия и текущий путь.
    """

    last_actions: reactive[list] = reactive([])

    # Внутреннее состояние, не reactive — обновляется тиком set_interval.
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cpu_percent: float = 0.0
        self._cpu_count: int = 1
        self._ram_used: int = 0
        self._ram_total: int = 0
        self._ram_percent: float = 0.0

        self._gpu_name: str = ""
        self._gpu_util: float = 0.0
        self._vram_used: int = 0
        self._vram_total: int = 0
        self._vram_percent: float = 0.0

        self._disks: list = []  # [{mount, used, total, percent, removable}]
        self._net_up: float = 0.0  # B/s
        self._net_down: float = 0.0
        self._io_read: float = 0.0
        self._io_write: float = 0.0
        self._procs: list = []  # [{name, mem_mb, cpu}]

        # Снимки счётчиков для расчёта скоростей
        self._last_net = None
        self._last_io = None
        self._last_ts = None
        self._cwd: str = ""

    # ── Сбор метрик ────────────────────────────────────────────────────────

    def collect(self, cwd: str = "") -> None:
        """Собирает свежие метрики (вызывается из app по таймеру)."""
        self._cwd = cwd or self._cwd
        if psutil is None:
            return
        try:
            self._cpu_percent = float(psutil.cpu_percent(interval=None))
            self._cpu_count = psutil.cpu_count(logical=True) or 1
            vm = psutil.virtual_memory()
            self._ram_used = int(vm.used)
            self._ram_total = int(vm.total)
            self._ram_percent = float(vm.percent)
        except Exception:
            pass

        # Диски
        try:
            disks = []
            removable_devs = set()
            try:
                # На Linux у removable-партиций обычно 'removable' в opts отсутствует,
                # эвристика: device начинается с /dev/sd[a-z] и mountpoint в /media|/run/media
                for p in psutil.disk_partitions(all=False):
                    mp = p.mountpoint
                    if mp.startswith("/media") or mp.startswith("/run/media") or mp.startswith("/mnt"):
                        removable_devs.add(mp)
                    if "removable" in (p.opts or "").lower():
                        removable_devs.add(mp)
            except Exception:
                pass
            try:
                seen = set()
                for p in psutil.disk_partitions(all=False):
                    mp = p.mountpoint
                    # Игнорируем псевдо-фс
                    fstype = (p.fstype or "").lower()
                    if not fstype or fstype in ("squashfs", "tmpfs", "devtmpfs", "proc", "sysfs", "overlay"):
                        continue
                    if mp in seen:
                        continue
                    seen.add(mp)
                    try:
                        u = psutil.disk_usage(mp)
                    except Exception:
                        continue
                    disks.append({
                        "mount": mp,
                        "used": int(u.used),
                        "total": int(u.total),
                        "percent": float(u.percent),
                        "removable": mp in removable_devs,
                    })
            except Exception:
                pass
            # Сортируем: сначала root, потом по размеру
            disks.sort(key=lambda d: (d["mount"] != "/", -d["total"]))
            self._disks = disks[:6]
        except Exception:
            self._disks = []

        # Сеть и диск I/O — через дельты
        import time
        now = time.time()
        try:
            net = psutil.net_io_counters()
            io = psutil.disk_io_counters()
            if self._last_net is not None and self._last_ts is not None:
                dt = max(0.001, now - self._last_ts)
                self._net_up = max(0.0, (net.bytes_sent - self._last_net.bytes_sent) / dt)
                self._net_down = max(0.0, (net.bytes_recv - self._last_net.bytes_recv) / dt)
                if io and self._last_io is not None:
                    self._io_read = max(0.0, (io.read_bytes - self._last_io.read_bytes) / dt)
                    self._io_write = max(0.0, (io.write_bytes - self._last_io.write_bytes) / dt)
            self._last_net = net
            self._last_io = io
            self._last_ts = now
        except Exception:
            pass

        # Top-5 процессов по памяти
        try:
            procs = []
            for p in psutil.process_iter(["name", "memory_info", "cpu_percent"]):
                try:
                    info = p.info
                    mem = info.get("memory_info")
                    if not mem:
                        continue
                    procs.append({
                        "name": (info.get("name") or "?")[:14],
                        "mem_mb": int(mem.rss / (1024 * 1024)),
                        "cpu": float(info.get("cpu_percent") or 0.0),
                    })
                except Exception:
                    continue
            procs.sort(key=lambda x: x["mem_mb"], reverse=True)
            self._procs = procs[:5]
        except Exception:
            self._procs = []

        # GPU (NVIDIA через NVML — опционально)
        if _HAS_NVML and pynvml is not None:
            try:
                count = pynvml.nvmlDeviceGetCount()
                if count > 0:
                    h = pynvml.nvmlDeviceGetHandleByIndex(0)
                    name = pynvml.nvmlDeviceGetName(h)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="ignore")
                    self._gpu_name = str(name)[:18]
                    util = pynvml.nvmlDeviceGetUtilizationRates(h)
                    self._gpu_util = float(util.gpu)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                    self._vram_used = int(mem.used)
                    self._vram_total = int(mem.total)
                    self._vram_percent = (
                        100.0 * mem.used / mem.total if mem.total else 0.0
                    )
            except Exception:
                pass

        # Принудительный перерендер
        try:
            self.refresh()
        except Exception:
            pass

    # ── Рендер ─────────────────────────────────────────────────────────────

    def render(self) -> str:
        lines: list = []

        # CPU
        lines.append("[bold cyan]ПРОЦЕССОР[/bold cyan]")
        lines.append(f"CPU x{self._cpu_count}")
        lines.append(_bar(self._cpu_percent))

        # GPU (если есть)
        if self._gpu_name:
            lines.append("")
            lines.append("[bold cyan]ВИДЕОКАРТА[/bold cyan]")
            lines.append(f"[dim]{self._gpu_name}[/dim]")
            lines.append(_bar(self._gpu_util))

        # RAM
        lines.append("")
        lines.append("[bold cyan]ПАМЯТЬ[/bold cyan]")
        lines.append(
            f"RAM {_human_bytes(self._ram_used)}/{_human_bytes(self._ram_total)}"
        )
        lines.append(_bar(self._ram_percent))
        if self._vram_total > 0:
            lines.append(
                f"VRAM {_human_bytes(self._vram_used)}/{_human_bytes(self._vram_total)}"
            )
            lines.append(_bar(self._vram_percent))

        # Диски
        lines.append("")
        lines.append("[bold cyan]ДИСКИ[/bold cyan]")
        if not self._disks:
            lines.append("  [dim]нет данных[/dim]")
        for d in self._disks:
            mark = "🔌 " if d["removable"] else ""
            mp = d["mount"]
            if len(mp) > 14:
                mp = mp[:13] + "…"
            lines.append(f"{mark}{mp}")
            lines.append(
                f"  {_human_bytes(d['used'])}/{_human_bytes(d['total'])}"
            )
            lines.append(_bar(d["percent"], width=10))

        # Сеть
        lines.append("")
        lines.append("[bold cyan]СЕТЬ[/bold cyan]")
        lines.append(
            f"↑ {_human_bytes(self._net_up)}/с"
        )
        lines.append(
            f"↓ {_human_bytes(self._net_down)}/с"
        )

        # Диск I/O
        lines.append("")
        lines.append("[bold cyan]ДИСК I/O[/bold cyan]")
        lines.append(f"R {_human_bytes(self._io_read)}/с")
        lines.append(f"W {_human_bytes(self._io_write)}/с")

        # Топ-процессы
        lines.append("")
        lines.append("[bold cyan]ТОП ПРОЦЕССЫ[/bold cyan]")
        if not self._procs:
            lines.append("  [dim]нет данных[/dim]")
        for p in self._procs:
            lines.append(
                f"[dim]{p['name']:<14}[/dim] [yellow]{p['mem_mb']}МБ[/yellow]"
            )

        # Последние действия
        lines.append("")
        lines.append("[bold cyan]ДЕЙСТВИЯ[/bold cyan]")
        if self.last_actions:
            for a in list(self.last_actions)[-5:]:
                safe = str(a).replace("[", r"\[")
                lines.append(f"  [green]✓[/green] {safe}")
        else:
            lines.append("  [dim]нет действий[/dim]")

        # Путь
        lines.append("")
        lines.append("[bold cyan]ПУТЬ[/bold cyan]")
        cwd = self._cwd or ""
        if len(cwd) > 26:
            cwd = "…" + cwd[-25:]
        safe_cwd = cwd.replace("[", r"\[")
        lines.append(f"[dim]{safe_cwd}[/dim]")

        return "\n".join(lines)

    # ── Совместимость со старым API ────────────────────────────────────────

    def update_system_info(self, info: dict) -> None:
        """Обратная совместимость: подхватывает то, что отдаёт TerminalManager."""
        try:
            self._cpu_percent = float(info.get("cpu_percent", self._cpu_percent))
        except Exception:
            pass

    def add_action(self, action: str) -> None:
        actions = list(self.last_actions)
        actions.append(str(action)[:24])
        self.last_actions = actions[-10:]


# ─── Главное приложение ───────────────────────────────────────────────────────

class CLIAssistantApp(App):
    """Главное TUI приложение CLI Assistant."""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Выход"),
        Binding("ctrl+s", "open_settings", "Настройки"),
        Binding("ctrl+l", "clear_chat", "Очистить"),
        Binding("ctrl+h", "show_help", "Помощь"),
        Binding("escape", "cancel_input", "Отмена"),
    ]

    show_sidebar: reactive[bool] = reactive(True)
    is_thinking: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self._config_manager = get_config_manager()
        self._config = self._config_manager.config
        self.assistant = Assistant()
        self._current_assistant_widget: Optional[AssistantMessage] = None
        self._current_tool_widget: Optional[ToolCallWidget] = None
        self._pending_confirm: Optional[asyncio.Future] = None
        self._pending_sudo: Optional[asyncio.Future] = None
        self._setup_assistant_callbacks()

    def _setup_assistant_callbacks(self) -> None:
        """Подключает callbacks ассистента к UI."""
        self.assistant.set_ui_callbacks(
            on_confirm=self._on_confirm_request,
            on_sudo_request=self._on_sudo_request,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            with ScrollableContainer(id="chat-area"):
                yield Static(
                    "[dim]🤖 CLI Assistant готов к работе. Введите сообщение или /help[/dim]",
                    id="chat-placeholder"
                )
            yield SidebarWidget(id="sidebar")
        with Container(id="input-area"):
            with Horizontal(id="input-row"):
                # Селектор активного профиля (слева). Опции выставим в on_mount.
                yield Select(
                    options=[("(нет профилей)", Select.BLANK)],
                    prompt="Профиль",
                    id="profile-selector",
                    allow_blank=True,
                )
                yield Input(
                    placeholder="Введите сообщение или /команду...",
                    id="message-input",
                )
                yield Button("➤", id="btn-send", variant="primary")
        yield Footer()

    async def on_mount(self) -> None:
        """Инициализация при запуске."""
        theme_css = get_theme(self._config.ui.theme)
        self.css = theme_css
        self._update_header()
        # Заполняем селектор профилей
        self._refresh_profile_selector()
        # Запускаем периодическое обновление системной информации (каждые 2с)
        self.set_interval(2.0, self._refresh_system_info)
        self._refresh_system_info()
        # Адаптируем layout под размер терминала
        self._adapt_layout()

    def _refresh_profile_selector(self) -> None:
        """Заполняет/обновляет dropdown с профилями.

        Длинные имена обрезаем эллипсисом в подписи, но в качестве value храним
        полное имя — чтобы переключение работало корректно.
        """
        try:
            sel = self.query_one("#profile-selector", Select)
            profiles = self._config_manager.get_profiles()
            active = self._config_manager.get_active_profile()
            if not profiles:
                sel.set_options([("(нет профилей)", Select.BLANK)])
                sel.value = Select.BLANK
                return
            # Ширина видимой области = 22 минус рамка/стрелка ≈ 16 символов
            max_label = 16
            options = []
            for name in profiles.keys():
                label = name if len(name) <= max_label else name[: max_label - 1] + "…"
                options.append((label, name))
            sel.set_options(options)
            if active and active in profiles:
                try:
                    sel.value = active
                except Exception:
                    pass
        except Exception:
            pass

    def on_resize(self) -> None:
        """Адаптируем layout при изменении размера."""
        self._adapt_layout()

    def _adapt_layout(self) -> None:
        """Скрываем боковую панель при узком терминале."""
        try:
            sidebar = self.query_one("#sidebar", SidebarWidget)
            if self.size.width < 100:
                sidebar.display = False
            else:
                sidebar.display = True
        except Exception:
            pass

    def _update_header(self) -> None:
        """Обновляет заголовок с информацией о провайдере."""
        try:
            provider = self._config.ai.provider
            model = self._config.ai.model
            self.title = f"🤖 CLI Assistant | {provider}: {model}"
            self.sub_title = self.assistant.cwd
        except Exception:
            self.title = "🤖 CLI Assistant"

    def _refresh_system_info(self) -> None:
        """Обновляет системную информацию в боковой панели."""
        try:
            sidebar = self.query_one("#sidebar", SidebarWidget)
            sidebar.collect(self.assistant.cwd)
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Обрабатывает отправку сообщения."""
        if event.input.id != "message-input":
            return

        text = event.value.strip()
        if not text:
            return

        event.input.value = ""

        # Обрабатываем slash-команды
        if text.startswith("/"):
            await self._handle_slash_command(text)
            return

        # Отправляем сообщение ассистенту
        await self._send_message(text)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Обрабатывает кнопку отправки."""
        if event.button.id == "btn-send":
            try:
                inp = self.query_one("#message-input", Input)
                text = (inp.value or "").strip()
                if not text:
                    return
                inp.value = ""
                if text.startswith("/"):
                    await self._handle_slash_command(text)
                else:
                    await self._send_message(text)
                inp.focus()
            except Exception:
                pass

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Переключение активного профиля через dropdown."""
        if event.select.id != "profile-selector":
            return
        value = event.value
        if value == Select.BLANK or value is None:
            return
        try:
            ok = self._config_manager.switch_profile(str(value))
            if ok:
                self._config = self._config_manager.config
                self.assistant.reload_config()
                self._update_header()
                chat_area = self.query_one("#chat-area", ScrollableContainer)
                await chat_area.mount(Static(
                    f"[green]Активный профиль: {value}[/green] "
                    f"[dim]({self._config.ai.provider} / {self._config.ai.model})[/dim]"
                ))
                chat_area.scroll_end(animate=False)
                # Возвращаем фокус в поле ввода
                try:
                    self.query_one("#message-input", Input).focus()
                except Exception:
                    pass
        except Exception:
            pass

    async def _send_message(self, text: str) -> None:
        """Отправляет сообщение ассистенту и отображает ответ."""
        if self.is_thinking:
            return

        # Убираем placeholder
        try:
            self.query_one("#chat-placeholder").remove()
        except Exception:
            pass

        # Добавляем сообщение пользователя
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        ts = datetime.now().strftime("%H:%M")
        user_widget = UserMessage(text, ts)
        await chat_area.mount(user_widget)

        # Создаём виджет ответа ассистента
        self.is_thinking = True
        assistant_widget = AssistantMessage(ts)
        self._current_assistant_widget = assistant_widget
        await chat_area.mount(assistant_widget)
        chat_area.scroll_end(animate=False)

        # Запускаем обработку в worker
        self.run_worker(self._process_message(text), exclusive=True)

    async def _process_message(self, text: str) -> None:
        """Worker: обрабатывает сообщение через ассистента."""
        try:
            async for event in self.assistant.chat(text):
                event_type = event.get("type")

                if event_type == "text":
                    chunk = event["content"]
                    # Если текущего пузыря нет (был сброшен после tool_done) — создаём новый
                    self.call_later(self._append_text_chunk, chunk)

                elif event_type == "tool_start":
                    tool_name = event.get("tool_name", "")
                    tool_input = event.get("tool_input", {})
                    # Перед показом tool-call виджета закрываем текущий пузырь ассистента
                    self.call_later(self._close_current_assistant_bubble)
                    if self._config.ui.show_tool_calls:
                        self.call_later(
                            self._add_tool_widget, tool_name, tool_input
                        )

                elif event_type == "tool_done":
                    tool_name = event.get("tool_name", "")
                    if self._current_tool_widget:
                        self.call_later(
                            self._current_tool_widget.set_done, 0.0
                        )
                    # Сбрасываем tool-виджет — следующий тул будет в новом
                    self.call_later(self._reset_current_tool_widget)
                    try:
                        sidebar = self.query_one("#sidebar", SidebarWidget)
                        self.call_later(sidebar.add_action, tool_name)
                    except Exception:
                        pass

                elif event_type == "error":
                    error = event.get("error", "Неизвестная ошибка")
                    self.call_later(self._show_error, error)

        except Exception as e:
            self.call_later(self._show_error, str(e))
        finally:
            self.call_later(self._finish_response)

    def _append_text_chunk(self, chunk: str) -> None:
        """Добавляет чанк текста в текущий пузырь ассистента, создавая его при необходимости."""
        try:
            if self._current_assistant_widget is None:
                # Создаём новый пузырь под tool-call'ом
                chat_area = self.query_one("#chat-area", ScrollableContainer)
                ts = datetime.now().strftime("%H:%M")
                widget = AssistantMessage(ts)
                self._current_assistant_widget = widget
                self.call_later(chat_area.mount, widget)
                # Добавляем чанк после монтирования
                self.call_later(widget.append_text, chunk)
                self.call_later(lambda: chat_area.scroll_end(animate=False))
            else:
                self._current_assistant_widget.append_text(chunk)
                try:
                    chat_area = self.query_one("#chat-area", ScrollableContainer)
                    chat_area.scroll_end(animate=False)
                except Exception:
                    pass
        except Exception:
            pass

    def _close_current_assistant_bubble(self) -> None:
        """Закрывает текущий пузырь ассистента (перед показом tool-call виджета)."""
        if self._current_assistant_widget is not None:
            try:
                # Если пузырь содержит только заголовок — удаляем, иначе финализируем
                widget = self._current_assistant_widget
                # _text у пузыря — заголовок ts. Если equals — пустой пузырь
                if hasattr(widget, "_text"):
                    header_only = widget._text.endswith("[/dim]\n") and len(widget._text) < 80
                    if header_only:
                        widget.remove()
                    else:
                        widget.finalize()
                else:
                    widget.finalize()
            except Exception:
                pass
            self._current_assistant_widget = None

    def _reset_current_tool_widget(self) -> None:
        """Сбрасывает ссылку на текущий tool-call виджет."""
        self._current_tool_widget = None

    def _add_tool_widget(self, tool_name: str, tool_input: dict) -> None:
        """Добавляет виджет вызова инструмента в чат."""
        try:
            chat_area = self.query_one("#chat-area", ScrollableContainer)
            widget = ToolCallWidget(tool_name, tool_input)
            self._current_tool_widget = widget
            self.call_later(chat_area.mount, widget)
            self.call_later(lambda: chat_area.scroll_end(animate=False))
        except Exception:
            pass

    def _show_error(self, error: str) -> None:
        """Показывает сообщение об ошибке в чате."""
        try:
            chat_area = self.query_one("#chat-area", ScrollableContainer)
            # Экранируем [ чтобы Textual markup не падал на текстах вида "[Errno 2]"
            safe_error = str(error).replace("[", r"\[")
            error_widget = Static(
                f"[bold red]❌ Ошибка:[/bold red] {safe_error}",
                classes="error-message"
            )
            self.call_later(chat_area.mount, error_widget)
        except Exception:
            pass

    def _finish_response(self) -> None:
        """Завершает отображение ответа."""
        self.is_thinking = False
        if self._current_assistant_widget:
            try:
                self._current_assistant_widget.finalize()
            except Exception:
                pass
        self._current_assistant_widget = None
        self._current_tool_widget = None
        try:
            chat_area = self.query_one("#chat-area", ScrollableContainer)
            chat_area.scroll_end(animate=False)
        except Exception:
            pass

    async def _on_confirm_request(self, action: str, target: str) -> bool:
        """Callback для запроса подтверждения от UI."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending_confirm = future

        def _resolve(yes: bool) -> None:
            if not future.done():
                loop.call_soon_threadsafe(future.set_result, yes)

        async def show_dialog():
            try:
                # Удаляем существующие диалоги
                for old in list(self.query(".confirm-dialog")):
                    try:
                        old.remove()
                    except Exception:
                        pass
                dialog = ConfirmDialog(action, target, _resolve)
                # Монтируем перед #input-area, ПОВЕРХ чата (не внутри scrollable)
                await self.mount(dialog, before=self.query_one("#input-area"))
                # Ставим фокус явно после монтирования
                await asyncio.sleep(0.05)
                try:
                    dialog.query_one("#confirm-input", Input).focus()
                except Exception:
                    pass
            except Exception as e:
                if not future.done():
                    future.set_result(False)

        self.call_later(show_dialog)
        return await future

    async def _on_sudo_request(self) -> str:
        """Callback для запроса пароля sudo от UI."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending_sudo = future

        def _resolve(pwd: str) -> None:
            if not future.done():
                loop.call_soon_threadsafe(future.set_result, pwd)

        async def show_sudo_dialog():
            try:
                # Удаляем существующие диалоги sudo
                for old in list(self.query("#sudo-dialog")):
                    try:
                        old.remove()
                    except Exception:
                        pass
                dialog = SudoPasswordDialog(_resolve)
                # Монтируем перед #input-area, ПОВЕРХ чата
                await self.mount(dialog, before=self.query_one("#input-area"))
                await asyncio.sleep(0.05)
                try:
                    dialog.query_one("#sudo-input", Input).focus()
                except Exception:
                    pass
            except Exception:
                if not future.done():
                    future.set_result("")

        self.call_later(show_sudo_dialog)
        return await future

    # ─── Slash-команды ────────────────────────────────────────────────────────

    async def _handle_slash_command(self, text: str) -> None:
        """Обрабатывает slash-команды."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        chat_area = self.query_one("#chat-area", ScrollableContainer)

        try:
            self.query_one("#chat-placeholder").remove()
        except Exception:
            pass

        if cmd == "/help":
            await chat_area.mount(Static(HELP_TEXT, classes="assistant-bubble"))

        elif cmd == "/clear":
            self.assistant.clear_history()
            await self._clear_chat_widgets()
            await chat_area.mount(Static("[dim]История очищена[/dim]"))

        elif cmd == "/provider":
            if arg:
                self._config.ai.provider = arg
                get_config_manager().save()
                self.assistant.reload_config()
                await chat_area.mount(Static(f"[green]Провайдер изменён на: {arg}[/green]"))
            else:
                await chat_area.mount(Static(f"[cyan]Текущий провайдер: {self._config.ai.provider}[/cyan]"))

        elif cmd == "/model":
            if arg:
                self._config.ai.model = arg
                get_config_manager().save()
                self.assistant.reload_config()
                self._update_header()
                await chat_area.mount(Static(f"[green]Модель изменена на: {arg}[/green]"))
            else:
                await chat_area.mount(Static(f"[cyan]Текущая модель: {self._config.ai.model}[/cyan]"))

        elif cmd == "/theme":
            if arg:
                self._config.ui.theme = arg
                get_config_manager().save()
                theme_css = get_theme(arg)
                self.css = theme_css
                await chat_area.mount(Static(f"[green]Тема изменена на: {arg}[/green]"))
            else:
                from .themes import get_theme_names
                themes = ", ".join(get_theme_names())
                await chat_area.mount(Static(f"[cyan]Доступные темы: {themes}[/cyan]"))

        elif cmd == "/apikey":
            # Показываем диалог ввода пароля в worker, чтобы не блокировать UI
            async def handle_apikey():
                future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
                
                async def on_dialog_close(pwd):
                    future.set_result(pwd)
                    # Возвращаем фокус на основное поле ввода после закрытия диалога
                    try:
                        self.query_one("#message-input", Input).focus()
                    except Exception:
                        pass
                
                dialog = SudoPasswordDialog(on_dialog_close)
                await chat_area.mount(dialog)
                # Даём время диалогу смонтироваться перед фокусировкой
                await asyncio.sleep(0.1)
                try:
                    dialog.focus()
                except Exception:
                    pass
                
                key = await future
                if key:
                    get_config_manager().set_api_key(key)
                    get_config_manager().save()
                    self.assistant.reload_config()
                    await chat_area.mount(Static("[green]API ключ обновлён[/green]"))
                    chat_area.scroll_end(animate=False)
            
            self.run_worker(handle_apikey())

        elif cmd == "/baseurl":
            if arg:
                self._config.ai.base_url = arg
                get_config_manager().save()
                self.assistant.reload_config()
                await chat_area.mount(Static(f"[green]Base URL изменён на: {arg}[/green]"))

        elif cmd == "/cd":
            if arg:
                try:
                    self.assistant.cwd = arg
                    self.sub_title = self.assistant.cwd
                    safe_cwd = str(self.assistant.cwd).replace("[", r"\[")
                    await chat_area.mount(Static(f"[green]Рабочая директория: {safe_cwd}[/green]"))
                except ValueError as e:
                    safe_e = str(e).replace("[", r"\[")
                    await chat_area.mount(Static(f"[red]{safe_e}[/red]", classes="error-message"))

        elif cmd == "/ls":
            from ..tools.file_reader import FileReader
            fr = FileReader()
            items = fr.list_directory(self.assistant.cwd, show_hidden=False, recursive=False)
            lines = "\n".join(
                f"  {'📁' if i.get('is_dir') else '📄'} {str(i['name']).replace('[', chr(92) + '[')}"
                for i in (items if isinstance(items, list) else [])
            )
            safe_cwd = str(self.assistant.cwd).replace("[", r"\[")
            await chat_area.mount(Static(f"[cyan]{safe_cwd}[/cyan]\n{lines or '(пусто)'}"))

        elif cmd == "/history":
            history = self.assistant.get_history()
            count = len([m for m in history if m["role"] == "user"])
            await chat_area.mount(Static(f"[cyan]Сообщений в истории: {count}[/cyan]"))

        elif cmd == "/export":
            path = arg or os.path.expanduser("~/cli-assistant-history.json")
            fmt = "md" if path.endswith(".md") else "json"
            ok = self.assistant.export_history(path, fmt)
            if ok:
                await chat_area.mount(Static(f"[green]История экспортирована: {path}[/green]"))
            else:
                await chat_area.mount(Static(f"[red]Ошибка экспорта[/red]", classes="error-message"))

        elif cmd == "/sudo":
            if arg == "clear":
                self.assistant.sudo_manager.clear_sudo_cache()
                await chat_area.mount(Static("[green]Кэш sudo очищен[/green]"))
            else:
                ok = await self.assistant.sudo_manager.request_sudo_password()
                if ok:
                    remaining = self.assistant.sudo_manager.get_cache_remaining_seconds()
                    await chat_area.mount(Static(f"[green]Sudo активирован на {remaining}с[/green]"))
                else:
                    await chat_area.mount(Static("[red]Не удалось получить пароль sudo[/red]"))

        elif cmd == "/profile":
            await self._handle_profile_command(arg)

        elif cmd == "/settings":
            await self.action_open_settings()

        else:
            await chat_area.mount(Static(
                f"[yellow]Неизвестная команда: {cmd}. Введите /help для справки.[/yellow]"
            ))

        chat_area.scroll_end(animate=False)

    async def _clear_chat_widgets(self) -> None:
        """Удаляет все виджеты из области чата."""
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        for child in list(chat_area.children):
            child.remove()

    async def _handle_profile_command(self, arg: str) -> None:
        """Обрабатывает /profile [list | add <name> | delete <name> | <name>]."""
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        cm = self._config_manager
        parts = arg.split(maxsplit=2)

        # /profile  → список
        if not parts or parts[0] in ("list", "ls"):
            profiles = cm.get_profiles()
            active = cm.get_active_profile()
            if not profiles:
                await chat_area.mount(Static(
                    "[yellow]Нет сохранённых профилей.[/yellow]\n"
                    "[dim]Создайте: /profile add <имя>[/dim]"
                ))
                return
            lines = ["[bold cyan]Профили:[/bold cyan]"]
            for name, p in profiles.items():
                marker = "[green]●[/green]" if name == active else "[dim]○[/dim]"
                provider = p.get("provider", "")
                model = p.get("model", "")
                safe_name = str(name).replace("[", r"\[")
                lines.append(f"  {marker} [bold]{safe_name}[/bold] [dim]({provider} / {model})[/dim]")
            await chat_area.mount(Static("\n".join(lines)))
            return

        sub = parts[0].lower()

        # /profile add <name>
        if sub == "add":
            if len(parts) < 2:
                await chat_area.mount(Static(
                    "[yellow]Использование:[/yellow] /profile add <имя>"
                ))
                return
            name = parts[1].strip()
            # Используем текущие настройки ai.* как шаблон для нового профиля,
            # api_key берём в распакованном виде через get_api_key().
            real_key = cm.get_api_key()
            ok = cm.add_profile(
                name=name,
                provider=self._config.ai.provider,
                model=self._config.ai.model,
                api_key=real_key,
                base_url=self._config.ai.base_url,
            )
            if ok:
                self._refresh_profile_selector()
                safe_name = name.replace("[", r"\[")
                await chat_area.mount(Static(
                    f"[green]✓ Профиль создан:[/green] {safe_name}\n"
                    f"[dim]Скопированы текущие настройки. Меняйте через /provider, /model, /apikey, /baseurl.[/dim]"
                ))
            else:
                await chat_area.mount(Static(
                    f"[red]Не удалось создать профиль (возможно, уже существует или пустое имя).[/red]"
                ))
            return

        # /profile delete <name>  /  /profile rm <name>
        if sub in ("delete", "del", "rm", "remove"):
            if len(parts) < 2:
                await chat_area.mount(Static(
                    "[yellow]Использование:[/yellow] /profile delete <имя>"
                ))
                return
            name = parts[1].strip()
            ok = cm.delete_profile(name)
            if ok:
                self._refresh_profile_selector()
                safe_name = name.replace("[", r"\[")
                await chat_area.mount(Static(f"[green]✓ Профиль удалён:[/green] {safe_name}"))
            else:
                await chat_area.mount(Static(f"[red]Профиль не найден: {name}[/red]"))
            return

        # /profile switch <name>  или просто  /profile <name>
        target_name = parts[1].strip() if sub == "switch" and len(parts) >= 2 else parts[0].strip()
        ok = cm.switch_profile(target_name)
        if ok:
            self._config = cm.config
            self.assistant.reload_config()
            self._update_header()
            self._refresh_profile_selector()
            safe = target_name.replace("[", r"\[")
            await chat_area.mount(Static(
                f"[green]✓ Активный профиль:[/green] {safe} "
                f"[dim]({self._config.ai.provider} / {self._config.ai.model})[/dim]"
            ))
        else:
            safe = target_name.replace("[", r"\[")
            await chat_area.mount(Static(
                f"[red]Профиль не найден:[/red] {safe}\n"
                f"[dim]Список: /profile list[/dim]"
            ))

    # ─── Actions ──────────────────────────────────────────────────────────────

    async def action_open_settings(self) -> None:
        """Открывает экран настроек."""
        from .settings_screen import SettingsScreen
        await self.push_screen(SettingsScreen())

    async def action_clear_chat(self) -> None:
        """Очищает чат."""
        self.assistant.clear_history()
        await self._clear_chat_widgets()
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        await chat_area.mount(Static("[dim]История очищена[/dim]"))

    async def action_show_help(self) -> None:
        """Показывает справку."""
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        await chat_area.mount(Static(HELP_TEXT, classes="assistant-bubble"))
        chat_area.scroll_end(animate=False)

    def action_cancel_input(self) -> None:
        """Сбрасывает поле ввода."""
        try:
            self.query_one("#message-input", Input).value = ""
        except Exception:
            pass

    CSS = """
    #main-layout {
        height: 1fr;
    }

    #chat-area {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }

    #sidebar {
        width: 22;
        height: 1fr;
        padding: 1;
        border-left: solid #2a2a4a;
    }

    #input-area {
        height: 3;
        padding: 0 1;
    }

    #input-row {
        height: 3;
        width: 1fr;
    }

    #profile-selector {
        width: 22;
        height: 3;
        min-width: 22;
        max-width: 22;
    }

    #profile-selector SelectCurrent {
        height: 1;
        max-height: 1;
        overflow-x: hidden;
        overflow-y: hidden;
        text-overflow: ellipsis;
    }

    #profile-selector Static {
        height: 1;
        max-height: 1;
        overflow-x: hidden;
        text-overflow: ellipsis;
    }

    #message-input {
        width: 1fr;
        height: 3;
    }

    #btn-send {
        width: 5;
        height: 3;
        min-width: 5;
        margin-left: 1;
    }

    .user-bubble {
        background: #0f3460;
        color: #e0e0e0;
        border: round #3a5a8a;
        margin: 1 2;
        padding: 1 2;
        width: auto;
        max-width: 70%;
        align-horizontal: right;
    }

    .assistant-bubble {
        background: #1e3a2f;
        color: #e0e0e0;
        border: round #2a5a3a;
        margin: 1 2;
        padding: 1 2;
        width: auto;
        max-width: 85%;
    }

    .tool-call {
        background: #1a2744;
        color: #88aaff;
        border: solid #3a4a7a;
        margin: 0 4;
        padding: 0 1;
        width: auto;
    }

    .error-message {
        color: #f44336;
        background: #3a1a1a;
        border: solid #f44336;
        margin: 1 2;
        padding: 1;
    }

    .confirm-dialog {
        background: #2a1a00;
        border: round #ff9800;
        margin: 1 2;
        padding: 1 2;
        height: auto;
    }
    .confirm-dialog #confirm-text {
        margin-bottom: 1;
    }
    .confirm-dialog #confirm-input {
        margin-bottom: 1;
    }
    .confirm-dialog #confirm-buttons {
        height: 3;
    }
    .confirm-dialog #confirm-buttons Button {
        margin-right: 1;
    }
    """


HELP_TEXT = """[bold cyan]📖 Справка CLI Assistant[/bold cyan]

[bold]Slash-команды:[/bold]
  [cyan]/help[/cyan]              — эта справка
  [cyan]/settings[/cyan]          — открыть настройки
  [cyan]/provider \\[name][/cyan]   — сменить провайдера (anthropic/gemini/openai_compatible)
  [cyan]/model \\[name][/cyan]      — сменить модель
  [cyan]/theme \\[name][/cyan]      — сменить тему (dark/light/cyberpunk/nord/solarized)
  [cyan]/apikey[/cyan]            — изменить API ключ
  [cyan]/baseurl \\[url][/cyan]     — изменить base URL
  [cyan]/clear[/cyan]             — очистить историю чата
  [cyan]/history[/cyan]           — показать статистику истории
  [cyan]/export \\[path][/cyan]     — экспортировать историю (json/md)
  [cyan]/cd \\[path][/cyan]         — сменить рабочую директорию
  [cyan]/ls[/cyan]                — содержимое текущей директории
  [cyan]/sudo[/cyan]              — запросить sudo пароль
  [cyan]/sudo clear[/cyan]        — очистить кэш sudo

[bold]Профили (мульти-аккаунт):[/bold]
  [cyan]/profile[/cyan]                — список профилей
  [cyan]/profile add \\[имя][/cyan]     — создать профиль из текущих настроек
  [cyan]/profile delete \\[имя][/cyan]  — удалить профиль
  [cyan]/profile \\[имя][/cyan]         — переключиться на профиль
  [dim]Также можно переключаться через выпадающий список слева от поля ввода.[/dim]

[bold]Горячие клавиши:[/bold]
  [cyan]Ctrl+C[/cyan]  — выход
  [cyan]Ctrl+S[/cyan]  — настройки
  [cyan]Ctrl+L[/cyan]  — очистить чат
  [cyan]Ctrl+H[/cyan]  — справка
  [cyan]Enter[/cyan]   — отправить сообщение"""
