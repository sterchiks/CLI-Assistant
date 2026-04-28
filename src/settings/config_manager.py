"""Менеджер конфигурации CLI Assistant."""

import json
import os
import base64
import logging
from pathlib import Path
from typing import Any, Optional
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


class AppConfig(BaseModel):
    ai: AIConfig = Field(default_factory=AIConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)


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
        """Получает API ключ, пытаясь сначала из keyring."""
        try:
            import keyring
            key = keyring.get_password("cli-assistant", f"api_key_{self._config.ai.provider}")
            if key:
                return key
        except Exception:
            pass

        # Просто возвращаем ключ как есть (без base64)
        return self._config.ai.api_key or ""

    def set_api_key(self, key: str) -> bool:
        """Сохраняет API ключ безопасно."""
        try:
            import keyring
            keyring.set_password("cli-assistant", f"api_key_{self._config.ai.provider}", key)
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
        return bool(api_key) or self.config.ai.provider == "openai_compatible" and not self.config.ai.api_key

    def reload(self) -> None:
        """Перезагружает конфигурацию из файла."""
        self.load()


# Глобальный экземпляр
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Возвращает глобальный экземпляр ConfigManager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
        _config_manager.load()
    return _config_manager
