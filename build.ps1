$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe package_tools.py
if ($LASTEXITCODE -ne 0) { throw 'Tool payload preparation failed' }
$originalPath = $env:PATH
# Do not accidentally bundle ICU/UCRT DLLs from unrelated development tools.
try {
    $env:PATH = "$PSScriptRoot\.venv\Scripts;$env:SystemRoot\System32;$env:SystemRoot"
    & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name YouTubeDownloader --icon app.ico --add-data 'app.ico;.' --add-data 'assets;assets' --add-data 'tools.zip;.' --add-data 'tools-manifest.json;.' --add-data 'THIRD_PARTY_NOTICES.txt;.' main.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
} finally {
    $env:PATH = $originalPath
}
Copy-Item -LiteralPath README.md,THIRD_PARTY_NOTICES.txt -Destination dist\YouTubeDownloader -Force
Write-Host 'Ready: dist\YouTubeDownloader\YouTubeDownloader.exe'