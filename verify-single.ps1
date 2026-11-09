$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$isolatedRoot = Join-Path $env:TEMP ('YouTubeDownloader-standalone-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $isolatedRoot | Out-Null
$isolatedExe = Join-Path $isolatedRoot 'YouTubeDownloader.exe'
Copy-Item -LiteralPath '.\dist\single\YouTubeDownloader.exe' -Destination $isolatedExe
$previousLocalAppData = $env:LOCALAPPDATA
$previousPath = $env:PATH
try {
    $env:LOCALAPPDATA = Join-Path $isolatedRoot 'userdata'
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $gui = Start-Process -FilePath $isolatedExe -WorkingDirectory $isolatedRoot -ArgumentList '--smoke-test' -WindowStyle Hidden -PassThru -Wait
    Write-Output "Isolated GUI exit: $($gui.ExitCode)"
    if ($gui.ExitCode -ne 0) { throw 'Isolated GUI failed' }
    $bundle = Start-Process -FilePath $isolatedExe -WorkingDirectory $isolatedRoot -ArgumentList '--verify-bundle' -WindowStyle Hidden -PassThru -Wait
    Write-Output "Isolated bundled tools exit: $($bundle.ExitCode)"
    $report = Join-Path $env:LOCALAPPDATA 'YouTubeDownloaderStudio\bundle-verification.json'
    Get-Content -LiteralPath $report
    if ($bundle.ExitCode -ne 0) { throw 'Bundled tools failed' }
    # Simulate missing installed tools, then verify repair on the next launch.
    $toolsRoot = Join-Path $env:LOCALAPPDATA 'YouTubeDownloaderStudio\tools'
    Get-ChildItem -LiteralPath $toolsRoot -Filter '*.exe' -Recurse | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force
    }
    $repair = Start-Process -FilePath $isolatedExe -WorkingDirectory $isolatedRoot -ArgumentList '--verify-bundle' -WindowStyle Hidden -PassThru -Wait
    if ($repair.ExitCode -ne 0) { throw 'Bundled tools repair failed' }
    Write-Output 'Missing-tool repair and relaunch: passed'
    Copy-Item -LiteralPath $report -Destination '.\standalone-verification.json'
} finally {
    $env:LOCALAPPDATA = $previousLocalAppData
    $env:PATH = $previousPath
}
