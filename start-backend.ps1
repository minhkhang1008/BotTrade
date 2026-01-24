<# Simple script to start backend in mock mode (assumes conda or venv is prepared) #>
Set-StrictMode -Version Latest
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root

if (Get-Command conda -ErrorAction SilentlyContinue) {
  conda activate bottrade
} elseif (Test-Path ".venv") {
  . .\.venv\Scripts\Activate.ps1
}

python -m src.main --mock

Pop-Location
