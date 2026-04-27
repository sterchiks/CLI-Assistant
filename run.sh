#!/usr/bin/env bash
# Быстрый запуск CLI Assistant из директории проекта (без установки)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.cli-assistant/venv"

# Если venv не существует — запускаем установку
if [ ! -d "$VENV_DIR" ]; then
  echo "Виртуальное окружение не найдено. Запускаю установку..."
  bash "$SCRIPT_DIR/install.sh"
  exit 0
fi

source "$VENV_DIR/bin/activate"
exec python "$SCRIPT_DIR/src/main.py" "$@"
