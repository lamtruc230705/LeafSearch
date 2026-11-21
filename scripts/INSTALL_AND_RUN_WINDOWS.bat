@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
echo ===============================================
echo LEAFSEARCH PTIT - SETUP VA KHOI DONG WEBSITE
echo ===============================================
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Tao Python virtual environment ...
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 goto failed
)
echo [2/3] Cai cac thu vien phu thuoc ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo [3/3] Bat dau FastAPI ...
echo Website: http://127.0.0.1:8000
echo Swagger: http://127.0.0.1:8000/docs
echo Muon dung server: bam Ctrl+C.
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo Co loi xay ra. Hay doc README.md va mo CMD de xem thong bao loi.
pause
exit /b 1
