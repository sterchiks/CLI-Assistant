<div align="center">

# 🤖 CLI Assistant

### Your personal AI assistant right in the terminal

*Manage Linux / macOS / Windows in plain language. Safe. Transparent. No pain.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/Built_with-Textual-5A45FF?style=for-the-badge)](https://github.com/Textualize/textual)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Linux_•_macOS_•_Windows-supported-orange?style=for-the-badge)]()

[Installation](#-installation) •
[Features](#-features) •
[Screenshots](#-screenshots) •
[Commands](#-slash-commands) •
[Architecture](#-architecture) •
[FAQ](#-faq)

---

> "Delete all .log files in /var/log older than 7 days"  
> "Show me what's taking up the most disk space"  
> "Start docker-compose in this folder and tail the nginx logs"

All of this — in plain English, right in your terminal.

</div>

---

## ✨ What is this?

**CLI Assistant** is a TUI interface (text-based, like `htop` or `lazygit`) where you talk to a modern LLM (Claude / Gemini / any OpenAI-compatible) in natural language. The assistant **automatically** calls the right tools — reads files, runs commands, installs packages, manages services — and **shows every step** before executing it.

Perfect for:

- 🆕 Beginners who are scared of `bash`
- ⚡ Power users who can't remember every `find`, `awk`, `journalctl` flag
- 🛠 DevOps — for routine tasks: restarting services, cleaning logs, checking ports
- 🧪 Testers and students learning Linux

---

## 🌟 Features

<table>
<tr>
<td width="50%" valign="top">

### 🧠 Multiple AI Providers
- **Anthropic** Claude (Opus / Sonnet / Haiku)
- **Google** Gemini 2.x / 1.5
- **OpenAI-compatible**:
  - OpenAI, Groq, Together AI
  - **Ollama / LM Studio** (local, free)
  - OpenRouter, Mistral

### 🎨 5 Built-in Themes
`dark` • `light` • `cyberpunk` • `nord` • `solarized`

### 🌍 Localization
Russian 🇷🇺 and English 🇬🇧 out of the box

### 🔒 Secure Key Storage
Via system keyring (KWallet, GNOME Keyring, macOS Keychain, Windows Credential Locker)

</td>
<td width="50%" valign="top">

### 🛠 60+ Tools in 14 Categories
- 📂 **Files** — read / write / search / edit
- 🗂 **Filesystem** — copy, permissions, ownership
- 💻 **Terminal** — run commands, open new windows
- 💾 **Disks** — partitions, mounting, lsblk
- 🔐 **Sudo** — password cached in memory for 15 min
- 🌐 **Network** — ping, ports, HTTP, file download
- 📦 **Packages** — apt / dnf / pacman / brew / winget / pip / npm
- ⚙️ **Processes** — psutil-powered htop alternative
- 📦 **Archives** — zip / tar / tar.gz / bz2 / xz
- 🌿 **Git** — status / commit / push / clone / branch
- 🔧 **systemd** — services, journals, autostart
- 🪟 **GUI Apps** — open, close, move between workspaces
- ⏰ **Cron** — human-readable format (`every day at 9:30`)

</td>
</tr>
</table>

---

## 📸 Screenshots

<div align="center">

### Main Screen
<!-- ![main](docs/screenshots/main.png) -->
*— screenshot coming soon —*

### Setup Wizard
<!-- ![wizard](docs/screenshots/wizard.png) -->
*— screenshot coming soon —*

### Dangerous Action Confirmation
<!-- ![confirm](docs/screenshots/confirm.png) -->
*— screenshot coming soon —*

### Themes

<table>
<tr>
<th>Dark</th><th>Cyberpunk</th><th>Nord</th><th>Solarized</th>
</tr>
<tr>
<td>🌑</td>
<td>🌆</td>
<td>❄️</td>
<td>☀️</td>
</tr>
</table>

</div>

---

## 🚀 Installation

### Linux / macOS

```bash
git clone https://github.com/yourname/cli-assistant.git
cd cli-assistant
chmod +x install.sh
./install.sh
```

After installation, launch from anywhere:

```bash
cli-assistant     # or just `ai` if you accepted the alias
```

### Windows

```powershell
git clone https://github.com/yourname/cli-assistant.git
cd cli-assistant
install.bat
```

### Manual Installation (for developers)

```bash
python3 -m venv venv
source venv/bin/activate         # Linux/macOS
# venv\Scripts\activate          # Windows

pip install -r requirements.txt
python -m src.main
```

### install.sh Flags

| Flag | Action |
|------|--------|
| `--update` | Update an existing installation |
| `--reset-config` | Reset config at `~/.cli-assistant/config.json` |
| `--uninstall` | Full removal |
| `--check` | Check dependencies only, install nothing |
| `--deps-only` | Install/update dependencies only |

---

## ⚙️ First Launch

On first launch, the **Setup Wizard** walks you through the setup:

```
┌─────────────────────────────────────────────────┐
│  🤖 Welcome to CLI Assistant!                   │
│                                                 │
│  1. Choose language                             │
│  2. Choose AI provider                          │
│  3. Enter API key (with connection test)        │
│  4. Select model                                │
│  5. Security settings                           │
│  6. Choose theme                                │
│  7. Test request                                │
│                                                 │
│           [ Start Setup ]                       │
└─────────────────────────────────────────────────┘
```

Config is saved to `~/.cli-assistant/config.json`, keys go into the system keyring.

---

## 🤖 Supported AI Providers

| Provider | Models | Free tier |
|----------|--------|-----------|
| **Google Gemini** | gemini-2.0-flash, gemini-1.5-pro | ✅ Yes (AI Studio) |
| **Anthropic Claude** | claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5 | ❌ Paid |
| **OpenAI** | gpt-4o, gpt-4o-mini | ❌ Paid |
| **Ollama** (local) | llama3.2, mistral, qwen and more | ✅ Free |
| **Groq** | llama-3.3-70b and more | ✅ Free |
| **LM Studio** | any local model | ✅ Free |
| **OpenRouter** | 200+ models | ✅ Partly free |

> 💡 **Recommended for starters: Google AI Studio** — free API key in 30 seconds at [aistudio.google.com](https://aistudio.google.com)

---

## 💬 Slash Commands

Available directly in the chat (start with `/`):

| Command | Description |
|---|---|
| `/help` | List all commands |
| `/settings` | Open full settings screen |
| `/provider <name>` | Switch provider (`anthropic` / `gemini` / `openai_compatible`) |
| `/model <name>` | Switch model |
| `/theme <name>` | Switch UI theme |
| `/apikey` | Securely update API key |
| `/baseurl <url>` | Change base URL (for Ollama, OpenRouter, etc.) |
| `/cd <path>` | Change working directory |
| `/ls` | List current directory contents |
| `/sudo` | Request sudo password for the session |
| `/sudo clear` | Clear sudo cache |
| `/clear` | Clear chat history |
| `/history` | Show recent messages |
| `/export <path>` | Export history to JSON / Markdown |

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `Ctrl+C` | Quit |
| `Ctrl+S` | Open settings |
| `Ctrl+L` | Clear chat |
| `Enter` | Send message |
| `↑ / ↓` | Navigate input history |

---

## 🔒 Security

CLI Assistant is designed to **minimize the risk of irreversible actions**:

- ✅ **Confirmation before delete, overwrite, and sudo commands** (configurable)
- ✅ **Protected paths** are never modified: `/etc/passwd`, `/etc/shadow`, `/etc/sudoers`, `/boot/*`, `/dev/*`
- ✅ **API keys stored in system keyring**, never in plaintext
- ✅ **Sudo password only in process memory**, auto-cleared after configurable timeout
- ✅ **File read size limit** (50 MB by default)
- ✅ **Sudo command whitelist** (optional)
- ✅ **System prompt blocks** `rm -rf /`, fork bombs, and similar; the assistant will suggest a safe alternative
- ✅ **All errors logged** to `~/.cli-assistant/logs/error.log`, not dumped as stack traces

---

## 🏗 Architecture

```
cli-assistant/
├── install.sh / install.bat / run.sh
├── requirements.txt
├── config/default_config.json
└── src/
    ├── main.py                    # entry point, argument parser
    ├── ai/                        # AI providers (unified interface)
    │   ├── provider.py            # BaseProvider (ABC)
    │   ├── anthropic_provider.py
    │   ├── gemini_provider.py
    │   ├── openai_provider.py     # + any OpenAI-compatible API
    │   └── provider_factory.py
    ├── tools/                     # 14 tool sets
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
    │   ├── assistant.py           # main orchestrator
    │   ├── tool_executor.py       # function calling + dispatch
    │   └── safety.py              # checks and confirmations
    ├── settings/
    │   ├── config_manager.py      # pydantic + keyring
    │   └── settings_ui.py
    ├── ui/
    │   ├── chat_ui.py             # Textual App
    │   ├── setup_wizard.py
    │   └── themes.py              # themes as Textual CSS
    └── i18n/
        ├── ru.json
        └── en.json
```

### Stack

| Component | Technology |
|---|---|
| TUI Framework | [Textual](https://github.com/Textualize/textual) |
| Formatting | [Rich](https://github.com/Textualize/rich) |
| AI SDKs | `anthropic` • `google-generativeai` • `openai` |
| Config | `pydantic` |
| Key Storage | `keyring` |
| System Info | `psutil` |
| Async I/O | `asyncio` + `aiofiles` |

---

## 🔌 Adding a New AI Provider

1. Create `src/ai/myprovider.py`, inherit from `BaseProvider`:

```python
from .provider import BaseProvider

class MyProvider(BaseProvider):
    async def chat(self, messages, tools, stream): ...
    async def test_connection(self) -> bool: ...
    def get_available_models(self) -> list[str]: ...
```

2. Register it in `src/ai/provider_factory.py`:

```python
elif name == "my_provider":
    return MyProvider(config)
```

3. Add the option in `src/ui/setup_wizard.py` and in the default config.

Done — the assistant will immediately pick up the new provider in `/provider` and in the Setup Wizard.

---

## 🧩 Adding a New Tool

1. Create `src/tools/my_tool.py` with a class and methods.
2. Add the import to `src/tools/__init__.py`.
3. Add the description to `TOOL_DEFINITIONS` in `src/core/tool_executor.py`.
4. Add `elif tool_name == "my_action": ...` to `_dispatch()`.

The LLM will **immediately** see your tool via function calling — no extra configuration needed.

---

## ❓ FAQ

<details>
<summary><b>Does it work offline?</b></summary>

Yes, if you use **Ollama** or **LM Studio** as the provider. In the Setup Wizard, choose *OpenAI-compatible*, set Base URL to `http://localhost:11434/v1` (Ollama) or `http://localhost:1234/v1` (LM Studio).

</details>

<details>
<summary><b>What about Windows?</b></summary>

Supported. Most tools are cross-platform (`psutil`, file operations, network, git, archives, pip/npm/winget). Linux-specific limitations:
- `service_manager` (systemd) — not available
- `app_manager` uses PowerShell instead of `wmctrl`
- `disk_manager.mount/unmount` works on Linux only

</details>

<details>
<summary><b>How much does it cost?</b></summary>

The assistant itself is **free and open source**. You only pay for the API provider (or use a local model via Ollama — that's **$0**).

Roughly: 1 tool-use request ≈ $0.001–0.01 for Claude Haiku / Gemini Flash.

</details>

<details>
<summary><b>Where are conversations stored?</b></summary>

In `~/.cli-assistant/history.json`. Default limit is the last 1000 messages. Can be disabled in settings or exported via `/export`.

</details>

<details>
<summary><b>Can I block certain commands?</b></summary>

Yes. In the config:
```json
"safety": {
  "blocked_paths": ["/etc/passwd", "/important/data"],
  "allowed_sudo_commands": ["systemctl", "apt"]
}
```
If `allowed_sudo_commands` is empty — all commands are allowed.

</details>

---

## 🤝 Contributing

PRs and Issues are welcome! Especially appreciated:

- 🌍 New localization languages (just add `src/i18n/<lang>.json`)
- 🎨 New UI themes
- 🔌 Support for new AI providers
- 🛠 New tools (see [Adding a New Tool](#-adding-a-new-tool))

```bash
git clone https://github.com/yourname/cli-assistant.git
cd cli-assistant
pip install -r requirements.txt
python -m src.main
```

---

## 📄 License

MIT — do whatever you want, but no warranties.  
See [LICENSE](LICENSE).

---

<div align="center">

### Made with ❤️ for everyone who's afraid of `man bash`

**[⭐ Star this repo](https://github.com/yourname/cli-assistant)** if you find it useful!

</div>
