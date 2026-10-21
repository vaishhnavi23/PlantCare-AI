# Windows PowerShell: start the API (and the built frontend, if frontend\dist exists) on http://127.0.0.1:8000
Set-Location "$PSScriptRoot\..\backend"
if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --port 8000
