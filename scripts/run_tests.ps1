Set-Location "$PSScriptRoot\..\backend"
. .\.venv\Scripts\Activate.ps1
python -m pytest tests -q
