LEAFSEARCH PTIT - DU AN WEB TIM KIEM ANH LA CAY - V1.1
==================================================
DA TICH HOP TOAN BO 1.685 ANH THUC TE VAO data/images/.
DA CO SQLite that: data/leafsearch.sqlite (6.740 vectors).
KHONG CAN NHAP ZIP ANH LAI NEU CHI MUON CHAY WEB.

WINDOWS - CACH CHAY DE NHAT:
  1. Cai Python 3.11, 3.12 hoac 3.13.
  2. Mo file scripts/INSTALL_AND_RUN_WINDOWS.bat.
  3. Khi server chay, mo http://127.0.0.1:8000

HOAC COMMAND PROMPT / POWERSHELL (tai thu muc goc):
  py -3 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  .venv\Scripts\python.exe -m uvicorn backend.main:app --reload

FILE NEN DOC:
  README.md - Huong dan du an
  docs/FILE_GUIDE.md - Cong dung tung file
  docs/ARCHITECTURE.md - Cach hoat dong FE/BE/SQLite
  docs/REAL_DATASET_REPORT.md - Ket qua 1.685 anh that
  docs/STUDY_PLAN.md - Lo trinh tu hoc

LUU Y: Accuracy tren test la ket qua dataset hien tai; can duyet
       cac cap anh nghi gan trung truoc khi cong bo la do doc lap.
