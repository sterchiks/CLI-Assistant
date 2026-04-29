#!/usr/bin/env bash

set -e

APP_NAME="CLI_Assistant"
ENTRY="src/main.py"
VENV="venv"
DIST="dist"
APPDIR="AppDir"

echo "🚀 Starting build for $APP_NAME..."

# -------------------------
# 1. VENV
# -------------------------
if [ ! -d "$VENV" ]; then
    echo "📦 Creating venv..."
    python3 -m venv $VENV
fi

source $VENV/bin/activate

# -------------------------
# 2. DEPENDENCIES
# -------------------------
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install pyinstaller pydantic click
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# -------------------------
# 3. PYINSTALLER BUILD
# -------------------------
echo "⚙️ Building binary with PyInstaller..."

rm -rf build dist *.spec

pyinstaller --onefile --noconfirm --clean \
  --name cli-assistant \
  --paths=src \
  --hidden-import=pydantic \
  --hidden-import=click \
  --collect-all pydantic \
  src/main.py

# -------------------------
# 4. TEST BINARY
# -------------------------
echo "🧪 Testing binary..."
./dist/cli-assistant || {
    echo "❌ Binary failed to run"
    exit 1
}

# -------------------------
# 5. APPDIR
# -------------------------
echo "📦 Creating AppDir..."

rm -rf $APPDIR
mkdir -p $APPDIR/usr/bin

cp dist/cli-assistant $APPDIR/usr/bin/
chmod +x $APPDIR/usr/bin/cli-assistant

# AppRun
cat > $APPDIR/AppRun << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/cli-assistant"
EOF

chmod +x $APPDIR/AppRun

# Desktop file
cat > $APPDIR/cli-assistant.desktop << EOF
[Desktop Entry]
Name=CLI Assistant
Exec=cli-assistant
Icon=cli-assistant
Type=Application
Categories=Utility;
EOF

# -------------------------
# 6. BUILD APPIMAGE
# -------------------------
echo "📦 Building AppImage..."

ARCH=x86_64 ~/appimagetool-x86_64.AppImage $APPDIR

echo "🎉 DONE!"
echo "👉 AppImage created in current folder"
