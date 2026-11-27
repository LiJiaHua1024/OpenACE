# MP3/FLAC/OGG Export Regression QA

Visible Chrome validation on rendered fixture project `Mix Automation QA` after backend restart and cache-bust. Implementation was not modified.

## Assertions

- **Buttons visible:** passed — export grid contains WAV, MP3, FLAC, OGG, STEMS, MP4, MID, LRC, USTX, SVP, VPR.
- **MP3 download/ffprobe:** passed — `Mix Automation QA.mp3`, 82,605 bytes, codec `mp3`, 48 kHz stereo, 320 kbps, duration 2.04 s.
- **FLAC download/ffprobe:** passed — `Mix Automation QA.flac`, 149,029 bytes, codec `flac`, 48 kHz stereo, duration 2.00 s.
- **OGG download/ffprobe:** passed — `Mix Automation QA.ogg`, 11,669 bytes, codec `vorbis`, 48 kHz stereo, duration 2.00 s.
- **WAV/STEMS regression:** passed — WAV downloaded 576,044 bytes; STEMS zip downloaded 384,877 bytes.
- **Layout:** passed — export grid remained three-column/contained; right panel `clientWidth == scrollWidth == 311`, no horizontal page overflow.
- **Console/page/network:** passed — no errors or failed responses.

No defects found.

## Artifacts

- `codec_export_results.json`
- `master.mp3`, `master.flac`, `master.ogg`, `master.wav`, `stems.zip`
- `00_codec_export_buttons.png`, `01_after_codec_downloads.png`
