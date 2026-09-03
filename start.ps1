$ErrorActionPreference = "Stop"

Write-Host "Activăm mediul virtual..." -ForegroundColor Cyan
if (Test-Path ".venv\Scripts\Activate.ps1") {
    . ".venv\Scripts\Activate.ps1"
} else {
    Write-Warning "Mediul virtual (.venv) nu a fost găsit. Va încerca să ruleze folosind Python-ul global."
}

Write-Host "Pornim API-ul într-o fereastră separată..." -ForegroundColor Cyan
# Folosim Start-Process pentru a deschide API-ul în altă fereastră, astfel încât să poți vedea logurile separat.
$apiCommand = "& { if (Test-Path '.venv\Scripts\Activate.ps1') { . '.venv\Scripts\Activate.ps1' }; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 }"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCommand

Write-Host "Așteptăm 3 secunde pentru pornirea API-ului..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host "Generăm token-ul de acces pentru UI..." -ForegroundColor Cyan
$token = python -m app.core.dev_token --subject synthetic-demo-user --minutes 120

if (-not $token) {
    Write-Error "Nu s-a putut genera token-ul de acces."
    exit 1
}

Write-Host "Setăm variabilele de mediu pentru interfață..." -ForegroundColor Cyan
$env:CHIATRATON_API_BASE_URL = "http://127.0.0.1:8000"
$env:CHIATRATON_UI_BEARER_TOKEN = $token

Write-Host "Pornim Interfața NiceGUI..." -ForegroundColor Green
python -m Interface.main
