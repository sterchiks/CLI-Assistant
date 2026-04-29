"""Фабрика AI провайдеров."""

import logging
from typing import Optional

from .provider import BaseProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Создаёт экземпляры AI провайдеров по конфигурации."""

    @staticmethod
    def create(
        provider_name: str,
        api_key: str,
        model: str,
        base_url: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> Optional[BaseProvider]:
        """
        Создаёт провайдер по имени.

        Args:
            provider_name: 'anthropic' | 'gemini' | 'openai_compatible'
            api_key: API ключ
            model: название модели
            base_url: базовый URL (для openai_compatible)
            temperature: температура генерации
            max_tokens: максимум токенов
            system_prompt: системный промпт

        Returns:
            Экземпляр провайдера или None при ошибке
        """
        try:
            if provider_name == "anthropic":
                from .anthropic_provider import AnthropicProvider
                return AnthropicProvider(
                    api_key=api_key,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    base_url=base_url,
                )

            elif provider_name == "gemini":
                from .gemini_provider import GeminiProvider
                return GeminiProvider(
                    api_key=api_key,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )

            elif provider_name == "openai_compatible":
                from .openai_provider import OpenAICompatibleProvider
                return OpenAICompatibleProvider(
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )

            else:
                logger.error(f"Неизвестный провайдер: {provider_name}")
                return None

        except Exception as e:
            logger.error(f"Ошибка создания провайдера {provider_name}: {e}")
            return None

    @staticmethod
    def create_from_config(config) -> Optional[BaseProvider]:
        """Создаёт провайдер из объекта конфигурации AppConfig."""
        from ..settings.config_manager import get_config_manager
        cm = get_config_manager()
        api_key = cm.get_api_key()

        return ProviderFactory.create(
            provider_name=config.ai.provider,
            api_key=api_key,
            model=config.ai.model,
            base_url=config.ai.base_url,
            temperature=config.ai.temperature,
            max_tokens=config.ai.max_tokens,
            system_prompt=config.ai.system_prompt,
        )

    @staticmethod
    def get_models_for_provider(provider_name: str) -> list[str]:
        """Возвращает список моделей для провайдера."""
        from .anthropic_provider import ANTHROPIC_MODELS
        from .gemini_provider import GEMINI_MODELS
        from .openai_provider import OPENAI_MODELS

        mapping = {
            "anthropic": ANTHROPIC_MODELS,
            "gemini": GEMINI_MODELS,
            "openai_compatible": OPENAI_MODELS,
        }
        return mapping.get(provider_name, [])
