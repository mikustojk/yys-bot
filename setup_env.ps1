$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$requirements = Join-Path $root "requirements.txt"

if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not installed or not in PATH. Install uv first, then run this script again."
}

if (!(Test-Path -LiteralPath $requirements)) {
    throw "Missing requirements.txt: $requirements"
}

Set-Location -LiteralPath $root

if (!(Test-Path -LiteralPath $venvPython)) {
    uv venv .venv --python 3.13
}

uv pip install --python $venvPython -r $requirements

Write-Host "Environment ready: $venvPython"
Write-Host "The launcher will use this virtual environment automatically."
