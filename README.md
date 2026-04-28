<div align="center">

# 🤖 CLI Assistant

### Ваш персональный AI-помощник прямо в терминале

*Управляйте Linux / macOS / Windows на естественном языке. Безопасно. Прозрачно. Без боли.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/Built_with-Textual-5A45FF?style=for-the-badge)](https://github.com/Textualize/textual)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Linux_•_macOS_•_Windows-supported-orange?style=for-the-badge)]()

[Установка](#-установка) •
[Возможности](#-возможности) •
[Скриншоты](#-скриншоты) •
[Команды](#-slash-команды) •
[Архитектура](#-архитектура) •
[FAQ](#-faq)

---

> «Удали все .log файлы в /var/log старше 7 дней»  
> «Покажи, что занимает больше всего места»  
> «Подними docker-compose в этой папке и открой логи nginx»

И всё это — на русском, английском или любом другом языке. Прямо в терминале.

</div>

---

## ✨ Что это?

**CLI Assistant** — это TUI-интерфейс (текстовый, как у `htop` или `lazygit`), в котором вы общаетесь с современной LLM (Claude / Gemini / любая OpenAI-совместимая) на естественном языке. Ассистент **сам** вызывает нужные инструменты — читает файлы, выполняет команды, ставит пакеты, управляет сервисами — и **показывает каждый шаг** перед выполнением.

Идеально подходит:

- 🆕 Новичкам, которые боятся `bash`
- ⚡ Опытным пользователям, которым лень помнить флаги `find`, `awk`, `journalctl`
- 🛠 DevOps — для рутины: рестарт сервисов, чистка логов, проверка портов
- 🧪 Тестировщикам и студентам, изучающим Linux

---

## 🌟 Возможности

<table>
<tr>
<td width="50%" valign="top">

### 🧠 Несколько AI-провайдеров
- **Anthropic** Claude (Opus / Sonnet / Haiku)
- **Google** Gemini 2.x / 1.5
- **OpenAI-совместимые**:
  - OpenAI, Groq, Together AI
  - **Ollama / LM Studio** (локально, бесплатно)
  - OpenRouter, Mistral

### 🎨 5 встроенных тем
`dark` • `light` • `cyberpunk` • `nord` • `solarized`

### 🌍 Локализация
Русский 🇷🇺 и Английский 🇬🇧 из коробки

### 🔒 Безопасное хранение ключей
Через системный keyring (KWallet, GNOME Keyring, macOS Keychain, Windows Credential Locker)

</td>
<td width="50%" valign="top">

### 🛠 60+ инструментов в 14 категориях
- 📂 **Файлы** — чтение / запись / поиск / редактирование
- 🗂 **Управление ФС** — копирование, права, владельцы
- 💻 **Терминал** — выполнение команд, новые окна
- 💾 **Диски** — разделы, монтирование, lsblk
- 🔐 **Sudo** — кэширование пароля в памяти на 15 мин
- 🌐 **Сеть** — ping, порты, HTTP, скачивание
- 📦 **Пакеты** — apt / dnf / pacman / brew / winget / pip / npm
- ⚙️ **Процессы** — psutil-аналог htop
- 📦 **Архивы** — zip / tar / tar.gz / bz2 / xz
- 🌿 **Git** — status / commit / push / clone / branch
- 🔧 **systemd** — сервисы, журналы, автозапуск
- 🪟 **GUI-приложения** — открыть, закрыть, рабочие столы
- ⏰ **Cron** — человеческий формат (`every day at 9:30`)

</td>
</tr>
</table>

---

## 📸 Скриншоты

> *Сюда я прикреплю скрины запуска, чата, мастера настройки и тем оформления.*

<div align="center">

### Главный экран

<!-- ![main](docs/screenshots/main.png) -->
*— скриншот будет добавлен —*

### Setup Wizard

<!-- ![wizard](docs/screenshots/wizard.png) -->
*— скриншот будет добавлен —*

### Подтверждение опасных операций

<!-- ![confirm](docs/screenshots/confirm.png) -->
*— скриншот будет добавлен —*

### Темы

<table>
<tr>
<th>Dark</th><th>Cyberpunk</th><th>Nord</th><th>Solarized</th>
</tr>
<tr>
<td><!-- ![dark](docs/themes/dark.png) --> 🌑</td>
<td><!-- ![cyber](docs/themes/cyberpunk.png) --> 🌆</td>
<td><!-- ![nord](docs/themes/nord.png) --> ❄️</td>
<td><!-- ![sol](docs/themes/solarized.png) --> ☀️</td>
</tr>
</table>

</div>

---

## 🚀 Установка

### Linux / macOS

```bash
git clone https://github.com/yourname/cli-assistant.git
cd cli-assistant
chmod +x install.sh
./install.sh
```

После установки запускайте откуда угодно:

```bash
cli-assistant     # или просто `ai` если согласились на алиас
```

### Windows

```powershell
git clone https://github.com/yourname/cli-assistant.git
cd cli-assistant
install.bat
```

### Ручная установка (для разработчиков)

```bash
python3 -m venv venv
source venv/bin/activate         # Linux/macOS
# venv\Scripts\activate          # Windows

pip install -r requirements.txt
python -m src.main
```

### Флаги install.sh

| Флаг | Действие |
|------|----------|
| `--update` | Обновить существующую установку |
| `--reset-config` | Сбросить конфиг в `~/.cli-assistant/config.json` |
| `--uninstall` | Полное удаление |

---

## ⚙️ Первый запуск

При первом запуске откроется **Setup Wizard**, который проведёт по 7 шагам:

```
┌─────────────────────────────────────────────────┐
│  🤖 Добро пожаловать в CLI Assistant!           │
│                                                 │
│  1. Выбор AI-провайдера                         │
│  2. Ввод API-ключа (с проверкой подключения)    │
│  3. Выбор модели                                │
│  4. Настройки безопасности                      │
│  5. Выбор темы                                  │
│  6. Тестовый запрос                             │
│                                                 │
│           [ Начать настройку ]                  │
└─────────────────────────────────────────────────┘
```

Конфиг сохраняется в `~/.cli-assistant/config.json`, ключи — в системном keyring.

---

## 💬 Slash-команды

Прямо в чате доступны команды (начинаются с `/`):

| Команда | Назначение |
|---|---|
| `/help` | Список всех команд |
| `/settings` | Открыть полный экран настроек |
| `/provider <name>` | Сменить провайдера (`anthropic` / `gemini` / `openai_compatible`) |
| `/model <name>` | Сменить модель |
| `/theme <name>` | Сменить тему оформления |
| `/apikey` | Безопасно изменить API-ключ |
| `/baseurl <url>` | Изменить base URL (для Ollama, OpenRouter и т. д.) |
| `/cd <path>` | Сменить рабочую директорию |
| `/ls` | Показать содержимое текущей папки |
| `/sudo` | Запросить пароль sudo на сессию |
| `/sudo clear` | Очистить кэш sudo |
| `/clear` | Очистить историю чата |
| `/history` | Показать последние сообщения |
| `/export <path>` | Экспорт истории в JSON / Markdown |

### Горячие клавиши

| Клавиша | Действие |
|---|---|
| `Ctrl+C` | Выход |
| `Ctrl+S` | Открыть настройки |
| `Ctrl+L` | Очистить чат |
| `Enter` | Отправить сообщение |
| `↑ / ↓` | Навигация по истории ввода |

---

## 🔒 Безопасность

CLI Assistant спроектирован так, чтобы **минимизировать риск необратимых действий**:

- ✅ **Подтверждение перед удалением, перезаписью, sudo-командами** (настраивается)
- ✅ **Защищённые пути** не редактируются никогда: `/etc/passwd`, `/etc/shadow`, `/etc/sudoers`, `/boot/*`, `/dev/*`
- ✅ **API-ключи в системном keyring**, никогда в plaintext
- ✅ **Sudo-пароль только в памяти процесса**, авто-очистка через настраиваемое время
- ✅ **Ограничение размера читаемых файлов** (по умолчанию 50 МБ)
- ✅ **Whitelist sudo-команд** (опционально)
- ✅ **Системный промпт запрещает** `rm -rf /`, fork-бомбы и подобное; ассистент сам предложит безопасную альтернативу
- ✅ **Все ошибки логируются** в `~/.cli-assistant/logs/error.log`, а не сваливаются в стектрейс на пол-экрана

---

## 🏗 Архитектура

```
cli-assistant/
├── install.sh / install.bat / run.sh
├── requirements.txt
├── config/default_config.json
└── src/
    ├── main.py                    # точка входа, парсер аргументов
    ├── ai/                        # AI-провайдеры (единый интерфейс)
    │   ├── provider.py            # BaseProvider (ABC)
    │   ├── anthropic_provider.py
    │   ├── gemini_provider.py
    │   ├── openai_provider.py     # + любой OpenAI-compatible API
    │   └── provider_factory.py
    ├── tools/                     # 14 наборов инструментов
    │   ├── file_reader.py
    │   ├── file_manager.py
    │   ├── file_editor.py
    │   ├── terminal_manager.py
    │   ├── disk_manager.py
    │   ├── sudo_manager.py
    │   ├── network_tool.py
    │   ├── package_manager.py
    │   ├── process_manager.py
    │   ├── archive_tool.py
    │   ├── git_tool.py
    │   ├── service_manager.py
    │   ├── app_manager.py
    │   └── cron_tool.py
    ├── core/
    │   ├── assistant.py           # главный оркестратор
    │   ├── tool_executor.py       # function calling + dispatch
    │   └── safety.py              # проверки и подтверждения
    ├── settings/
    │   ├── config_manager.py      # pydantic + keyring
    │   └── settings_ui.py
    ├── ui/
    │   ├── chat_ui.py             # Textual App
    │   ├── setup_wizard.py
    │   └── themes.py              # 5 тем как Textual CSS
    └── i18n/
        ├── ru.json
        └── en.json
```

### Stack

| Компонент | Технология |
|---|---|
| TUI-фреймворк | [Textual](https://github.com/Textualize/textual) |
| Форматирование | [Rich](https://github.com/Textualize/rich) |
| AI SDK | `anthropic` • `google-generativeai` • `openai` |
| Конфиг | `pydantic` |
| Хранение ключей | `keyring` |
| Системная инфа | `psutil` |
| Async I/O | `asyncio` + `aiofiles` |

---

## 🔌 Как добавить нового AI-провайдера

1. Создайте `src/ai/myprovider.py`, унаследуйтесь от `BaseProvider`:

```python
from .provider import BaseProvider

class MyProvider(BaseProvider):
    async def chat(self, messages, tools, stream): ...
    async def test_connection(self) -> bool: ...
    def get_available_models(self) -> list[str]: ...
```

2. Добавьте в `src/ai/provider_factory.py`:

```python
elif name == "my_provider":
    return MyProvider(config)
```

3. Зарегистрируйте опцию в `src/ui/setup_wizard.py` и в дефолтном конфиге.

Готово — ассистент сразу подхватит нового провайдера в `/provider` и в Setup Wizard.

---

## 🧩 Как добавить новый инструмент

1. Создайте файл `src/tools/my_tool.py` с классом и методами.
2. Добавьте импорт в `src/tools/__init__.py`.
3. Добавьте описание в `TOOL_DEFINITIONS` в `src/core/tool_executor.py`.
4. Добавьте `elif tool_name == "my_action": ...` в `_dispatch()`.

LLM **немедленно** увидит ваш инструмент через function calling — никакой дополнительной настройки не нужно.

---

## ❓ FAQ

<details>
<summary><b>Это работает оффлайн?</b></summary>

Да, если использовать **Ollama** или **LM Studio** как провайдера. В Setup Wizard выберите *OpenAI-совместимый*, в Base URL укажите `http://localhost:11434/v1` (Ollama) или `http://localhost:1234/v1` (LM Studio).

</details>

<details>
<summary><b>А что насчёт Windows?</b></summary>

Поддерживается. Большинство инструментов кросс-платформенные (`psutil`, файловые операции, сеть, git, архивы, pip/npm/winget). Что специфично для Linux:
- `service_manager` (systemd) — недоступен
- `app_manager` использует PowerShell вместо `wmctrl`
- `disk_manager.mount/unmount` работает только на Linux

</details>

<details>
<summary><b>Сколько это стоит?</b></summary>

Сам ассистент — **бесплатный и open source**. Платите только за API провайдера (или используйте локальную модель через Ollama — тогда **0 ₽**).

Примерно: 1 запрос с tool use ≈ $0.001–0.01 для Claude Haiku / Gemini Flash.

</details>

<details>
<summary><b>Где хранятся диалоги?</b></summary>

В `~/.cli-assistant/history.json`. По умолчанию — последние 1000 сообщений. Можно отключить в настройках или экспортировать через `/export`.

</details>

<details>
<summary><b>Можно ли запретить определённые команды?</b></summary>

Да. В конфиге:
```json
"safety": {
  "blocked_paths": ["/etc/passwd", "/важные/данные"],
  "allowed_sudo_commands": ["systemctl", "apt"]
}
```
Если `allowed_sudo_commands` пустой — разрешены все.

</details>

---

## 🤝 Вклад в проект

PR'ы и Issue приветствуются! Особенно интересны:

- 🌍 Новые языки локализации (просто добавьте `src/i18n/<lang>.json`)
- 🎨 Новые темы оформления
- 🔌 Поддержка новых AI-провайдеров
- 🛠 Новые инструменты (TUI scaffolding есть в [#как-добавить-новый-инструмент](#-как-добавить-новый-инструмент))

```bash
git clone https://github.com/yourname/cli-assistant.git
cd cli-assistant
pip install -r requirements.txt
python -m src.main
```

---

## 📄 Лицензия

MIT — делайте что хотите, но без гарантий.  
См. [LICENSE](LICENSE).

---

<div align="center">

### Made with ❤️ for everyone who's afraid of `man bash`

**[⭐ Поставьте звезду](https://github.com/yourname/cli-assistant)**, если проект оказался полезен!

</div>
