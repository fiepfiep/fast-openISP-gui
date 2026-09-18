# Build dist\fast-openISP.exe and smoke-test it.
# Usage (from the repository root):  .\scripts\build_exe.ps1
# Native tools write progress to stderr; rely on exit codes instead of "Stop"
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "==> Syncing environment"
uv sync
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

Write-Host "==> Building with PyInstaller"
uv run pyinstaller fast_openisp.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path (Get-Location) "dist\fast-openISP.exe"
if (-not (Test-Path $exe)) { throw "Expected $exe" }

Write-Host "==> Self-test"
# A windowed exe does not block the console, so wait for the process explicitly
$process = Start-Process -FilePath $exe -ArgumentList "--self-test" -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Self-test failed with exit code $($process.ExitCode)" }

$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "==> OK: $exe ($sizeMb MB)"
