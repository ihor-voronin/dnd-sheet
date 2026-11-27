@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Перезбираю образ dndsheet і перезапускаю контейнер...
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo ПОМИЛКА: збірка не вдалася. Скопіюйте текст вище й надішліть Claude.
) else (
  echo.
  docker compose ps
  echo Готово: http://127.0.0.1:8000
)
pause
