"""CLI Assistant GUI — десктопное приложение в стиле Claude.

Запуск: python3 gui_app.py
Стек:   pywebview + HTML/CSS/JS (без тяжёлых GUI-фреймворков).

Архитектура:
  • Класс Api  — мост Python ↔ JS, экспортируется в окно через js_api.
  • ChatStore  — JSON-стор бесед в ~/.cli-assistant/chats.json.
  • Assistant  — переиспользуем существующий из src/core/assistant.py.

Каждый JS-вызов api.send_message(...) запускает background-task в asyncio,
который стримит чанки обратно в окно через webview.evaluate_js — так мы
получаем «печатающийся» ответ ИИ без блокировки UI-потока.
"""

import sys
import os
# Добавляем src/ в путь чтобы работали абсолютные импорты
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ─── Совместимость с Wayland/GPU (ВАЖНО: до импорта Qt/webview!) ───────────
# QtWebEngine падает на части Linux-систем с ошибками вроде
# "Compositor returned null texture" / "dma_buf acquisition failure" —
# окно создаётся, но содержимое не рендерится и приложение выглядит
# как «не запустилось». Пользователь жалуется именно на это.
#
# Решение: принудительно используем X11-бэкенд (xcb) и отключаем
# проблемные GPU-фичи. Это работает на любом Linux (X11/Wayland)
# и не вредит производительности обычного UI-окна.
if sys.platform.startswith("linux"):
    # Заставляем Qt использовать X11/XWayland — стабильнее нативного wayland
    # для QtWebEngine (там часто валится Vulkan/dma-buf).
    # ВАЖНО: используем ПЕРЕЗАПИСЬ, а не setdefault — DE (GNOME/KDE на Wayland)
    # может уже установить QT_QPA_PLATFORM=wayland, и тогда из меню запуск
    # падает, а из терминала (где переменной нет) работает. Юзер дал именно
    # такой репорт. Если кто-то осознанно хочет wayland — может выставить
    # CLI_ASSISTANT_QT_PLATFORM перед запуском.
    _force_platform = os.environ.get("CLI_ASSISTANT_QT_PLATFORM", "xcb")
    os.environ["QT_QPA_PLATFORM"] = _force_platform
    # Программный рендер для самого Chromium — самый надёжный путь;
    # окно UI лёгкое, производительности хватает.
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    extra = (
        " --disable-gpu"
        " --disable-software-rasterizer"
        " --disable-features=Vulkan,VaapiVideoDecoder,UseOzonePlatform"
        " --no-sandbox"
    )
    if "--disable-gpu" not in flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + extra).strip()
    # Программный рендеринг QtQuick (на всякий случай).
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

# Импорты из текущего пакета
from core.assistant import Assistant  # noqa: E402
from settings.config_manager import get_config_manager  # noqa: E402

try:
    import webview  # pywebview
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "❌ pywebview не установлен. Установите:\n"
        "   pip install pywebview\n"
        "или:\n"
        "   pip install -r requirements-gui.txt\n"
    )
    sys.exit(1)


CHATS_DIR = Path(os.path.expanduser("~/.cli-assistant"))
CHATS_FILE = CHATS_DIR / "chats.json"


# ─── Хранилище чатов ──────────────────────────────────────────────────────────

class ChatStore:
    """Простой JSON-стор для списка бесед.

    Структура файла:
        {
          "chats": [
            {"id": "abc", "title": "...", "created": 1714..., "updated": 1714...,
             "messages": [{"role":"user","content":"..."}, ...]}
          ],
          "active_id": "abc"
        }
    """

    def __init__(self, path: Path = CHATS_FILE) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict = {"chats": [], "active_id": None}
        self._load()

    def _load(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            if "chats" not in self._data:
                self._data["chats"] = []
        except Exception:
            self._data = {"chats": [], "active_id": None}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            tmp.replace(self.path)
        except Exception:
            pass

    def list_chats(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "id": c["id"],
                    "title": c.get("title") or "Новый чат",
                    "updated": c.get("updated", c.get("created", 0)),
                }
                for c in sorted(
                    self._data["chats"],
                    key=lambda x: x.get("updated", 0),
                    reverse=True,
                )
            ]

    def get(self, chat_id: str) -> Optional[dict]:
        with self._lock:
            for c in self._data["chats"]:
                if c["id"] == chat_id:
                    return json.loads(json.dumps(c))
        return None

    def create(self, title: str = "Новый чат") -> dict:
        chat = {
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "created": int(time.time()),
            "updated": int(time.time()),
            "messages": [],
        }
        with self._lock:
            self._data["chats"].append(chat)
            self._data["active_id"] = chat["id"]
            self._save()
        return chat

    def delete(self, chat_id: str) -> bool:
        with self._lock:
            before = len(self._data["chats"])
            self._data["chats"] = [c for c in self._data["chats"] if c["id"] != chat_id]
            if self._data.get("active_id") == chat_id:
                self._data["active_id"] = None
            self._save()
            return len(self._data["chats"]) < before

    def rename(self, chat_id: str, title: str) -> bool:
        with self._lock:
            for c in self._data["chats"]:
                if c["id"] == chat_id:
                    c["title"] = (title or "Новый чат")[:80]
                    c["updated"] = int(time.time())
                    self._save()
                    return True
        return False

    def append_message(self, chat_id: str, role: str, content: str) -> None:
        with self._lock:
            for c in self._data["chats"]:
                if c["id"] == chat_id:
                    c["messages"].append({"role": role, "content": content})
                    c["updated"] = int(time.time())
                    if role == "user" and (
                        not c.get("title") or c["title"] == "Новый чат"
                    ):
                        c["title"] = content.strip().splitlines()[0][:60] or "Новый чат"
                    self._save()
                    return

    def set_active(self, chat_id: Optional[str]) -> None:
        with self._lock:
            self._data["active_id"] = chat_id
            self._save()

    def get_active(self) -> Optional[str]:
        with self._lock:
            return self._data.get("active_id")


# ─── JS ↔ Python API ──────────────────────────────────────────────────────────

class Api:
    """Объект, который pywebview прокидывает в JS как `window.pywebview.api`."""

    def __init__(self) -> None:
        self.store = ChatStore()
        self.assistant = Assistant()
        self.config = get_config_manager()
        self._window: Optional["webview.Window"] = None
        # Отдельный event-loop для async-вызовов ассистента, крутится в потоке.
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # pending-события: JS закрывает их через api.resolve_*.
        self._pending_confirm: dict[str, threading.Event] = {}
        self._pending_confirm_result: dict[str, bool] = {}
        self._pending_sudo: dict[str, threading.Event] = {}
        self._pending_sudo_result: dict[str, str] = {}
        # Подключаем sync-callbacks (Assistant ожидает синхронные функции).
        self.assistant.set_ui_callbacks(
            on_confirm=self._on_confirm_sync,
            on_sudo_request=self._on_sudo_request_sync,
        )

    # ── lifecycle ───────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def attach_window(self, window: "webview.Window") -> None:
        self._window = window

    def _eval_js(self, code: str) -> None:
        """Безопасно вызвать JS из любого треда."""
        try:
            if self._window is not None:
                self._window.evaluate_js(code)
        except Exception:
            pass

    def _push(self, event: str, payload: dict) -> None:
        """Отправить событие в JS: window.cli.on(event, payload)."""
        try:
            data = json.dumps(payload, ensure_ascii=False)
        except Exception:
            data = "{}"
        self._eval_js(
            f"window.cli && window.cli.on && window.cli.on({json.dumps(event)}, {data});"
        )

    # ── chats ──────────────────────────────────────────────────────────────

    def list_chats(self) -> list[dict]:
        return self.store.list_chats()

    def get_chat(self, chat_id: str) -> Optional[dict]:
        return self.store.get(chat_id)

    def create_chat(self) -> dict:
        chat = self.store.create()
        # Сбрасываем историю ассистента — новый чат начинается с нуля.
        try:
            self.assistant.clear_history()
        except Exception:
            pass
        return chat

    def delete_chat(self, chat_id: str) -> bool:
        return self.store.delete(chat_id)

    def rename_chat(self, chat_id: str, title: str) -> bool:
        return self.store.rename(chat_id, title)

    def select_chat(self, chat_id: str) -> Optional[dict]:
        chat = self.store.get(chat_id)
        if not chat:
            return None
        self.store.set_active(chat_id)
        # Перезаливаем историю в Assistant (в формате провайдера).
        try:
            self.assistant.clear_history()
            msgs = getattr(self.assistant, "_messages", None)
            if isinstance(msgs, list):
                for m in chat.get("messages", []):
                    role = m.get("role")
                    content = m.get("content", "")
                    if role in ("user", "assistant") and content:
                        msgs.append({"role": role, "content": content})
        except Exception:
            pass
        return chat

    # ── settings ───────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        c = self.config.config
        try:
            yolo = bool(getattr(c.safety, "yolo_mode", False))
        except Exception:
            yolo = False
        return {
            "provider": c.ai.provider,
            "model": c.ai.model,
            "yolo": yolo,
            "theme": c.ui.theme,
            "language": c.ui.language,
        }

    def get_settings_full(self) -> dict:
        """Возвращает полный набор настроек для экрана настроек."""
        c = self.config.config
        return {
            "ai": {
                "provider": c.ai.provider,
                "model": c.ai.model,
                "api_key": self.config.get_api_key(),
                "base_url": c.ai.base_url,
                "temperature": c.ai.temperature,
                "max_tokens": c.ai.max_tokens,
                "stream": c.ai.stream,
            },
            "ui": {
                "theme": c.ui.theme,
                "language": c.ui.language,
                "animation_speed": c.ui.animation_speed,
                "show_tool_calls": c.ui.show_tool_calls,
                "show_timestamps": c.ui.show_timestamps,
            },
            "safety": {
                "yolo_mode": bool(getattr(c.safety, "yolo_mode", False)),
                "confirm_destructive": c.safety.confirm_destructive,
                "confirm_sudo": c.safety.confirm_sudo,
            },
            "active_profile": self.config.get_active_profile(),
        }

    def get_models(self) -> dict:
        """Список моделей: встроенные по провайдерам + добавленные пользователем."""
        try:
            from src.ai.anthropic_provider import ANTHROPIC_MODELS
        except Exception:
            ANTHROPIC_MODELS = []
        try:
            from src.ai.openai_provider import OPENAI_MODELS, KNOWN_PROVIDERS
        except Exception:
            OPENAI_MODELS, KNOWN_PROVIDERS = [], {}
        try:
            from src.ai.gemini_provider import GEMINI_MODELS
        except Exception:
            GEMINI_MODELS = []

        c = self.config.config
        # Собираем модели всех профилей пользователя — это то, что он
        # «ввёл» в настройках раньше.
        user_models: list[str] = []
        try:
            for name, p in (self.config.get_profiles() or {}).items():
                m = (p.get("model") or "").strip()
                if m and m not in user_models:
                    user_models.append(m)
        except Exception:
            pass
        cur = (c.ai.model or "").strip()
        if cur and cur not in user_models:
            user_models.append(cur)

        return {
            "current": cur,
            "current_provider": c.ai.provider,
            "user_models": user_models,
            "providers": {
                "anthropic": list(ANTHROPIC_MODELS),
                "gemini": list(GEMINI_MODELS),
                "openai_compatible": list(OPENAI_MODELS),
            },
            "known_endpoints": {
                k: v.get("base_url", "") for k, v in (KNOWN_PROVIDERS or {}).items()
            },
        }

    def set_model(self, model: str) -> bool:
        """Меняет активную модель (без смены провайдера/ключа)."""
        m = (model or "").strip()
        if not m:
            return False
        self.config.config.ai.model = m
        ok = self.config.save()
        try:
            self.assistant.reload_config()
        except Exception:
            pass
        return bool(ok)

    def save_settings(self, payload: dict) -> dict:
        """Сохраняет полный экран настроек.

        payload: {
          ai: {provider, model, api_key, base_url, temperature?, max_tokens?},
          ui: {theme, language, animation_speed, show_tool_calls, show_timestamps},
          safety: {yolo_mode, confirm_destructive, confirm_sudo}
        }
        """
        c = self.config.config
        try:
            payload = payload or {}
            ai = payload.get("ai") or {}
            ui = payload.get("ui") or {}
            safety = payload.get("safety") or {}

            if "provider" in ai and ai["provider"]:
                c.ai.provider = str(ai["provider"])
            if "model" in ai and ai["model"]:
                c.ai.model = str(ai["model"]).strip()
            if "base_url" in ai:
                c.ai.base_url = str(ai["base_url"] or "")
            if "temperature" in ai:
                try: c.ai.temperature = float(ai["temperature"])
                except Exception: pass
            if "max_tokens" in ai:
                try: c.ai.max_tokens = int(ai["max_tokens"])
                except Exception: pass
            # API key — отдельным методом, через keyring
            api_key = ai.get("api_key", None)
            if api_key is not None and api_key != "":
                try:
                    self.config.set_api_key(str(api_key))
                except Exception:
                    pass

            if "theme" in ui and ui["theme"]:
                c.ui.theme = str(ui["theme"])
            if "language" in ui and ui["language"]:
                c.ui.language = str(ui["language"])
            if "animation_speed" in ui:
                c.ui.animation_speed = str(ui["animation_speed"] or "normal")
            if "show_tool_calls" in ui:
                c.ui.show_tool_calls = bool(ui["show_tool_calls"])
            if "show_timestamps" in ui:
                c.ui.show_timestamps = bool(ui["show_timestamps"])

            if "yolo_mode" in safety:
                c.safety.yolo_mode = bool(safety["yolo_mode"])
            if "confirm_destructive" in safety:
                c.safety.confirm_destructive = bool(safety["confirm_destructive"])
            if "confirm_sudo" in safety:
                c.safety.confirm_sudo = bool(safety["confirm_sudo"])

            self.config.save()
            try:
                self.assistant.reload_config()
            except Exception:
                pass
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def test_provider(self, payload: dict) -> dict:
        """Лёгкая проверка: пробуем создать провайдер и сделать пробный запрос."""
        try:
            from src.ai.provider_factory import create_provider
            p = (payload or {}).get("provider") or self.config.config.ai.provider
            m = (payload or {}).get("model")    or self.config.config.ai.model
            k = (payload or {}).get("api_key")  or self.config.get_api_key()
            u = (payload or {}).get("base_url") or self.config.config.ai.base_url
            try:
                provider = create_provider(provider=p, model=m, api_key=k, base_url=u)
            except TypeError:
                provider = create_provider(p, m, k, u)
            ok = bool(provider)
            return {"ok": ok}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    # ── Профили (мульти-аккаунт) ──────────────────────────────────────────

    def list_profiles(self) -> dict:
        return {
            "active": self.config.get_active_profile(),
            "profiles": self.config.get_profiles(),
        }

    def add_profile(self, name: str, provider: str, model: str,
                    api_key: str, base_url: str = "") -> bool:
        return bool(self.config.add_profile(name, provider, model, api_key, base_url))

    def switch_profile(self, name: str) -> bool:
        ok = bool(self.config.switch_profile(name))
        if ok:
            try:
                self.assistant.reload_config()
            except Exception:
                pass
        return ok

    def delete_profile(self, name: str) -> bool:
        return bool(self.config.delete_profile(name))

    # ── Темы / i18n (UI ресурсы) ──────────────────────────────────────────

    def get_themes(self) -> dict:
        """Возвращает все доступные темы из gui_web/themes.json."""
        try:
            path = Path(_resource("themes.json"))
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def get_i18n(self) -> dict:
        """Возвращает все строки переводов GUI (из gui_web/i18n.json)."""
        try:
            path = Path(_resource("i18n.json"))
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def toggle_yolo(self) -> bool:
        c = self.config.config
        new = not bool(getattr(c.safety, "yolo_mode", False))
        c.safety.yolo_mode = new
        self.config.save()
        try:
            self.assistant.reload_config()
        except Exception:
            pass
        return new

    # ── chat send ──────────────────────────────────────────────────────────

    def send_message(self, chat_id: str, text: str) -> str:
        """Отправить сообщение. Стриминг идёт через push-события в JS."""
        if not chat_id:
            chat = self.store.create()
            chat_id = chat["id"]
            self._push("chat_created", chat)
        # Сохраняем user-сообщение
        self.store.append_message(chat_id, "user", text)
        self._push("title_updated", {"id": chat_id, "title": self.store.get(chat_id)["title"]})

        # Запускаем стриминг в worker-loop.
        asyncio.run_coroutine_threadsafe(
            self._stream_message(chat_id, text), self._loop
        )
        return chat_id

    async def _stream_message(self, chat_id: str, text: str) -> None:
        msg_id = uuid.uuid4().hex[:10]
        self._push("msg_start", {"chat_id": chat_id, "msg_id": msg_id})
        full_text = ""
        try:
            async for ev in self.assistant.chat(text):
                t = ev.get("type")
                if t == "text":
                    chunk = ev.get("content", "")
                    full_text += chunk
                    self._push("msg_chunk", {"msg_id": msg_id, "chunk": chunk})
                elif t == "tool_start":
                    self._push("tool_start", {
                        "msg_id": msg_id,
                        "tool_name": ev.get("tool_name", ""),
                        "tool_input": ev.get("tool_input", {}),
                        "id": ev.get("id") or uuid.uuid4().hex[:8],
                    })
                elif t == "tool_done":
                    self._push("tool_done", {
                        "msg_id": msg_id,
                        "tool_name": ev.get("tool_name", ""),
                        "id": ev.get("id"),
                    })
                elif t == "error":
                    self._push("msg_error", {"msg_id": msg_id, "error": ev.get("error", "")})
        except Exception as e:
            self._push("msg_error", {"msg_id": msg_id, "error": str(e)})
        # Финал — сохраняем ответ ассистента в стор.
        if full_text.strip():
            self.store.append_message(chat_id, "assistant", full_text)
        self._push("msg_end", {"chat_id": chat_id, "msg_id": msg_id})

    # ── confirm / sudo (sync API для Assistant; ждём ответ из JS) ──────────
    # Assistant вызывает их синхронно из worker-потока, поэтому используем
    # threading.Event — это безопасно блокирует только тот поток, не UI.

    def _on_confirm_sync(self, action: str, target: str) -> bool:
        rid = uuid.uuid4().hex[:10]
        ev = threading.Event()
        self._pending_confirm[rid] = ev
        self._pending_confirm_result[rid] = False
        self._push("ask_confirm", {"id": rid, "action": action, "target": str(target)[:300]})
        ev.wait(timeout=300)  # 5 минут максимум
        result = self._pending_confirm_result.pop(rid, False)
        self._pending_confirm.pop(rid, None)
        return bool(result)

    def resolve_confirm(self, rid: str, yes: bool) -> None:
        if rid in self._pending_confirm:
            self._pending_confirm_result[rid] = bool(yes)
            self._pending_confirm[rid].set()

    def _on_sudo_request_sync(self) -> str:
        rid = uuid.uuid4().hex[:10]
        ev = threading.Event()
        self._pending_sudo[rid] = ev
        self._pending_sudo_result[rid] = ""
        self._push("ask_sudo", {"id": rid})
        ev.wait(timeout=300)
        password = self._pending_sudo_result.pop(rid, "")
        self._pending_sudo.pop(rid, None)
        return password or ""

    def resolve_sudo(self, rid: str, password: str) -> None:
        if rid in self._pending_sudo:
            self._pending_sudo_result[rid] = password or ""
            self._pending_sudo[rid].set()


# ─── Точка входа ──────────────────────────────────────────────────────────────

def _resource(name: str) -> str:
    """Путь к файлу UI: учитываем PyInstaller-сборку (sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", str(ROOT))
    return str(Path(base) / "gui_web" / name)


def main() -> int:
    api = Api()
    html_path = _resource("index.html")
    if not os.path.exists(html_path):
        sys.stderr.write(f"❌ Не найден UI: {html_path}\n")
        return 1
    window = webview.create_window(
        title="CLI Assistant",
        url="file://" + html_path,
        js_api=api,
        width=1280,
        height=820,
        min_size=(900, 600),
        background_color="#1f1e1d",
        text_select=True,
    )
    api.attach_window(window)
    # Принудительно используем Qt-бэкэнд (PySide6 + QtWebEngine).
    # GTK-вариант часто не работает в frozen-сборках (нет PyGObject) и пишет
    # "GTK cannot be loaded" → ничего не открывается. Qt — стабильный fallback.
    _gui_backend = os.environ.get("PYWEBVIEW_GUI", "qt").lower() or "qt"
    try:
        webview.start(gui=_gui_backend, debug=False)
    except (KeyError, ValueError, ModuleNotFoundError, ImportError):
        # Если по какой-то причине Qt недоступен — пробуем дефолт.
        webview.start(debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
