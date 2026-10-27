param([switch]$Install,[int]$Port=8010)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$officePython = if (Test-Path '.venv/Scripts/python.exe') { (Resolve-Path '.venv/Scripts/python.exe').Path } else { 'py' }
if ($Install) {
    & $officePython -m pip install -r apps/api/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    Push-Location apps/web
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
$env:NATEE_PORT=[string]$Port
Write-Host "Natee's Software House: http://127.0.0.1:$Port"
& $officePython run.py
