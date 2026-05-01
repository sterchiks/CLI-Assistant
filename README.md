<div align="center">

<img src="https://raw.githubusercontent.com/sterchiks/CLI-Assistant/main/src/gui_web/icons/icon.png" width="120" alt="CLI Assistant Logo" />

# CLI Assistant

**An AI-powered assistant for Linux — in your terminal and as a full GUI app**

*Perfect for beginners learning Linux and pros who want to move faster*

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux%20Only-FCC624?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/sterchiks/CLI-Assistant)
[![Debian](https://img.shields.io/badge/Debian%2FUbuntu-Ready-A81D33?style=for-the-badge&logo=debian&logoColor=white)](https://github.com/sterchiks/CLI-Assistant/releases)

<br/>

> **New to Linux?** Just tell CLI Assistant what you want in plain language.  
> **A pro?** Stop memorizing flags — describe the task and move on.

<br/>

[🚀 Quick Install](#-installation) · [📖 How It Works](#-how-it-works) · [🤖 AI Providers](#-supported-ai-providers) · [📸 Screenshots](#-screenshots) · [⌨️ Commands](#%EF%B8%8F-commands)

</div>

---

## 🤔 Why CLI Assistant?

Linux is powerful — but the learning curve is steep. Remembering the exact flags for `find`, `awk`, `rsync`, `journalctl`, or `systemctl` takes years. CLI Assistant bridges the gap:

| Without CLI Assistant | With CLI Assistant |
|---|---|
| `find /var/log -name "*.log" -mtime +7 -exec rm {} \;` | *"Delete log files older than 7 days"* |
| `du -sh /* 2>/dev/null \| sort -rh \| head -10` | *"What's taking up the most disk space?"* |
| `systemctl list-units --failed` | *"Show me what services are broken"* |
| `ss -tulpn \| grep LISTEN` | *"What ports are open on my system?"* |

The AI explains **every action before doing it**, so you learn while you work — no blind commands.

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🖥️ Two Interfaces
- **GUI App** — full graphical window, works like a modern chat
- **CLI/TUI** — runs entirely in the terminal (Textual-based)
- Both support the same AI providers and tools

### 🧠 Smart AI Integration
- Supports **Claude, Gemini, OpenAI, OpenRouter, Ollama** and any OpenAI-compatible API
- Switch providers and models on the fly
- Local AI support via Ollama — **no internet required, totally free**

### 🛡️ Safety First
- Confirms before **any destructive action** (delete, overwrite, sudo)
- Protected system paths (`/etc/passwd`, `/boot`, etc.)
- Sudo password cached in memory only — never written to disk

</td>
<td width="50%" valign="top">

### 🛠️ Powerful Tools
- 📂 **Files** — read, write, search, edit, copy, move, delete
- 💾 **Disk** — partitions, usage, mount/unmount
- 📦 **Packages** — apt, pip, npm, snap, flatpak
- ⚙️ **Services** — systemd start/stop/restart/logs
- 🌐 **Network** — ping, ports, download, speed
- 🔐 **Sudo** — safe privilege escalation
- 📊 **Processes** — kill, find, monitor
- 📦 **Archives** — zip, tar.gz, extract
- 🌿 **Git** — commit, push, pull, clone
- 🪟 **Apps** — open/close GUI apps, workspaces
- ⏰ **Cron** — schedule tasks in plain English

### 🎨 Looks Good Too
- Dark / Light / Cyberpunk / Nord and more themes
- Russian 🇷🇺 and English 🇬🇧 interface
- Responsive layout

</td>
</tr>
</table>

---

## 📸 Screenshots

### GUI Version
> *Full graphical window — launch from your app menu or run `cli-assistant-gui`*

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLI Assistant                              OpenAI · llama-3.3-70b  │
├──────────────────┬──────────────────────────────────────────────────┤
│                  │                                                   │
│  + New Chat      │          What can I help you with?               │
│                  │    Manage your system through dialogue.           │
│  ──────────────  │    I explain what I'm doing at every step.       │
│  CHATS           │                                                   │
│  > What takes... │   ┌──────────────────┐  ┌──────────────────┐    │
│                  │   │ 🖥 Disk usage     │  │ 🧠 Top processes │    │
│                  │   └──────────────────┘  └──────────────────┘    │
│                  │   ┌──────────────────┐  ┌──────────────────┐    │
│                  │   │ 📋 Find .log files│  │ ⚙️ System info   │    │
│                  │   └──────────────────┘  └──────────────────┘    │
│                  │                                                   │
│                  │  ┌─────────────────────────────────────────────┐ │
│  ⚙ Settings      │  │ Write a message...                          │ │
│  CLI Assistant   │  │  🛡 Safe  ·  llama-3.3-70b ▾          [➤] │ │
│  Local mode      │  └─────────────────────────────────────────────┘ │
└──────────────────┴──────────────────────────────────────────────────┘
```

### CLI / TUI Version
> *Runs directly in the terminal — launch with `cli-assistant`*

```
┌─────────────────────────────────────────────────────┬─────────────────────┐
│ 🤖 CLI Assistant │ gemini: gemini-2.0-flash │ ~/     │ SYSTEM              │
├─────────────────────────────────────────────────────│ CPU:  ████░░  42%   │
│                                                     │ RAM:  7.3/15.5 GB   │
│                   ╭──────────────────────────╮      │       ████████░░    │
│                   │ what takes the most space│      │                     │
│                   │ on my disk?              │      │ DISK                │
│                   │                  👤 You  │      │ /  168/242 GB       │
│                   ╰──────────────────────────╯      │    ██████████░░     │
│                                                     │                     │
│ 🤖 Assistant                                        │ NETWORK             │
│ ╭──────────────────────────────────────────╮        │ ↓ 2.3 MB/s          │
│ │ Analyzing disk usage in /home...         │        │ ↑ 0.4 MB/s          │
│ │ [🔧 get_disk_usage: /home]               │        │                     │
│ │                                          │        │ TOP PROCESSES       │
│ │ Top 5 by size:                           │        │ code      2.1 GB    │
│ │ • ~/Videos    — 42.3 GB                  │        │ firefox   1.4 GB    │
│ │ • ~/Downloads — 18.7 GB                  │        │ chrome    0.8 GB    │
│ │ • ~/.local    —  4.2 GB                  │        │                     │
│ │ Want to clean something up?              │        │ PATH                │
│ ╰──────────────────────────────────────────╯        │ /home/user          │
│                                                     │                     │
├─────────────────────────────────────────────────────┴─────────────────────┤
│ > Write a message or /command...                                   [Enter] │
│ ^s Settings   ^l Clear   ^h Help   esc Cancel                             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation

### Option 1 — Download .deb (Recommended)

The easiest way. The package installs everything automatically.

```bash
# Download the latest release
wget https://github.com/sterchiks/CLI-Assistant/releases/latest/download/cli-assistant_1.0.0_amd64.deb

# Install
sudo dpkg -i cli-assistant_1.0.0_amd64.deb

# Install system dependencies if needed
sudo apt-get install -f -y
```

After installation:
- **GUI version** → find "CLI Assistant" in your app menu, or run `cli-assistant-gui`
- **TUI version** → open a terminal and run `cli-assistant`

---

### Option 2 — Install from Source (CLI/TUI version)

```bash
# Clone the repo
git clone https://github.com/sterchiks/CLI-Assistant.git
cd CLI-Assistant

# Run the installer
chmod +x install.sh
./install.sh
```

The installer will:
1. Check for Python 3.10+
2. Create a virtual environment
3. Install all dependencies
4. Add `cli-assistant` to your PATH
5. Optionally add the `ai` alias to your `.bashrc`

After installation, open a new terminal and run:

```bash
cli-assistant
# or the short alias:
ai
```

---

### First Launch — Setup Wizard

On first launch, a setup wizard will guide you through:

1. **Choose language** — English or Russian
2. **Choose AI provider** — Gemini, Claude, OpenAI, OpenRouter, Ollama, or custom
3. **Enter API key** — with live connection test
4. **Select model**
5. **Security settings** — confirmation before destructive actions
6. **Choose theme**

Config is saved to `~/.cli-assistant/config.json`. API keys are stored securely in your system keyring.

---

## 🤖 Supported AI Providers

| Provider | Free Tier | API Key Format | Notes |
|----------|-----------|----------------|-------|
| **Google Gemini** | ✅ Yes | `AIza...` | Get free key at [aistudio.google.com](https://aistudio.google.com) |
| **Anthropic Claude** | ❌ Paid | `sk-ant-...` | [console.anthropic.com](https://console.anthropic.com) |
| **OpenAI** | ❌ Paid | `sk-...` | [platform.openai.com](https://platform.openai.com) |
| **OpenRouter** | ✅ Partly | `sk-or-...` | 200+ models, some free. [openrouter.ai](https://openrouter.ai) |
| **Ollama** (local) | ✅ Free | `ollama` | Runs on your machine, no internet |
| **LM Studio** (local) | ✅ Free | any | Runs on your machine |
| **Custom** | — | — | Any OpenAI-compatible API with custom base URL |

### 🆓 Completely Free Setup (Ollama)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download a model (pick one)
ollama pull llama3.2          # 2 GB — great quality
ollama pull llama3.2:1b       # 1 GB — faster, lightweight
ollama pull qwen2.5:7b        # 4 GB — excellent quality
```

Then in CLI Assistant settings:
- Provider: `OpenAI Compatible`
- Base URL: `http://localhost:11434/v1`
- API Key: `ollama`
- Model: `llama3.2`

---

## ⌨️ Commands

Type these in the chat input (start with `/`):

| Command | Description |
|---|---|
| `/help` | Show all available commands |
| `/settings` | Open full settings panel |
| `/provider <name>` | Switch AI provider |
| `/model <name>` | Switch model |
| `/theme <name>` | Change UI theme (`dark`, `light`, `cyberpunk`, `nord`...) |
| `/apikey` | Update API key securely |
| `/baseurl <url>` | Change base URL (for Ollama, OpenRouter, etc.) |
| `/cd <path>` | Change working directory |
| `/ls` | List current directory |
| `/sudo` | Request sudo for the session |
| `/clear` | Clear chat history |
| `/export <path>` | Export history to JSON or Markdown |

### Keyboard Shortcuts (TUI version)

| Key | Action |
|---|---|
| `Enter` | Send message |
| `Ctrl+S` | Settings |
| `Ctrl+L` | Clear chat |
| `Ctrl+H` | Help |
| `Ctrl+C` | Exit |

---

## 🔒 Safety & Security

CLI Assistant is built with safety in mind:

- **Confirmation prompts** before any delete, overwrite, or sudo operation
- **Protected paths** — `/etc/passwd`, `/etc/shadow`, `/boot`, `/dev` are read-only by default
- **API keys** stored in system keyring (GNOME Keyring / KWallet) — never in plaintext
- **Sudo password** lives only in process memory, auto-cleared after 15 minutes
- **Blocked commands** — `rm -rf /`, fork bombs, and similar are rejected
- **File size limit** — won't read files over 50 MB by default

You can customize all safety settings in `/settings`.

---

## 🏗️ Project Structure

```
CLI-Assistant/
├── install.sh              # Installer for source installation
├── run.sh                  # Quick launch after install
├── requirements.txt        # Python dependencies (TUI)
├── requirements-gui.txt    # Python dependencies (GUI)
├── build_deb.sh            # .deb package builder
├── config/
│   └── default_config.json
└── src/
    ├── main.py             # TUI entry point
    ├── gui_app.py          # GUI entry point
    ├── gui_web/            # HTML/CSS/JS for GUI
    ├── ai/                 # AI provider implementations
    │   ├── anthropic_provider.py
    │   ├── gemini_provider.py
    │   ├── openai_provider.py
    │   └── provider_factory.py
    ├── tools/              # System tools (14 categories)
    │   ├── file_manager.py
    │   ├── package_manager.py
    │   ├── process_manager.py
    │   ├── git_tool.py
    │   ├── service_manager.py
    │   └── ...
    ├── core/
    │   ├── assistant.py
    │   └── tool_executor.py
    └── settings/
        └── config_manager.py
```

---

## 📋 Requirements

| | Minimum | Recommended |
|---|---|---|
| **OS** | Debian 11 / Ubuntu 20.04 | Ubuntu 22.04+ / Debian 12 |
| **Python** | 3.10 | 3.12 |
| **RAM** | 512 MB | 1 GB+ |
| **Architecture** | amd64 | amd64 |

> ⚠️ **Linux only.** CLI Assistant is built exclusively for Debian-based Linux distributions.  
> Windows and macOS are not supported.

---

## 🤝 Contributing

Contributions are welcome! Ideas for contribution:

- 🌍 New interface languages
- 🎨 New UI themes
- 🔌 New AI provider integrations
- 🛠️ New system tools
- 🐛 Bug fixes

```bash
git clone https://github.com/sterchiks/CLI-Assistant.git
cd CLI-Assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

---

## 📄 License

**MIT License** — free to use, modify, and distribute.  
See [LICENSE](LICENSE) for details.

---

<div align="center">

**Made for Linux users — from beginners to power users**

*If CLI Assistant saved you time, consider giving it a ⭐*

**[GitHub](https://github.com/sterchiks/CLI-Assistant)** · **[Report a Bug](https://github.com/sterchiks/CLI-Assistant/issues)** · **[Request a Feature](https://github.com/sterchiks/CLI-Assistant/issues)**

</div>
