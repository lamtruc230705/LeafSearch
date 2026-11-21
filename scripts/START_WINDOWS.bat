@echo off
REM Chay FastAPI + frontend tren Windows; khong tu tao du lieu anh mau.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m uvicorn backend.main:app --reload
) else (
  python -m uvicorn backend.main:app --reload
)
pause
