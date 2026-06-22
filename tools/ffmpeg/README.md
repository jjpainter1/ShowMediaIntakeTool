FFmpeg binaries are not stored in git.

Run `scripts\build-release.ps1` to download and stage `ffmpeg.exe` and `ffprobe.exe`
into the release zip under `tools\ffmpeg\bin\`.

For local packaging tests without a full release build, copy ffprobe manually here or run:

```powershell
.\scripts\build-release.ps1 -SkipTauriBuild
```
