# YouTube Downloader Studio v1.1.0

## Features
- Redesigned GUI with Simple, Advanced and Professional workspaces.
- Balanced, Maximum speed, Maximum reliability and Data saver presets.
- Improved batch queue actions, retry, selection and cleanup.
- First-run compatibility checker and local engineering diagnostic tools.
- More complete screenshots and usage guides.
- Source comments explaining downloader arguments, tool integrity, queue persistence and throttled UI rendering.

## Standalone Windows build
The Windows x64 EXE bundles Python, Qt, yt-dlp, Deno, FFmpeg and FFprobe. No separate installer is required. Verify with the attached SHA256SUMS.txt.

## Validation
31 Windows automated tests passed on November 22, 2026. See windows-verification.json for isolated application verification once available. Windows binary is unsigned. Linux x86-64 v1.1.0 was rebuilt on November 24, 2026 using WSL Ubuntu 24.04 (glibc 2.39 baseline). The 32 applicable Linux tests, packaged GUI smoke test, tool checks and synthetic local-media download passed. Two Windows-specific loader tests were replaced with native equivalents. Other distributions and live YouTube downloads were not tested. Verify the Linux archive using SHA256SUMS-linux.txt. macOS has not been rebuilt.

Download only media that you have the right to save. Authentication, site protections and third-party availability may change.

## Guide
See [README](https://github.com/farshid1996/youtube_downloader#readme) and [Visual walkthrough](https://github.com/farshid1996/youtube_downloader#visual-walkthrough).
