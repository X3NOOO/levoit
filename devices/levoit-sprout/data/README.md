# Sprout audio files

Files in this folder are built into the `assets` SPIFFS partition when you run `esphome run`.

Up to 6 MP3 files are supported. Place the files you want here before building — missing files are silently skipped.

| File | Sound |
|------|-------|
| `100001.mp3` | Summer rain |
| `100002.mp3` | Gentle sea wave |
| `100003.mp3` | Sound 03 |
| `100004.mp3` | Sound 04 |
| `100005.mp3` | Sound 05 |
| `100006.mp3` | Insects chirp by the stream |

Only MP3 files are supported. Any `.ogg` files are skipped with a warning during build.

## File size

Keep files small — the `assets` partition is **~1.44 MB** total (4 MB flash) or **2 MB** (8 MB flash).

Re-encode if needed:
```bash
ffmpeg -i input.mp3 -b:a 32k -ar 32000 -ac 1 output.mp3
```
