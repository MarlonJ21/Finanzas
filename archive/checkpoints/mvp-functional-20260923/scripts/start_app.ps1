$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "app\backend"
$frontend = Join-Path $root "app\frontend"

Start-Process pwsh -WindowStyle Hidden -WorkingDirectory $backend -ArgumentList "-NoExit", "-Command", "uv sync; uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process pwsh -WindowStyle Hidden -WorkingDirectory $frontend -ArgumentList "-NoExit", "-Command", "npm install; npm run dev"

Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Frontend: http://127.0.0.1:3000"
