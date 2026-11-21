@echo off
REM Keo tha ZIP anh vao file BAT nay; khong phai su dung lenh cmd phuc tap.
cd /d "%~dp0.."
set "DATASET=%~1"
if "%DATASET%"=="" (
  echo Nhap duong dan file ZIP (co the paste duong dan, khong co dau ngoac kep):
  set /p DATASET=
)
if "%DATASET%"=="" (
  echo Khong co file ZIP. Dung lai.
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m backend.tools.import_dataset --source "%DATASET%"
) else (
  python -m backend.tools.import_dataset --source "%DATASET%"
)
echo.
echo Da ket thuc lenh nhap anh. Xem ket qua phia tren.
pause
