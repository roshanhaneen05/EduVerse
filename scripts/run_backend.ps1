# Safe startup script for EduVerse Backend (does not require weakening execution policies)
Set-Location -Path "$PSScriptRoot\..\backend"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

