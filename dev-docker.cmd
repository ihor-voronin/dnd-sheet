@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Fast dev mode: Vite on http://127.0.0.1:5173 and the API with auto-reload.
echo Changes in frontend and backend/src show up in seconds, without rebuilding the image.
echo To stop: Ctrl+C in this window.
echo.
docker compose --profile dev up --build api-dev web-dev
pause
