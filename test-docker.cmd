@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Running the tests and DDD gates in the Docker image (it has the corpus and WeasyPrint)...
docker compose --profile test run --rm --build test
if errorlevel 1 (
  echo.
  echo TESTS FAILED. See the output above.
) else (
  echo.
  echo All tests passed.
)
pause
