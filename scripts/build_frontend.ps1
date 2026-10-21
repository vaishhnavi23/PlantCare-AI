# Windows PowerShell: build the UI once so the backend serves everything on http://127.0.0.1:8000
Set-Location "$PSScriptRoot\..\frontend"
npm install
npm run build
