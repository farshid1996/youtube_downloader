# Verification — 2026-11-02

- Automated tests: **8 passed** (seven application tests plus the engine-update persistence test).
- Single-file build: copied only the EXE to an isolated temporary folder, used fresh per-user storage and a Windows-only PATH. GUI smoke test exited 0. Bundled yt-dlp, Deno, FFmpeg and FFprobe all ran successfully; FFmpeg generated a video and FFprobe confirmed its 320×180 dimensions. Verified engine updates are retained instead of replaced by the embedded version on restart.
- UI update: tested menu targeting, enabled/disabled actions, pause/resume, copy link, preparing a new download and removing a row while keeping its file. Checked input heights in all tabs in a 960×650 window. Visually reviewed options at 100% and 150% scaling and the context menu.
- Quality-upgrade regression: downloaded 720p then 1080p for the same video ID to one folder with archive enabled; verified two files and actual heights of 720 and 1080 using FFprobe. Verified an identical repeat is skipped, and the GUI labels an existing-file repeat as Skipped.
- Downloaded a generated video over localhost using the real yt-dlp executable; verified MP4 audio and video streams with FFprobe.
- Downloaded and converted the same source to MP3; verified its audio stream with FFprobe.
- Exercised the GUI queue: started a throttled transfer, paused its process tree, confirmed a partial file, resumed successfully, verified final output and persistent queue state.
- Confirmed HTTP 404 becomes a Failed item with a useful error.
- Verified URL validation and argument separation.
- Progress-bar update: verified real percentage events during a throttled download, a partially filled bar, pause/resume, and a full bar on completion. Explicitly enabled engine progress output alongside metadata printing.
- Ran source UI smoke test and visually reviewed its screenshot.
- Ran final packaged Windows executable smoke test: **exit code 0**, screenshot generated successfully.
- Fixed packaging contamination from unrelated ICU/UCRT libraries by restricting the build PATH.

## Requested YouTube link

`https://www.youtube.com/watch?v=vDmjw-c_R2k`

Real network attempt using yt-dlp 2026.10.26 and bundled Deno: **blocked by YouTube**, which returned “Sign in to confirm you're not a bot.” No video was downloaded from this URL. The user requested continuing without browser access; no cookies were read.

## Scope

This verifies the listed local workflows and executable startup on this Windows PC. Playlist expansion, live subtitles, proxy servers, authenticated downloads, other PCs and every output codec combination were not exhaustively tested. Remote availability depends on the source service.

## Standalone repair — 2026-11-03

Rebuilt dist/single/YouTubeDownloader.exe and copied the verified artifact to dist/YouTubeDownloader/YouTubeDownloader.exe.

- Eight existing/regression tests passed; the additional missing-tools GUI regression test also passed (nine total).
- Copied only the EXE into an isolated temporary folder with fresh LOCALAPPDATA and a system-only PATH.
- GUI smoke test: passed.
- All four embedded tools launched successfully.
- Generated/probed H.264 media and inspected/downloaded it using the packaged yt-dlp: passed.
- Deleted all four installed test tools and relaunched the copied EXE: automatic restoration and the entire bundle verification passed again.
- Repair regression covers corrupted tools and preserving an explicitly accepted engine update.

The screenshot establishes a missing extracted yt-dlp executable. The original archive contains it; the reason it disappeared on the other PC is not established. The replacement packages tools as a checked archive and installs them to versioned per-user storage, with repair and recoverable GUI errors. Security software can still block executables; no security settings are changed.

This verification ran on the build PC in an isolated environment, not on the recipient PC or a clean Windows VM. Live YouTube authentication/network behavior is outside the offline bundle test.
