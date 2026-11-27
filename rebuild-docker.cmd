@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Rebuilding the dndsheet image and restarting the container...
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo ERROR: the build failed. See the output above.
) else (
  echo.
  docker compose ps
  echo Done: http://127.0.0.1:8000
)
pause
