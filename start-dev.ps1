$ErrorActionPreference = "Stop"

Write-Host "=== Automatizare pornire mediu dezvoltare ChIAtraton ===" -ForegroundColor Cyan


# 1. Python + mediu virtual
Write-Host "`n[1] Configurare mediu virtual..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    Write-Host "Creare .venv..." -ForegroundColor Cyan
    python -m venv .venv
}

if (Test-Path ".venv\Scripts\Activate.ps1") {
    . ".venv\Scripts\Activate.ps1"
    Write-Host "Mediul virtual a fost activat." -ForegroundColor Green
} else {
    Write-Error "Eroare: Nu s-a putut găsi scriptul de activare .venv."
    exit 1
}

# 2. Instalare dependente
Write-Host "`n[2] Instalare dependențe..." -ForegroundColor Yellow
python -m pip install -e ".[test,ui]"

# 3. Configurare .env
Write-Host "`n[3] Configurare .env..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item .env.example .env
        Write-Host "Fișierul .env a fost creat din .env.example." -ForegroundColor Green
    } else {
        Write-Warning "Fișierul .env.example lipsește!"
    }
}

if (Test-Path ".env") {
    $envContent = Get-Content -Path .env -Raw
    $envContent = $envContent -replace '(?m)^CHIATRATON_JWT_SECRET=.*', 'CHIATRATON_JWT_SECRET="andrei-local-dev-secret"'
    $envContent = $envContent -replace '(?m)^CHIATRATON_CRITERION_EXTRACTOR_BACKEND=.*', 'CHIATRATON_CRITERION_EXTRACTOR_BACKEND="fake"'
    $envContent = $envContent -replace '(?m)^CHIATRATON_REPORT_ANALYZER_BACKEND=.*', 'CHIATRATON_REPORT_ANALYZER_BACKEND="fake"'
    Set-Content -Path .env -Value $envContent
    Write-Host "Variabilele din .env au fost actualizate pentru modul de dezvoltare (backend-uri setate pe fake, secret local)." -ForegroundColor Green
}

# 4. Oprire proces vechi pe port 8000
Write-Host "`n[4] Oprire procese vechi uvicorn (port 8000)..." -ForegroundColor Yellow
$processes = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
if ($processes) {
    foreach ($process in $processes) {
        Write-Host "Oprire proces cu PID $process care ocupă portul 8000..." -ForegroundColor Cyan
        Stop-Process -Id $process -Force -ErrorAction SilentlyContinue
    }
}

# 5. Pornire API
Write-Host "`n[5] Pornire API (în fereastră separată)..." -ForegroundColor Yellow
$apiCommand = "& { if (Test-Path '.venv\Scripts\Activate.ps1') { . '.venv\Scripts\Activate.ps1' }; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 }"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCommand

Write-Host "Așteptăm 5 secunde pentru pornirea API-ului..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

$health = try { Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -ErrorAction Stop } catch { $null }
if (-not $health -or $health.status -ne "ok") {
    Write-Warning "API-ul nu a răspuns corect la /health. Este posibil să nu fi pornit corect. Verifică fereastra separată."
} else {
    Write-Host "API-ul rulează cu succes!" -ForegroundColor Green
}

# 6. Generare token
Write-Host "`n[6] Generare token de dezvoltare..." -ForegroundColor Yellow
$token = python -m app.core.dev_token --subject andrei-dev --minutes 120

if (-not $token) {
    Write-Error "Nu s-a putut genera token-ul de acces."
    exit 1
}
Write-Host "Token generat cu succes." -ForegroundColor Green

# 7. Pornire UI
Write-Host "`n[7] Setare mediu și pornire UI..." -ForegroundColor Yellow
$env:CHIATRATON_API_BASE_URL = "http://127.0.0.1:8000"
$env:CHIATRATON_UI_BEARER_TOKEN = $token

Write-Host "Pornim interfața în fereastra curentă (va fi disponibilă la http://127.0.0.1:8081)..." -ForegroundColor Green
python -m Interface.main
