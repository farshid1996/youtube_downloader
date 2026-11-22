$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$target = Join-Path $PSScriptRoot 'audit_sources'
if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}
New-Item -ItemType Directory -Path $target -Force | Out-Null

$rootFiles = @(
    'main.py', 'engine.py', 'system_check.py', 'project_orchestrator.py',
    'requirements.txt', 'README.md', 'build.ps1', 'build-single.ps1',
    'verify-single.ps1', 'THIRD_PARTY_NOTICES.txt', 'YouTubeDownloader.spec',
    'package_tools.py', 'prepare_tools.py', 'tools-manifest.json'
)
foreach ($relative in $rootFiles) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $relative) -Destination $target -Force
}

foreach ($directory in @('tests', 'portable', '.github/workflows')) {
    $destination = Join-Path $target $directory
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
}

foreach ($relative in @('tests/test_app.py', 'tests/test_system_check.py',
                        'tests/test_professional_options.py',
                        'portable/launcher.py', 'portable/build.py',
                        'portable/verify.py', 'portable/README.md',
                        'portable/build.sh', 'portable/check.sh',
                        '.github/workflows/native-desktop.yml')) {
    $destination = Join-Path $target $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $relative) -Destination $destination -Force
}

Write-Host "Prepared audit source snapshot: $target"
