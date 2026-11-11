# Safe startup script for EduVerse Backend (does not require weakening execution policies)
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path "$repoRoot\backend"
& "$repoRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
