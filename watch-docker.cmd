@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Запускаю dndsheet з автоперезбіркою: після змін у frontend, backend/src чи перекладах
echo контейнер перезбереться й перезапуститься сам. Сайт: http://127.0.0.1:8000
echo Щоб зупинити стеження — закрийте це вікно або натисніть Ctrl+C (контейнер лишиться працювати).
echo.
docker compose up -d --build
if errorlevel 1 (
  echo ПОМИЛКА: перша збірка не вдалася. Скопіюйте текст вище й надішліть Claude.
  pause
  exit /b 1
)
docker compose watch
pause
