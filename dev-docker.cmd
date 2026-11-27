@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Швидкий режим розробки: Vite на http://127.0.0.1:5173 і API з автоперезавантаженням.
echo Зміни у frontend і backend/src видно за секунди, без перезбирання образу.
echo Зупинити — Ctrl+C у цьому вікні.
echo.
docker compose --profile dev up --build api-dev web-dev
pause
