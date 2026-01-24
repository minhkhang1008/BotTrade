<# Simple script to start frontend (Vite) inside bottrade-ui #>
Set-StrictMode -Version Latest
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location "$root\bottrade-ui"

npm install
npm run dev

Pop-Location
