"""Менеджер конфигурации CLI Assistant."""

import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".cli-assistant"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_CONFIG_FILE = Path(__file__).parent.parent.parent / "config" / "default_config.json"


class AIConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-opus-4-5"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = True
    system_prompt: str = ""


class UIConfig(BaseModel):
    theme: str = "dark"
    language: str = "ru"
    show_timestamps: bool = True
    bubble_style: str = "rounded"
    show_tool_calls: bool = True
    animation_speed: str = "normal"


class SafetyConfig(BaseModel):
    confirm_destructive: bool = True
    confirm_sudo: bool = True
    # YOLO-режим: ассистент НЕ спрашивает подтверждения для деструктивных
    # операций и sudo-команд. Хард-блок катастрофических команд
    # (rm -rf /, dd of=/dev/sdX, fork bomb и т.п.) при этом сохраняется
    # — это нельзя выключить через конфиг.
    yolo_mode: bool = False
    blocked_paths: list[str] = Field(default_factory=lambda: [
        "/etc/passwd", "/etc/shadow", "/etc/sudoers"
    ])
    max_file_size_mb: int = 50
    allowed_sudo_commands: list[str] = Field(default_factory=list)


class SessionConfig(BaseModel):
    save_history: bool = True
    history_file: str = "~/.cli-assistant/history.json"
    max_history: int = 1000
    sudo_cache_minutes: int = 15


class ProfileConfig(BaseModel):
    """Конфигурация одного профиля (поднабор AIConfig)."""
    provider: str = "anthropic"
    model: str = ""
    api_key: str = ""           # как и в AIConfig: "__keyring__" или base64
    base_url: str = ""


class AppConfig(BaseModel):
    ai: AIConfig = Field(default_factory=AIConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    # Мульти-профили
    profiles: Dict[str, ProfileConfig] = Field(default_factory=dict)
    active_profile: str = ""

    class Config:
        # Игнорируем неизвестные поля при чтении старых конфигов
        extra = "ignore"


class ConfigManager:
    """Управляет конфигурацией приложения."""

    def __init__(self) -> None:
        self._config: AppConfig = AppConfig()
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Создаёт директорию конфига если не существует."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        logs_dir = CONFIG_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)

    def config_exists(self) -> bool:
        """Проверяет существование файла конфига."""
        return CONFIG_FILE.exists()

    def load(self) -> AppConfig:
        """Загружает конфигурацию из файла."""
        if not CONFIG_FILE.exists():
            self._config = self._load_defaults()
            return self._config

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._config = AppConfig(**data)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфига: {e}")
            self._config = self._load_defaults()

        return self._config

    def _load_defaults(self) -> AppConfig:
        """Загружает дефолтную конфигурацию."""
        try:
            if DEFAULT_CONFIG_FILE.exists():
                with open(DEFAULT_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AppConfig(**data)
        except Exception as e:
            logger.error(f"Ошибка загрузки дефолтного конфига: {e}")
        return AppConfig()

    def save(self) -> bool:
        """Сохраняет конфигурацию в файл."""
        try:
            self._ensure_config_dir()
            data = self._config.model_dump()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения конфига: {e}")
            return False

    @property
    def config(self) -> AppConfig:
        """Возвращает текущую конфигурацию."""
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Получает значение по точечному пути (например 'ai.provider')."""
        parts = key.split(".")
        obj: Any = self._config
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return default
        return obj

    def set(self, key: str, value: Any) -> bool:
        """Устанавливает значение по точечному пути."""
        parts = key.split(".")
        if len(parts) < 2:
            return False
        section = parts[0]
        field = ".".join(parts[1:])
        section_obj = getattr(self._config, section, None)
        if section_obj is None:
            return False
        try:
            if "." in field:
                sub_parts = field.split(".")
                sub_obj = section_obj
                for p in sub_parts[:-1]:
                    sub_obj = getattr(sub_obj, p)
                setattr(sub_obj, sub_parts[-1], value)
            else:
                setattr(section_obj, field, value)
            return True
        except Exception as e:
            logger.error(f"Ошибка установки значения {key}: {e}")
            return False

    def get_api_key(self) -> str:
        """Получает API ключ из config.json или keyring."""
        stored = self._config.ai.api_key
        if stored == "__keyring__":
            try:
                import keyring

                key = keyring.get_password(
                    "cli-assistant",
                    f"api_key_{self._config.ai.provider}",
                )
                if key:
                    return key
            except Exception:
                pass
            return ""

        if stored:
            try:
                return base64.b64decode(stored.encode()).decode()
            except Exception:
                return stored

        return ""

    def set_api_key(self, key: str) -> bool:
        """Сохраняет API ключ безопасно."""
        try:
            import keyring
            keyring.set_password(
                "cli-assistant",
                f"api_key_{self._config.ai.provider}",
                key,
            )
            self._config.ai.api_key = "__keyring__"
            return True
        except Exception:
            pass

        # Fallback: base64
        try:
            encoded = base64.b64encode(key.encode()).decode()
            self._config.ai.api_key = encoded
            logger.warning("keyring недоступен, API ключ сохранён в base64 (небезопасно)")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения API ключа: {e}")
            return False

    def clear_keyring(self) -> bool:
        """Удаляет сохранённые API ключи из keyring для всех провайдеров."""
        providers = {"anthropic", "gemini", "openai_compatible", self._config.ai.provider}

        try:
            import keyring
        except Exception:
            return True

        success = True
        for provider in providers:
            try:
                keyring.delete_password("cli-assistant", f"api_key_{provider}")
            except Exception:
                success = False
        return success

    def reset(self) -> bool:
        """Сбрасывает конфигурацию к дефолтным значениям."""
        self._config = self._load_defaults()
        return self.save()

    def is_configured(self) -> bool:
        """Проверяет настроен ли ассистент (провайдер и API ключ)."""
        if not self.config_exists():
            return False
        if not self.config.ai.provider:
            return False
        api_key = self.get_api_key()
        if api_key:
            return True
        if self.config.ai.provider == "openai_compatible":
            return bool(self.config.ai.base_url and self.config.ai.model)
        return False

    def reload(self) -> None:
        """Перезагружает конфигурацию из файла."""
        self.load()

    # ─── Мульти-профили ─────────────────────────────────────────────────────

    def get_profiles(self) -> Dict[str, Dict[str, str]]:
        """Возвращает словарь профилей как dict[name -> dict]."""
        try:
            return {n: p.model_dump() for n, p in self._config.profiles.items()}
        except Exception:
            return {}

    def get_active_profile(self) -> str:
        """Имя активного профиля или пустая строка."""
        try:
            name = self._config.active_profile or ""
            if name and name in self._config.profiles:
                return name
        except Exception:
            pass
        return ""

    def _store_profile_api_key(self, profile_name: str, key: str) -> str:
        """
        Сохраняет API ключ профиля в keyring (под уникальным сервисом для профиля)
        или fallback в base64. Возвращает значение, которое надо положить в
        profile.api_key ("__keyring__" или base64).
        """
        if not key:
            return ""
        try:
            import keyring
            keyring.set_password(
                "cli-assistant-profile",
                f"api_key_{profile_name}",
                key,
            )
            return "__keyring__"
        except Exception:
            pass
        try:
            return base64.b64encode(key.encode()).decode()
        except Exception:
            return ""

    def _read_profile_api_key(self, profile_name: str, stored: str) -> str:
        """Извлекает API ключ профиля из хранилища."""
        if not stored:
            return ""
        if stored == "__keyring__":
            try:
                import keyring
                k = keyring.get_password("cli-assistant-profile", f"api_key_{profile_name}")
                return k or ""
            except Exception:
                return ""
        try:
            return base64.b64decode(stored.encode()).decode()
        except Exception:
            return stored

    def add_profile(
        self,
        name: str,
        provider: str,
        model: str,
        api_key: str,
        base_url: str = "",
    ) -> bool:
        """Добавляет новый профиль. Возвращает False если уже существует или ошибка."""
        name = (name or "").strip()
        if not name:
            return False
        if name in self._config.profiles:
            return False
        try:
            stored_key = self._store_profile_api_key(name, api_key)
            self._config.profiles[name] = ProfileConfig(
                provider=provider,
                model=model,
                api_key=stored_key,
                base_url=base_url,
            )
            # Если активный профиль не задан — делаем этот активным и
            # синхронизируем ai-конфиг.
            if not self._config.active_profile:
                self.switch_profile(name)
            self.save()
            return True
        except Exception as e:
            logger.error(f"add_profile error: {e}")
            return False

    def delete_profile(self, name: str) -> bool:
        """Удаляет профиль по имени."""
        if name not in self._config.profiles:
            return False
        try:
            del self._config.profiles[name]
            try:
                import keyring
                keyring.delete_password("cli-assistant-profile", f"api_key_{name}")
            except Exception:
                pass
            if self._config.active_profile == name:
                self._config.active_profile = ""
            self.save()
            return True
        except Exception as e:
            logger.error(f"delete_profile error: {e}")
            return False

    def switch_profile(self, name: str) -> bool:
        """Делает указанный профиль активным и копирует его в ai-секцию."""
        if name not in self._config.profiles:
            return False
        try:
            p = self._config.profiles[name]
            self._config.ai.provider = p.provider
            self._config.ai.model = p.model
            self._config.ai.base_url = p.base_url
            # Прокидываем сырое значение api_key (строку, что в профиле).
            # Для get_api_key() — он сам распознает __keyring__/base64.
            # Но keyring у нас под другим service-name, поэтому достаём ключ
            # вручную и сохраняем уже под обычным service-name.
            real_key = self._read_profile_api_key(name, p.api_key)
            if real_key:
                # Сохраняем под "обычным" сервисом cli-assistant/api_key_<provider>
                self.set_api_key(real_key)
            else:
                self._config.ai.api_key = ""
            self._config.active_profile = name
            self.save()
            return True
        except Exception as e:
            logger.error(f"switch_profile error: {e}")
            return False

    def update_profile(
        self,
        name: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> bool:
        """Обновляет поля существующего профиля."""
        if name not in self._config.profiles:
            return False
        try:
            p = self._config.profiles[name]
            if provider is not None:
                p.provider = provider
            if model is not None:
                p.model = model
            if base_url is not None:
                p.base_url = base_url
            if api_key is not None:
                p.api_key = self._store_profile_api_key(name, api_key)
            self.save()
            # Если это активный профиль — синхронизируем ai-секцию
            if self._config.active_profile == name:
                self.switch_profile(name)
            return True
        except Exception as e:
            logger.error(f"update_profile error: {e}")
            return False


# Глобальный экземпляр
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Возвращает глобальный экземпляр ConfigManager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
        _config_manager.load()
    return _config_manager
