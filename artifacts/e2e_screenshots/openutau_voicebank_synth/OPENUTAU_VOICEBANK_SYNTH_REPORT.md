# OpenUtau Eugene real voicebank synthesis validation

## Verdict

**Passed / synthesis proven.** The OpenACE-exported USTX was not merely visually loadable: official OpenUtau 0.1.576 attached the real temporary `友人` voicebank, phonemized and rendered the part, started playback, and produced a nonzero rendered WAV cache whose duration matches the project.

## Evidence

- GUI zoom shows track `Eugene validation`, singer `友人`, `JA VCV & CVVC`, engine `WORLDLINE-R`; no missing-singer or phonemizer error appeared.
- OpenUtau log contains:
  - `Attach singer to track: 友人`
  - `Publish notification Phonemized`
  - `Publish notification Part rendered.`
  - `StartPlayback at 00:00:00`
- Rendered cache file found:
  - `/home/ubuntu/.cache/OpenUtau/wdl-v10-fb08d7f099260031.wav`
  - duration `4.85s` at `44100Hz`, mono
  - RMS `0.2017346743`, peak `0.7326660156`, nonzero
  - size `427816` bytes
- This duration closely matches eight quarter notes at the displayed project tempo `100` (`4.8s` musical content plus small rendering boundary/tail), strongly supporting that this cache is the validation part render.
- USTX confirms `singer: 友人`, `OpenUtau.Plugin.Builtin.JapanesePresampPhonemizer`, romaji/CVVC-safe lyrics `a/ka/sa/ta/na/ha/ma/ya`.

## Notes/blockers

- OpenUtau update check failed with GitHub/appcast `403 rate limit`; unrelated to synthesis.
- A BPM dialog was accidentally opened during transport probing and closed without changing tempo; this did not affect the already-completed render evidence.
- Browser/sandbox audio perception was not used as proof; log + rendered cache WAV measurements are the strong evidence.
- No OpenACE repo code was modified. No voicebank file or voicebank-derived rendered audio is copied into the OpenACE repo.

## Artifacts

- `00_initial_gui.png`
- `01_playback_started.png`
- `02_singer_track_zoom.png` — clearest singer/engine proof
- `03_after_playback.png`
- `04_final_gui.png`
- `openutau_log_excerpt.txt`
- `wav_measurements.json`
- Rendered cache audio was measured locally but is intentionally not committed because the temporary third-party voicebank is noncommercial-licensed; measurements/log/screenshots are the durable evidence.
