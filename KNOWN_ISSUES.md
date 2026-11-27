# Known Issues / Escape-Hatch Register

## Critical validation gaps

- Real GPU inference has not been run in this CPU-only cloud sandbox. `scripts/verify_local_gpu.py` is the required acceptance gate on a 12GB NVIDIA machine.
- Real SoulX-Singer/ACE-Step output quality, exact preprocess artifacts, and ACE-Step repaint/complete semantics still need physical GPU logs and listening validation.

## Current product gaps after the independent browser QA fix round

- Pitch automation affects SoulX target F0; Dynamic, Air, Energy, Tension, and Falsetto automation are applied as explicitly labeled post-render DSP. Breath events still persist without affecting sound.
- Piano roll now has marquee/multi-select/copy-paste/duplicate/quantize/context menu/velocity lane, per-note vibrato editing, and per-note pitch handles, cross-track clipboard is regression-verified, and dense 3000-note 60FPS playback/scroll proof exists at 1400×900@2x.
- Arrangement now uses decoded waveform peaks and supports independent audio-clip/grouped-note dragging, edge trim, split-at-cursor, linear fade endpoints, clip gain, and automatic equal-power crossfades, and clip copy/paste/duplicate/delete, but still lacks richer track-level operations.
- Repaint region selection is implemented via Alt-drag plus numeric seconds; the underlying ACE-Step repaint output has not been validated on GPU.
- MP4 export now burns timed ASS subtitles and matches audio duration, but it is not polished karaoke highlighting. On Linux hosts without CJK fonts, Chinese glyphs may render as tofu even though project/export text is valid UTF-8.
- `.ustx`/`.svp`/`.vpr` writers are structural implementations and must be opened in the real target applications for schema validation.
- Cantonese and Japanese phoneme coverage are incomplete; unsupported input correctly errors instead of silently becoming “la”.
- Render jobs now persist across backend restart, but interrupted jobs are marked failed rather than automatically requeued.
- Faster-whisper lyric transcription exists as a helper but is not yet integrated into the visible SVC/import workflow.
