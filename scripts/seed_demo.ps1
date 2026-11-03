# Script to seed database with realistic demo data
Set-Location -Path "$PSScriptRoot\..\backend"
& ".\.venv\Scripts\python.exe" -m app.utils.seed_data

