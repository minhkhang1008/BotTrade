<#
.SYNOPSIS
  Start both backend (FastAPI) and frontend (Vite) for local development.

USAGE
  Run from repository root (BotTrade):
    ./start-dev.ps1

DESCRIPTION
  - If conda is available, this script will create/activate a conda env named 'bottrade',
    install numpy/pandas via conda-forge and then pip install the remaining requirements.
  - If conda is not available, it will create a Python venv at .venv and attempt to pip install
    dependencies (may fail on Windows without build tools). In that case, install Miniconda
    or Visual Studio Build Tools as recommended in README_RUN_LOCAL.md.

  This script will then launch the backend (mock mode) in a separate PowerShell window
  and launch the frontend (Vite) in another window.

SECURITY
  Do NOT store secrets (passwords, account numbers) in client env (VITE_*) variables.
  Put server-side secrets in `BotTrade/.env` (not committed). See README_RUN_LOCAL.md.
#>

Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Repo root: $root"

function Has-Command($name) {
  return (Get-Command $name -ErrorAction SilentlyContinue) -ne $null
}

Push-Location $root

if (Has-Command conda) {
  Write-Host "Conda detected. Using conda to create environment 'bottrade'."

  # Create env if it doesn't exist
  $envs = conda env list --json | ConvertFrom-Json
  $exists = $false
  if ($envs.envs) {
    foreach ($e in $envs.envs) { if ($e -like "*\\envs\\bottrade") { $exists = $true } }
  }

  if (-not $exists) {
    Write-Host "Creating conda env 'bottrade' (python 3.11)..."
    conda create -n bottrade python=3.11 -y
  }

  Write-Host "Activating 'bottrade' and installing dependencies..."
  conda activate bottrade
  conda install -c conda-forge numpy pandas -y
  pip install -r requirements.txt

  # Start backend in new window
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root'; conda activate bottrade; python -m src.main --mock"

  # Start frontend in new window
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\bottrade-ui'; npm install; npm run dev"

} else {
  Write-Host "Conda not found. Falling back to venv (may fail for heavy packages on Windows)."

  if (-not (Test-Path "$root\.venv")) {
    Write-Host "Creating venv at $root\.venv ..."
    python -m venv .venv
  }

  Write-Host "Activating venv and installing lightweight dependencies (pip install may fail without build tools)."
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt || Write-Warning "pip install failed. Consider installing Miniconda or Visual Studio Build Tools."

  Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root'; . .\.venv\Scripts\Activate.ps1; python -m src.main --mock"
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\bottrade-ui'; npm install; npm run dev"
}

Pop-Location

Write-Host "Started backend and frontend (check their windows). If frontend does not show UI, open browser to http://localhost:5173 (or printed port)."
