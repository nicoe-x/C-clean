$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$buildPython = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $buildPython)) {
    & py -3.12 -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create build environment.' }
}
& $buildPython -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Failed to install build dependencies.' }
& $buildPython make_icons.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
& $buildPython -m unittest -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& $buildPython -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --icon assets/app.ico --version-file version_info.txt --add-data "assets;assets" --name Clearspace cleaner.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
Copy-Item -LiteralPath '.\dist\Clearspace.exe' -Destination '.\dist\AI-Cache-Cleaner.exe' -Force
Copy-Item -LiteralPath '.\dist\Clearspace.exe' -Destination '.\dist\Clearspace-5.exe' -Force
Write-Host "Built: $PSScriptRoot\dist\Clearspace.exe"

