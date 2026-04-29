#!/usr/bin/env bash
# CLI Assistant — скрипт установки для Linux
set -euo pipefail

# ─── Цвета ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[OK]${RESET}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
error()   { echo -e "${RED}[ERR]${RESET}  $*" >&2; }
die()     { error "$*"; exit 1; }

# ─── Переменные ───────────────────────────────────────────────────────────────
INSTALL_DIR="$HOME/.cli-assistant"
VENV_DIR="$INSTALL_DIR/venv"
SRC_DIR="$INSTALL_DIR/src"
BIN_PATH="/usr/local/bin/cli-assistant"
ALT_BIN_PATH="$HOME/.local/bin/cli-assistant"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Флаги ────────────────────────────────────────────────────────────────────
UNINSTALL=false
UPDATE=false
RESET_CONFIG=false

for arg in "$@"; do
  case "$arg" in
    --uninstall)    UNINSTALL=true ;;
    --update)       UPDATE=true ;;
    --reset-config) RESET_CONFIG=true ;;
    --help|-h)
      echo "Использование: $0 [--uninstall] [--update] [--reset-config]"
      exit 0 ;;
  esac
done

# ─── Удаление ─────────────────────────────────────────────────────────────────
if $UNINSTALL; then
  info "Удаление CLI Assistant..."
  rm -rf "$INSTALL_DIR"
  rm -f "$BIN_PATH" "$ALT_BIN_PATH"
  success "CLI Assistant удалён."
  exit 0
fi

# ─── Сброс конфига ────────────────────────────────────────────────────────────
if $RESET_CONFIG; then
  info "Сброс конфигурации..."
  rm -f "$INSTALL_DIR/config.json"
  success "Конфигурация сброшена. При следующем запуске откроется мастер настройки."
  exit 0
fi

echo -e "${BOLD}${CYAN}"
echo "  ██████╗██╗     ██╗      █████╗ ███████╗███████╗██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗"
echo "  ██╔════╝██║     ██║     ██╔══██╗██╔════╝██╔════╝██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝"
echo "  ██║     ██║     ██║     ███████║███████╗███████╗██║███████╗   ██║   ███████║██╔██╗ ██║   ██║   "
echo "  ██║     ██║     ██║     ██╔══██║╚════██║╚════██║██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║   "
echo "  ╚██████╗███████╗██║     ██║  ██║███████║███████║██║███████║   ██║   ██║  ██║██║ ╚████║   ██║   "
echo "   ╚═════╝╚══════╝╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   "
echo -e "${RESET}"
echo -e "${BOLD}  AI-ассистент для терминала v1.0.0${RESET}"
echo ""

# ─── Проверка Python ──────────────────────────────────────────────────────────
info "Проверка Python 3.10+..."
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    MAJOR=$(echo "$VER" | cut -d. -f1)
    MINOR=$(echo "$VER" | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
      PYTHON="$cmd"
      success "Найден Python $VER ($cmd)"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  error "Python 3.10+ не найден!"
  echo ""
  echo "Установите Python:"
  echo "  Ubuntu/Debian: sudo apt install python3.11"
  exit 1
fi

# ─── Создание директорий ──────────────────────────────────────────────────────
info "Создание директорий..."
mkdir -p "$INSTALL_DIR"/{logs,config}
success "Директория: $INSTALL_DIR"

# ─── Виртуальное окружение ────────────────────────────────────────────────────
if $UPDATE && [ -d "$VENV_DIR" ]; then
  info "Обновление зависимостей..."
else
  info "Создание виртуального окружения..."
  "$PYTHON" -m venv "$VENV_DIR"
  success "Venv создан: $VENV_DIR"
fi

# ─── Установка зависимостей ───────────────────────────────────────────────────
info "Установка зависимостей..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
success "Зависимости установлены"

# ─── Копирование файлов ───────────────────────────────────────────────────────
info "Копирование файлов проекта..."
mkdir -p "$SRC_DIR"
cp -r "$SCRIPT_DIR/src/"* "$SRC_DIR/"
cp -r "$SCRIPT_DIR/config/"* "$INSTALL_DIR/config/" 2>/dev/null || true
success "Файлы скопированы в $SRC_DIR"

# ─── Создание исполняемого файла ──────────────────────────────────────────────
LAUNCHER_CONTENT="#!/usr/bin/env bash
# CLI Assistant launcher
source \"$VENV_DIR/bin/activate\"
exec python \"$SRC_DIR/main.py\" \"\$@\"
"

# Пробуем /usr/local/bin, иначе ~/.local/bin
if [ -w "/usr/local/bin" ] || sudo -n true 2>/dev/null; then
  info "Установка в /usr/local/bin/cli-assistant..."
  echo "$LAUNCHER_CONTENT" | sudo tee "$BIN_PATH" > /dev/null
  sudo chmod +x "$BIN_PATH"
  INSTALLED_BIN="$BIN_PATH"
else
  info "Установка в ~/.local/bin/cli-assistant..."
  mkdir -p "$HOME/.local/bin"
  echo "$LAUNCHER_CONTENT" > "$ALT_BIN_PATH"
  chmod +x "$ALT_BIN_PATH"
  INSTALLED_BIN="$ALT_BIN_PATH"
fi
success "Исполняемый файл: $INSTALLED_BIN"

# ─── Алиас ────────────────────────────────────────────────────────────────────
ALIAS_LINE="alias ai='cli-assistant'"
SHELL_RC=""
if [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "${SHELL:-}")" = "zsh" ]; then
  SHELL_RC="$HOME/.zshrc"
elif [ -n "${BASH_VERSION:-}" ] || [ "$(basename "${SHELL:-}")" = "bash" ]; then
  SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
  echo ""
  read -r -p "Добавить алиас 'ai' в $SHELL_RC? [Y/n]: " REPLY
  REPLY="${REPLY:-Y}"
  if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    if ! grep -q "$ALIAS_LINE" "$SHELL_RC" 2>/dev/null; then
      echo "" >> "$SHELL_RC"
      echo "# CLI Assistant" >> "$SHELL_RC"
      echo "$ALIAS_LINE" >> "$SHELL_RC"
      success "Алиас добавлен в $SHELL_RC"
      warn "Выполните: source $SHELL_RC"
    else
      info "Алиас уже существует в $SHELL_RC"
    fi
  fi
fi

# ─── Готово ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✅ Установка завершена!${RESET}"
echo ""
echo "Запуск:"
echo -e "  ${CYAN}cli-assistant${RESET}          — запустить ассистент"
echo -e "  ${CYAN}cli-assistant --setup${RESET}  — повторная настройка"
echo -e "  ${CYAN}ai${RESET}                     — короткий алиас (после source)"
echo ""

# Запускаем Setup Wizard при первой установке
if ! $UPDATE; then
  read -r -p "Запустить мастер настройки сейчас? [Y/n]: " REPLY
  REPLY="${REPLY:-Y}"
  if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    "$INSTALLED_BIN" --setup
  fi
fi
