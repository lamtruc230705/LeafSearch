@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
echo == KIEM TRA 14 TEST ==
"%PYTHON%" -m pytest -q
if errorlevel 1 goto failed
echo == XAC MINH TOAN BO ANH PNG, VECTOR, SQLITE ==
"%PYTHON%" -m backend.tools.verify_dataset
if errorlevel 1 goto failed
echo NGHIEM THU THANH CONG.
pause
exit /b 0
:failed
echo NGHIEM THU CHUA DAT - XEM THONG BAO.
pause
exit /b 1
