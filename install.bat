@echo off
REM CLI Assistant — скрипт установки для Windows
setlocal EnableDelayedExpansion

set INSTALL_DIR=%USERPROFILE%\.cli-assistant
set VENV_DIR=%INSTALL_DIR%\venv
set SRC_DIR=%INSTALL_DIR%\src
set SCRIPT_DIR=%~dp0

echo.
echo  ========================================
echo   CLI Assistant v1.0.0
echo   AI-ассистент для терминала
echo  ========================================
echo.

REM Обработка флагов
if "%1"=="--uninstall" goto :uninstall
if "%1"=="--reset-config" goto :reset_config
if "%1"=="--help" goto :show_help

REM Проверка Python
echo [INFO] Проверка Python 3.10+...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERR] Python не найден!
    echo.
    echo Скачайте Python 3.10+ с https://python.org/downloads/
    echo Убедитесь что добавили Python в PATH при установке.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK]   Найден Python %PYVER%

REM Создание директорий
echo [INFO] Создание директорий...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
if not exist "%INSTALL_DIR%\config" mkdir "%INSTALL_DIR%\config"
echo [OK]   Директория: %INSTALL_DIR%

REM Виртуальное окружение
echo [INFO] Создание виртуального окружения...
if not exist "%VENV_DIR%" (
    python -m venv "%VENV_DIR%"
    echo [OK]   Venv создан: %VENV_DIR%
) else (
    echo [INFO] Venv уже существует, обновляю...
)

REM Установка зависимостей
echo [INFO] Установка зависимостей...
"%VENV_DIR%\Scripts\pip.exe" install --quiet --upgrade pip
"%VENV_DIR%\Scripts\pip.exe" install --quiet -r "%SCRIPT_DIR%requirements.txt"
echo [OK]   Зависимости установлены

REM Копирование файлов
echo [INFO] Копирование файлов проекта...
if not exist "%SRC_DIR%" mkdir "%SRC_DIR%"
xcopy /E /Y /Q "%SCRIPT_DIR%src\*" "%SRC_DIR%\" >nul
if exist "%SCRIPT_DIR%config\" (
    xcopy /E /Y /Q "%SCRIPT_DIR%config\*" "%INSTALL_DIR%\config\" >nul
)
echo [OK]   Файлы скопированы в %SRC_DIR%

REM Создание bat-лаунчера
set LAUNCHER=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\cli-assistant.bat
echo @echo off > "%LAUNCHER%"
echo call "%VENV_DIR%\Scripts\activate.bat" >> "%LAUNCHER%"
echo python "%SRC_DIR%\main.py" %%* >> "%LAUNCHER%"
echo [OK]   Лаунчер создан: %LAUNCHER%

echo.
echo  ========================================
echo   Установка завершена!
echo  ========================================
echo.
echo  Запуск:
echo    cli-assistant          - запустить ассистент
echo    cli-assistant --setup  - повторная настройка
echo.

set /p RUNSETUP="Запустить мастер настройки сейчас? [Y/n]: "
if /i "!RUNSETUP!"=="" set RUNSETUP=Y
if /i "!RUNSETUP!"=="Y" (
    call "%VENV_DIR%\Scripts\activate.bat"
    python "%SRC_DIR%\main.py" --setup
)
goto :eof

:uninstall
echo [INFO] Удаление CLI Assistant...
if exist "%INSTALL_DIR%" rmdir /S /Q "%INSTALL_DIR%"
echo [OK]   CLI Assistant удалён.
goto :eof

:reset_config
echo [INFO] Сброс конфигурации...
if exist "%INSTALL_DIR%\config.json" del "%INSTALL_DIR%\config.json"
echo [OK]   Конфигурация сброшена.
goto :eof

:show_help
echo Использование: install.bat [--uninstall] [--reset-config] [--help]
goto :eof
