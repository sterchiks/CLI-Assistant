<div align="center">

```
  ██████╗██╗     ██╗      █████╗ ███████╗███████╗██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗
 ██╔════╝██║     ██║     ██╔══██╗██╔════╝██╔════╝██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝
 ██║     ██║     ██║     ███████║███████╗███████╗██║███████╗   ██║   ███████║██╔██╗ ██║   ██║   
 ██║     ██║     ██║     ██╔══██║╚════██║╚════██║██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║   
 ╚██████╗███████╗███████╗██║  ██║███████║███████║██║███████║   ██║   ██║  ██║██║ ╚████║   ██║   
  ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝  
```

**Твой ИИ-ассистент прямо в терминале**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Textual](https://img.shields.io/badge/TUI-Textual-00d4aa?style=for-the-badge)](https://github.com/Textualize/textual)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-orange?style=for-the-badge)](https://github.com)

*Управляй системой на человеческом языке — без знания Linux*

</div>

---

## ✨ Что это такое?

**CLI Assistant** — это интерактивный AI-ассистент для терминала. Вместо того чтобы гуглить команды или бояться что-то сломать — просто напиши что хочешь сделать, и ИИ всё сделает сам, объясняя каждое действие

---

## 🚀 Быстрый старт

```bash
# Клонируй репозиторий
git clone https://github.com/твой-username/cli-assistant.git
cd cli-assistant

# Запусти установку
chmod +x install.sh && ./install.sh
```

После установки мастер настройки запустится автоматически — выбери AI провайдера, вставь API ключ, и всё готово.

```bash
# Запуск после установки
ai

# Или полный путь
cli-assistant
```

---

## 🤖 Поддерживаемые AI провайдеры

| Провайдер | Модели | Бесплатно |
|-----------|--------|-----------|
| **Google Gemini** | gemini-2.0-flash, gemini-1.5-pro | ✅ Да (AI Studio) |
| **Anthropic Claude** | claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5 | ❌ Платно |
| **OpenAI** | gpt-4o, gpt-4o-mini | ❌ Платно |
| **Ollama** (локально) | llama3.2, mistral, qwen и др. | ✅ Бесплатно |
| **Groq** | llama-3.3-70b и др. | ✅ Бесплатно |
| **LM Studio** | любая локальная модель | ✅ Бесплатно |
| **OpenRouter** | 200+ моделей | ✅ Частично |

> 💡 **Рекомендуем начать с Google AI Studio** — бесплатный API ключ за 30 секунд на [aistudio.google.com](https://aistudio.google.com)

---

## 🛠️ Возможности

<table>
<tr>
<td width="50%">

**📂 Файлы и папки**
- Читать содержимое файлов
- Копировать, перемещать, удалять
- Переименовывать файлы и папки
- Поиск файлов по имени/содержимому
- Создание и редактирование файлов

</td>
<td width="50%">

**💻 Терминал и система**
- Выполнять команды в терминале
- Открывать новые окна терминала
- Просматривать запущенные процессы
- Доступ к разделам диска
- Поддержка sudo (с подтверждением)

</td>
</tr>
<tr>
<td>

**🎨 Красивый интерфейс**
- Пузыри сообщений как в мессенджере
- 5 цветовых тем (dark, light, cyberpunk, nord, solarized)
- Адаптивный layout — не ломается при resize
- Системная панель (CPU, RAM, диск)
- Стриминг ответов в реальном времени

</td>
<td>

**⚙️ Гибкая настройка**
- Смена провайдера/модели на лету
- Кастомный Base URL для любого API
- Безопасное хранение токенов (keyring)
- История чатов с экспортом
- Slash-команды для быстрого управления

</td>
</tr>
</table>

---

## ⌨️ Команды в чате

```
/help                — список всех команд
/settings            — открыть настройки
/provider [name]     — сменить провайдера (anthropic/gemini/openai_compatible)
/model [name]        — сменить модель
/apikey              — изменить API ключ
/baseurl [url]       — изменить Base URL
/theme [name]        — сменить тему оформления
/clear               — очистить историю чата
/cd [path]           — сменить рабочую директорию
/ls                  — содержимое текущей папки
/sudo                — запросить sudo для сессии
/export [path]       — экспортировать историю в файл
```

**Горячие клавиши:**

| Клавиша | Действие |
|---------|----------|
| `Ctrl+S` | Настройки |
| `Ctrl+L` | Очистить чат |
| `Ctrl+H` | Справка |
| `Ctrl+C` | Выход |
| `Enter` | Отправить сообщение |

---

## 📦 Установка Ollama (локальный ИИ, бесплатно)

Если не хочешь зависеть от облачных API:

```bash
# Установить Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Скачать модель (выбери одну)
ollama pull llama3.2        # 2 ГБ — хорошее качество
ollama pull llama3.2:1b     # 1 ГБ — быстрее, для слабых ПК
ollama pull qwen2.5:7b      # 4 ГБ — отличное качество
```

Затем в CLI Assistant:
```
/provider openai_compatible
/baseurl http://localhost:11434/v1
/apikey ollama
/model llama3.2
```

---

## 🏗️ Структура проекта

```
cli-assistant/
├── install.sh              # Установка (Linux/macOS)
├── install.bat             # Установка (Windows)
├── run.sh                  # Быстрый запуск
├── requirements.txt
├── config/
│   └── default_config.json
└── src/
    ├── main.py             # Точка входа
    ├── ui/
    │   ├── chat_ui.py      # Главный интерфейс
    │   ├── setup_wizard.py # Мастер настройки
    │   └── themes.py       # Темы оформления
    ├── ai/
    │   ├── anthropic_provider.py
    │   ├── gemini_provider.py
    │   ├── openai_provider.py
    │   └── provider_factory.py
    ├── tools/
    │   ├── file_reader.py
    │   ├── file_manager.py
    │   ├── file_editor.py
    │   ├── terminal_manager.py
    │   ├── disk_manager.py
    │   └── sudo_manager.py
    ├── core/
    │   ├── assistant.py
    │   └── safety.py
    └── settings/
        └── config_manager.py
```

---

## 🔒 Безопасность

- **API ключи** хранятся в системном keychain (keyring), не в plaintext
- **Sudo пароль** кэшируется только в памяти, не на диске (15 минут)
- **Деструктивные операции** (удаление, sudo) требуют подтверждения
- **Защищённые пути** — `/etc/passwd`, `/etc/shadow` и др. недоступны по умолчанию

---

## 🖥️ Системные требования

| | Минимум | Рекомендуется |
|---|---|---|
| **OS** | Linux | Ubuntu 22.04+ / Debian 12+ |
| **Python** | 3.10 | 3.12 |
| **RAM** | 256 МБ | 512 МБ+ |
| **Терминал** | 80×24 | 120×40+ |

---

## 🤝 Вклад в проект

Pull request'ы приветствуются! Особенно нужны:

- 🌍 Переводы интерфейса на другие языки
- 🔌 Новые AI провайдеры
- 🎨 Новые темы оформления
- 🐛 Исправления багов

---

## 📄 Лицензия

MIT License — делай что хочешь, только оставь упоминание автора.

---

<div align="center">

Сделано с ❤️ для людей которые хотят использовать Linux не ломая его

**[⭐ Поставь звезду если понравилось](https://github.com/твой-username/cli-assistant)**

</div>
