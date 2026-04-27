"""Темы оформления для Textual TUI."""

THEMES: dict[str, str] = {}

THEMES["dark"] = """
$bg: #1a1a2e;
$bg-panel: #16213e;
$bg-input: #0f3460;
$accent: #0f3460;
$accent-light: #533483;
$text: #e0e0e0;
$text-muted: #888888;
$user-bubble: #0f3460;
$assistant-bubble: #1e3a2f;
$success: #4caf50;
$warning: #ff9800;
$error: #f44336;
$tool-bg: #1a2744;
$border: #2a2a4a;

Screen {
    background: $bg;
    color: $text;
}

Header {
    background: $bg-panel;
    color: $text;
    border-bottom: solid $border;
}

Footer {
    background: $bg-panel;
    color: $text-muted;
    border-top: solid $border;
}

#chat-area {
    background: $bg;
    border: none;
}

#sidebar {
    background: $bg-panel;
    border-left: solid $border;
    color: $text;
    width: 22;
}

#input-area {
    background: $bg-input;
    border-top: solid $border;
    height: 3;
}

#message-input {
    background: $bg-input;
    color: $text;
    border: none;
}

.user-bubble {
    background: $user-bubble;
    color: $text;
    border: round #3a5a8a;
    margin: 1 2;
    padding: 1 2;
    max-width: 70%;
    align-horizontal: right;
}

.assistant-bubble {
    background: $assistant-bubble;
    color: $text;
    border: round #2a5a3a;
    margin: 1 2;
    padding: 1 2;
    max-width: 80%;
}

.tool-call {
    background: $tool-bg;
    color: #88aaff;
    border: solid #3a4a7a;
    margin: 0 2;
    padding: 0 1;
}

.error-message {
    color: $error;
    background: #3a1a1a;
    border: solid $error;
    margin: 1 2;
    padding: 1;
}

.system-info-label {
    color: $text-muted;
}

.system-info-value {
    color: $accent-light;
}

Button {
    background: $accent;
    color: $text;
    border: none;
}

Button:hover {
    background: $accent-light;
}

Button.-primary {
    background: #0f7a3a;
}
"""

THEMES["light"] = """
$bg: #f5f5f5;
$bg-panel: #e8e8e8;
$bg-input: #ffffff;
$accent: #1565c0;
$accent-light: #1976d2;
$text: #212121;
$text-muted: #757575;
$user-bubble: #bbdefb;
$assistant-bubble: #e8f5e9;
$success: #388e3c;
$warning: #f57c00;
$error: #d32f2f;
$tool-bg: #e3f2fd;
$border: #bdbdbd;

Screen {
    background: $bg;
    color: $text;
}

Header {
    background: $accent;
    color: #ffffff;
}

Footer {
    background: $bg-panel;
    color: $text-muted;
    border-top: solid $border;
}

#chat-area {
    background: $bg;
}

#sidebar {
    background: $bg-panel;
    border-left: solid $border;
    color: $text;
    width: 22;
}

#input-area {
    background: $bg-input;
    border-top: solid $border;
    height: 3;
}

#message-input {
    background: $bg-input;
    color: $text;
    border: none;
}

.user-bubble {
    background: $user-bubble;
    color: $text;
    border: round $accent;
    margin: 1 2;
    padding: 1 2;
    max-width: 70%;
}

.assistant-bubble {
    background: $assistant-bubble;
    color: $text;
    border: round $success;
    margin: 1 2;
    padding: 1 2;
    max-width: 80%;
}

.tool-call {
    background: $tool-bg;
    color: $accent;
    border: solid $accent-light;
    margin: 0 2;
    padding: 0 1;
}

.error-message {
    color: $error;
    background: #ffebee;
    border: solid $error;
    margin: 1 2;
    padding: 1;
}

Button {
    background: $accent;
    color: #ffffff;
}

Button:hover {
    background: $accent-light;
}
"""

THEMES["cyberpunk"] = """
$bg: #000000;
$bg-panel: #0a0a0a;
$bg-input: #0d0d1a;
$accent: #00ff41;
$accent-pink: #ff00ff;
$text: #00ff41;
$text-muted: #005500;
$user-bubble: #001a00;
$assistant-bubble: #1a001a;
$success: #00ff41;
$warning: #ffff00;
$error: #ff0000;
$tool-bg: #001a1a;
$border: #00ff41;

Screen {
    background: $bg;
    color: $text;
}

Header {
    background: $bg-panel;
    color: $accent;
    border-bottom: solid $accent;
    text-style: bold;
}

Footer {
    background: $bg-panel;
    color: $text-muted;
    border-top: solid $accent;
}

#chat-area {
    background: $bg;
}

#sidebar {
    background: $bg-panel;
    border-left: solid $accent;
    color: $text;
    width: 22;
}

#input-area {
    background: $bg-input;
    border-top: solid $accent;
    height: 3;
}

#message-input {
    background: $bg-input;
    color: $accent;
    border: none;
}

.user-bubble {
    background: $user-bubble;
    color: $accent;
    border: round $accent;
    margin: 1 2;
    padding: 1 2;
    max-width: 70%;
    text-style: bold;
}

.assistant-bubble {
    background: $assistant-bubble;
    color: $accent-pink;
    border: round $accent-pink;
    margin: 1 2;
    padding: 1 2;
    max-width: 80%;
}

.tool-call {
    background: $tool-bg;
    color: #00ffff;
    border: solid #00ffff;
    margin: 0 2;
    padding: 0 1;
}

.error-message {
    color: $error;
    background: #1a0000;
    border: solid $error;
    margin: 1 2;
    padding: 1;
    text-style: bold;
}

Button {
    background: $bg-panel;
    color: $accent;
    border: solid $accent;
    text-style: bold;
}

Button:hover {
    background: $accent;
    color: $bg;
}
"""

THEMES["nord"] = """
$bg: #2e3440;
$bg-panel: #3b4252;
$bg-input: #434c5e;
$accent: #88c0d0;
$accent2: #81a1c1;
$text: #eceff4;
$text-muted: #d8dee9;
$user-bubble: #3b4252;
$assistant-bubble: #2e3440;
$success: #a3be8c;
$warning: #ebcb8b;
$error: #bf616a;
$tool-bg: #434c5e;
$border: #4c566a;

Screen {
    background: $bg;
    color: $text;
}

Header {
    background: $bg-panel;
    color: $accent;
    border-bottom: solid $border;
}

Footer {
    background: $bg-panel;
    color: $text-muted;
    border-top: solid $border;
}

#chat-area {
    background: $bg;
}

#sidebar {
    background: $bg-panel;
    border-left: solid $border;
    color: $text;
    width: 22;
}

#input-area {
    background: $bg-input;
    border-top: solid $border;
    height: 3;
}

#message-input {
    background: $bg-input;
    color: $text;
    border: none;
}

.user-bubble {
    background: $user-bubble;
    color: $text;
    border: round $accent2;
    margin: 1 2;
    padding: 1 2;
    max-width: 70%;
}

.assistant-bubble {
    background: $assistant-bubble;
    color: $text;
    border: round $accent;
    margin: 1 2;
    padding: 1 2;
    max-width: 80%;
}

.tool-call {
    background: $tool-bg;
    color: $accent;
    border: solid $accent2;
    margin: 0 2;
    padding: 0 1;
}

.error-message {
    color: $error;
    background: #3b2a2a;
    border: solid $error;
    margin: 1 2;
    padding: 1;
}

Button {
    background: $accent2;
    color: $bg;
}

Button:hover {
    background: $accent;
}
"""

THEMES["solarized"] = """
$bg: #002b36;
$bg-panel: #073642;
$bg-input: #073642;
$accent: #268bd2;
$accent2: #2aa198;
$text: #839496;
$text-bright: #93a1a1;
$user-bubble: #073642;
$assistant-bubble: #002b36;
$success: #859900;
$warning: #b58900;
$error: #dc322f;
$tool-bg: #073642;
$border: #586e75;

Screen {
    background: $bg;
    color: $text;
}

Header {
    background: $bg-panel;
    color: $accent;
    border-bottom: solid $border;
}

Footer {
    background: $bg-panel;
    color: $text;
    border-top: solid $border;
}

#chat-area {
    background: $bg;
}

#sidebar {
    background: $bg-panel;
    border-left: solid $border;
    color: $text;
    width: 22;
}

#input-area {
    background: $bg-input;
    border-top: solid $border;
    height: 3;
}

#message-input {
    background: $bg-input;
    color: $text-bright;
    border: none;
}

.user-bubble {
    background: $user-bubble;
    color: $text-bright;
    border: round $accent;
    margin: 1 2;
    padding: 1 2;
    max-width: 70%;
}

.assistant-bubble {
    background: $assistant-bubble;
    color: $text-bright;
    border: round $accent2;
    margin: 1 2;
    padding: 1 2;
    max-width: 80%;
}

.tool-call {
    background: $tool-bg;
    color: $accent2;
    border: solid $accent;
    margin: 0 2;
    padding: 0 1;
}

.error-message {
    color: $error;
    background: #1a0a0a;
    border: solid $error;
    margin: 1 2;
    padding: 1;
}

Button {
    background: $accent;
    color: $bg;
}

Button:hover {
    background: $accent2;
}
"""


def get_theme(name: str) -> str:
    """Возвращает CSS строку темы по имени. Fallback на dark."""
    return THEMES.get(name, THEMES["dark"])


def get_theme_names() -> list[str]:
    """Возвращает список доступных тем."""
    return list(THEMES.keys())
