@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting dndsheet with auto-rebuild: after changes in frontend, backend/src or translations
echo the container rebuilds and restarts by itself. Site: http://127.0.0.1:8000
echo To stop watching, close this window or press Ctrl+C (the container keeps running).
echo.
docker compose up -d --build
if errorlevel 1 (
  echo ERROR: the first build failed. See the output above.
  pause
  exit /b 1
)
docker compose watch
pause
