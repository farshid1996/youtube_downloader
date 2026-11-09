# Native Linux and macOS packages

These additional files reuse the existing GUI without editing main.py, engine.py,
the Windows build scripts, or the Windows EXE. launcher.py supplies native tool
installation, executable permissions, application-data paths and process-group
cancellation. Downloaded media and queue features are the same as on Windows.

## Build

On the target OS, install Python 3.11 or 3.12 and run from the project folder:

```sh
bash portable/build.sh
```

The build downloads pinned native yt-dlp, Deno, FFmpeg and FFprobe binaries, checks
yt-dlp/Deno against upstream SHA-256 files, records all download hashes, tests the
tools, and bundles Python, Qt and all four tools. FFmpeg hashes are recorded from
HTTPS downloads; they are not independently authenticated upstream checksums.
Keep portable/downloads to reuse downloads. Do not share portable/payload between
simultaneous builds. Each CI job uses an isolated checkout.

Linux output: dist/linux-x64/YouTubeDownloader (or linux-arm64), plus a tar.gz
that preserves the executable permission. Extract and double-click the binary.
If transferring the bare binary instead, run chmod +x YouTubeDownloader first.
No Python, FFmpeg or Deno installation is needed on the destination computer.
This is a native single-file executable, not an AppImage. It needs a compatible
Linux desktop and system graphics libraries. A build made on Ubuntu 24.04 targets
glibc 2.39 or newer; build on an older supported distro for a lower baseline.

macOS output: dist/macos-arm64 or dist/macos-x64, containing YouTubeDownloader.app,
a ZIP preserving the app bundle, and YouTubeDownloader.dmg. Copy the app from the
DMG to Applications. Python and download tools are included inside the app bundle.
Build Apple Silicon with native arm64 Python, and Intel with x86_64 Python.
These are separate architectures, not a universal binary. The unsigned/ad-hoc
signed build is for personal testing and may require macOS Open Anyway approval.
Set MACOS_SIGNING_IDENTITY for Developer ID signing; notarization requires an Apple
developer account and is not performed by this build script.

Linux build dependencies on Ubuntu include python3-venv, libegl1, libopengl0,
libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-keysyms1,
libxcb-shape0, libxcb-xinerama0, libxcb-randr0, and libxcb-render-util0.
For CI GUI verification, also install xvfb and xauth.

## Verify

Run `bash portable/check.sh` for the native adapter tests and the existing GUI,
queue and local-download regression suite. The Windows-specific loader test is
excluded because the native launcher replaces that loader.

Run `python3 portable/verify.py path/to/executable`. For macOS pass
`dist/macos-arm64/YouTubeDownloader.app/Contents/MacOS/YouTubeDownloader`.
The verifier isolates user data, runs the GUI smoke test, validates all bundled
tools and downloads a synthetic video from localhost. It never touches your
regular queue, browser cookies or download folder. On headless Linux use
`xvfb-run -a python3 portable/verify.py dist/linux-x64/YouTubeDownloader`.

Data is stored under ~/.local/share/YouTubeDownloaderStudio on Linux (or
$XDG_DATA_HOME) and ~/Library/Application Support/YouTubeDownloaderStudio on Mac.

The additional GitHub Actions workflow can build both Mac architectures and Linux
when these files are placed in a GitHub repository and manually dispatched. Adding
the workflow locally does not upload source or start a remote build.

For a Mac without the project, extract dist/native-build-source.zip, open Terminal
in the extracted folder, and run `bash portable/build.sh`. The archive is source
and build instructions, not a prebuilt macOS app.
