# Script to run all automated tests
Write-Host "Running Backend Pytest Suite..." -ForegroundColor Cyan
Set-Location -Path "$PSScriptRoot\..\backend"
& ".\.venv\Scripts\python.exe" -m pytest -v

