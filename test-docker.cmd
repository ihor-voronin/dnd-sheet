@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Запускаю тести й DDD-гейти в Docker-образі (там є корпус і WeasyPrint)...
docker compose --profile test run --rm --build test
if errorlevel 1 (
  echo.
  echo ТЕСТИ НЕ ПРОЙШЛИ. Скопіюйте текст вище й надішліть Claude.
) else (
  echo.
  echo Усі тести пройшли.
)
pause
