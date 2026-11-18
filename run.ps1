# ==============================================================================
# FraudGuard – Quick Launch Script (PowerShell)
# ==============================================================================
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "   FraudGuard – Global Online Payment Fraud Detection System" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

$pythonCandidates = @(
    "C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe",
    "python",
    "py"
)

$pythonExe = $null
foreach ($cand in $pythonCandidates) {
    if (Test-Path $cand) {
        $pythonExe = $cand
        break
    } else {
        $cmd = Get-Command $cand -ErrorAction SilentlyContinue
        if ($cmd) {
            $pythonExe = $cand
            break
        }
    }
}

if (-not $pythonExe) {
    Write-Host "[!] Could not locate Python executable." -ForegroundColor Red
    exit 1
}

Write-Host "[✓] Located Python: $pythonExe" -ForegroundColor Green
Write-Host "[✓] Starting FraudGuard Security Operations Server on http://127.0.0.1:5000" -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5000"

& $pythonExe app.py

