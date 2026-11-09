$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe package_tools.py
if ($LASTEXITCODE -ne 0) { throw 'Tool payload preparation failed' }
$originalPath = $env:PATH
try {
    $env:PATH = "$PSScriptRoot\.venv\Scripts;$env:SystemRoot\System32;$env:SystemRoot"
    & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile --noupx --name YouTubeDownloader --distpath dist\single --workpath build\single --specpath build --icon "$PSScriptRoot\app.ico" --add-data "$PSScriptRoot\app.ico;." --add-data "$PSScriptRoot\assets;assets" --add-data "$PSScriptRoot\tools.zip;." --add-data "$PSScriptRoot\tools-manifest.json;." --add-data "$PSScriptRoot\THIRD_PARTY_NOTICES.txt;." --add-data "$PSScriptRoot\README.md;." main.py
    if ($LASTEXITCODE -ne 0) { throw 'Single-file build failed' }
} finally {
    $env:PATH = $originalPath
}
Write-Host 'Ready: dist\single\YouTubeDownloader.exe'
